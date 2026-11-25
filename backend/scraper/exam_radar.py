import os
import sys
import json
import asyncio
import httpx
from lxml import html
from duckduckgo_search import DDGS
from supabase import create_client
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services import extract_and_evaluate_opportunities
from notifier import async_notify_new_opportunity
from link_resolver import resolve_opportunity_url

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

OFFICIAL_EXAM_QUERIES = [
    ("TCS NQT / CodeVita", "TCS NQT registration 2026 2027 site:tcs.com"),
    ("GATE Official", "GATE 2027 notification registration site:ac.in"),
    ("ISRO ICRB", "ISRO ICRB recruitment scientist engineer site:isro.gov.in"),
    ("DRDO RAC / CEPTAM", "DRDO recruitment notification scientist engineer site:drdo.gov.in"),
    ("BARC OCES", "BARC OCES recruitment engineering site:barc.gov.in"),
    ("NIC / NIELIT", "NIELIT NIC scientist recruitment site:nielit.gov.in"),
    ("Infosys HackWithInfy", "HackWithInfy registration 2026 2027 site:infosys.com"),
    ("Smart India Hackathon", "Smart India Hackathon registration site:sih.gov.in"),
    ("GSoC", "Google Summer of Code timeline site:summerofcode.withgoogle.com"),
]


def get_db():
    return create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))


def _fetch_page_lightweight(url: str, timeout: float = 8.0) -> tuple[str, dict]:
    """Lightweight httpx + lxml fetcher (zero Playwright RAM overhead)."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return "", {}
            tree = html.fromstring(resp.text[:200000])
            for bad in tree.xpath('//script|//style|//nav|//footer'):
                bad.drop_tree()
            text = " ".join(tree.text_content().split())
            links = {}
            for a_el in tree.xpath('//a[@href]'):
                href = a_el.get('href', '').strip()
                label = " ".join((a_el.text_content() or '').split())
                if href.startswith(('http://', 'https://')) and len(label) > 2:
                    links[label[:60]] = href
            return text[:15000], links
    except Exception:
        return "", {}


async def run_exam_radar():
    """
    Lightweight Official Exam & PSU Radar using DuckDuckGo site: queries + httpx + lxml.
    Designed to run safely within Render's 512MB RAM limit.
    """
    print("[Exam Radar] Starting lightweight official exam & PSU bulletin scan...")
    db = get_db()

    users_res = db.table('users').select('id').execute()
    users = users_res.data or []
    if not users:
        print("[Exam Radar] No users found.")
        return

    # 1. Run official queries once per sweep to save search quota & RAM
    discovered_pages = []
    for label, query in OFFICIAL_EXAM_QUERIES:
        try:
            results = await asyncio.to_thread(lambda q=query: list(DDGS().text(q, max_results=2)))
            for r in results:
                href = r.get('href')
                if href:
                    discovered_pages.append((label, r.get('title', label), href, r.get('body', '')))
        except Exception as e:
            print(f"[Exam Radar] Search failed for '{label}': {e}")
            await asyncio.sleep(1)

    print(f"[Exam Radar] Fetched {len(discovered_pages)} official search hits. Evaluating per user...")

    for user in users:
        user_id = user['id']
        prof_res = db.table('user_profiles').select('*').eq('user_id', user_id).execute()
        if not prof_res.data:
            continue
        profile = prof_res.data[0]
        if not profile.get('ai_filter_directive'):
            continue

        sched_res = db.table('user_schedules').select('*').eq('user_id', user_id).execute()
        schedule = sched_res.data or []

        for label, hit_title, url, snippet in discovered_pages:
            try:
                page_text, link_dict = await asyncio.to_thread(_fetch_page_lightweight, url)
                raw_text = f"Official Exam Notice ({label}): {hit_title}\nSnippet: {snippet}\n\n{page_text}"
                if len(raw_text.strip()) < 60:
                    continue
                link_dict[hit_title[:60]] = url

                evaluated = await asyncio.to_thread(
                    extract_and_evaluate_opportunities,
                    raw_text,
                    json.dumps(link_dict),
                    profile,
                    schedule,
                    url,
                    f"Exam Radar: {label}"
                )

                for eval_job in evaluated:
                    raw_apply = eval_job.apply_url or url
                    resolved_apply, is_official = await asyncio.to_thread(resolve_opportunity_url, raw_apply)

                    tags = list(eval_job.tags or [])
                    if "Official Exam Radar" not in tags:
                        tags.append("Official Exam Radar")

                    record = {
                        'user_id': user_id,
                        'title': eval_job.title,
                        'company': eval_job.company,
                        'description': eval_job.description,
                        'source_url': url,
                        'apply_url': resolved_apply,
                        'match_score': eval_job.match_score,
                        'schedule_conflict': eval_job.schedule_conflict,
                        'schedule_conflict_reason': eval_job.schedule_conflict_reason,
                        'legitimacy_score': eval_job.legitimacy_score,
                        'fraud_risk_score': eval_job.fraud_risk_score,
                        'credibility_flags': eval_job.credibility_flags,
                        'pros': eval_job.pros,
                        'cons': eval_job.cons,
                        'raw_text': raw_text[:4000],
                        'source_name': f"Exam Radar: {label}",
                        'source_tier': 'TIER_1_TRUSTED',
                        'category': eval_job.category,
                        'tags': tags,
                        'status': 'INBOX',
                        'eligible_batches': eval_job.eligible_batches,
                        'stipend_or_ctc': eval_job.stipend_or_ctc,
                        'application_deadline': eval_job.application_deadline,
                        'exam_date': eval_job.exam_date,
                        'is_official_source': bool(eval_job.is_official_source or is_official),
                        'telegram_notified': False,
                    }

                    # Deduplicate by apply_url or title+company
                    dup = db.table('opportunities').select('id').eq('user_id', user_id).eq('apply_url', resolved_apply).execute()
                    if not dup.data:
                        dup = db.table('opportunities').select('id').eq('user_id', user_id).eq('title', eval_job.title).eq('company', eval_job.company).execute()
                    if dup.data:
                        continue

                    ins = db.table('opportunities').insert(record).execute()
                    if ins.data:
                        record['id'] = ins.data[0]['id']
                        await async_notify_new_opportunity(db, record, profile)

            except Exception as e:
                print(f"[Exam Radar] Error processing {url}: {e}")

    print("[Exam Radar] Scan complete.")


if __name__ == "__main__":
    asyncio.run(run_exam_radar())

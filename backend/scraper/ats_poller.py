import os
import re
import sys
import json
import asyncio
from typing import Optional
from urllib.parse import urlparse
import httpx
from lxml import html as lxml_html
from supabase import create_client
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import extract_and_evaluate_opportunities
from notifier import async_notify_new_opportunity

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

SENIOR_TITLE_REGEX = re.compile(
    r'\b(senior|sr\.?|staff|principal|director|lead|manager|vp|vice\s+president|iii|iv)\b',
    re.IGNORECASE,
)

LOCALE_SEGMENT_REGEX = re.compile(r'^[a-z]{2}(?:-[A-Z]{2})?$', re.IGNORECASE)


def get_db():
    return create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))


def is_senior_title(title: str) -> bool:
    return bool(title and SENIOR_TITLE_REGEX.search(title))


def _strip_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    try:
        doc = lxml_html.fromstring(raw_html)
        return " ".join(doc.text_content().split())
    except Exception:
        return re.sub(r'<[^>]+>', ' ', raw_html).strip()


def parse_ats_url(url: str) -> Optional[dict]:
    """
    Detects and parses Workday, Greenhouse, Lever, and Ashby board URLs.
    Strips optional Workday locale segments (e.g., /en-US/, /en-GB/).
    """
    if not url or not isinstance(url, str):
        return None
    cleaned = url.strip()
    if not cleaned.startswith(('http://', 'https://')):
        cleaned = 'https://' + cleaned

    try:
        parsed = urlparse(cleaned)
        host = parsed.netloc.lower().split(':')[0]
        parts = [p for p in parsed.path.split('/') if p]

        # 1. Workday: https://{tenant}.wd{N}.myworkdayjobs.com/{optional_locale}/{site}
        wd_match = re.match(r'^([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com$', host)
        if wd_match:
            tenant, wd = wd_match.group(1), wd_match.group(2)
            # Strip optional locale segment(s) like en-US, en-GB, fr-FR
            filtered_parts = [p for p in parts if not LOCALE_SEGMENT_REGEX.match(p)]
            if not filtered_parts:
                return None
            site = filtered_parts[0]
            return {
                "platform": "workday",
                "tenant": tenant,
                "wd": wd,
                "site": site,
                "host": host,
                "company": tenant.replace('-', ' ').title(),
            }

        # 2. Greenhouse: boards.greenhouse.io/{slug} or job-boards.greenhouse.io/{slug}
        if host in ('boards.greenhouse.io', 'job-boards.greenhouse.io') and parts:
            slug = parts[0]
            return {
                "platform": "greenhouse",
                "slug": slug,
                "company": slug.replace('-', ' ').title(),
            }

        # 3. Lever: jobs.lever.co/{slug}
        if host == 'jobs.lever.co' and parts:
            slug = parts[0]
            return {
                "platform": "lever",
                "slug": slug,
                "company": slug.replace('-', ' ').title(),
            }

        # 4. Ashby: jobs.ashbyhq.com/{slug}
        if host == 'jobs.ashbyhq.com' and parts:
            slug = parts[0]
            return {
                "platform": "ashby",
                "slug": slug,
                "company": slug.replace('-', ' ').title(),
            }
    except Exception:
        return None

    return None


def _build_workday_queries(profile: Optional[dict]) -> list[str]:
    default_queries = ["Software", "Intern", "Engineer"]
    if not profile:
        return default_queries
    roles_raw = str((profile.get('form_preferences') or {}).get('roles') or '')
    if not roles_raw:
        return default_queries
    tokens = [t.strip().split()[0] for t in roles_raw.split(',') if t.strip()]
    merged = []
    for q in tokens + default_queries:
        if q and q.lower() not in [m.lower() for m in merged]:
            merged.append(q)
    return merged[:3]


async def fetch_workday_jobs(
    parsed: dict,
    queries: Optional[list[str]] = None,
    seen_urls: Optional[set[str]] = None,
    max_details: int = 10,
    fetch_details: bool = True,
    client: Optional[httpx.AsyncClient] = None,
) -> list[dict]:
    """
    Polls Workday CXS JSON API with strict limit <= 20, anti-N+1 dedup,
    senior-title pre-filter, max 10 detail fetches, and 10s timeout.
    """
    host = parsed["host"]
    tenant = parsed["tenant"]
    site = parsed["site"]
    list_url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    search_queries = queries or ["Software", "Intern", "Engineer"]
    known_urls = seen_urls if seen_urls is not None else set()

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=10.0)

    candidates = []
    batch_urls = set()

    try:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        for query in search_queries[:3]:
            payload = {
                "limit": 20,  # Mandatory Workday cap: never > 20
                "offset": 0,
                "searchText": query,
                "appliedFacets": {},
            }
            try:
                resp = await client.post(list_url, json=payload, headers=headers)
                if resp.status_code in (401, 403, 404, 422):
                    print(f"[ATS Workday] Tenant {tenant}/{site} returned HTTP {resp.status_code} on list. Skipping.")
                    break
                resp.raise_for_status()
                data = resp.json()
            except (httpx.TimeoutException, httpx.HTTPError, ValueError) as e:
                print(f"[ATS Workday] List fetch failed for {tenant}/{site} ({query}): {e}")
                continue

            for posting in data.get("jobPostings") or []:
                title = (posting.get("title") or "").strip()
                ext_path = (posting.get("externalPath") or "").strip()
                if not title or not ext_path:
                    continue
                if not ext_path.startswith("/"):
                    ext_path = "/" + ext_path
                canonical_url = f"https://{host}/{site}{ext_path}"

                if canonical_url in known_urls or canonical_url in batch_urls:
                    continue
                if is_senior_title(title):
                    continue

                batch_urls.add(canonical_url)
                candidates.append({
                    "title": title,
                    "company": parsed["company"],
                    "location": posting.get("locationsText") or "",
                    "url": canonical_url,
                    "external_path": ext_path,
                    "posted_on": posting.get("postedOn") or "",
                    "description": "",
                })

        if not fetch_details:
            return candidates

        results = []
        for job in candidates[:max_details]:
            detail_url = f"https://{host}/wday/cxs/{tenant}/{site}{job['external_path']}"
            try:
                d_resp = await client.get(detail_url, headers={"Accept": "application/json"})
                if d_resp.status_code in (401, 403, 404, 422):
                    continue
                d_resp.raise_for_status()
                info = (d_resp.json().get("jobPostingInfo") or {})
                job["description"] = _strip_html(info.get("jobDescription") or "")
                job["start_date"] = info.get("startDate")
                if info.get("externalUrl"):
                    job["url"] = info["externalUrl"]
                results.append(job)
            except (httpx.TimeoutException, httpx.HTTPError, ValueError) as e:
                print(f"[ATS Workday] Detail fetch failed for {detail_url}: {e}")
                continue
        return results
    finally:
        if owns_client:
            await client.aclose()


async def fetch_greenhouse_jobs(
    parsed: dict,
    seen_urls: Optional[set[str]] = None,
    max_jobs: int = 15,
    client: Optional[httpx.AsyncClient] = None,
) -> list[dict]:
    slug = parsed["slug"]
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    known_urls = seen_urls if seen_urls is not None else set()

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=10.0)

    try:
        resp = await client.get(url)
        if resp.status_code in (401, 403, 404, 422):
            return []
        resp.raise_for_status()
        jobs = resp.json().get("jobs") or []
    except (httpx.TimeoutException, httpx.HTTPError, ValueError) as e:
        print(f"[ATS Greenhouse] Fetch failed for {slug}: {e}")
        return []
    finally:
        if owns_client:
            await client.aclose()

    out = []
    for item in jobs:
        title = (item.get("title") or "").strip()
        job_url = (item.get("absolute_url") or "").strip()
        if not title or not job_url or job_url in known_urls or is_senior_title(title):
            continue
        loc = (item.get("location") or {}).get("name") or ""
        out.append({
            "title": title,
            "company": parsed["company"],
            "location": loc,
            "url": job_url,
            "description": _strip_html(item.get("content") or ""),
        })
        if len(out) >= max_jobs:
            break
    return out


async def fetch_lever_jobs(
    parsed: dict,
    seen_urls: Optional[set[str]] = None,
    max_jobs: int = 15,
    client: Optional[httpx.AsyncClient] = None,
) -> list[dict]:
    slug = parsed["slug"]
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    known_urls = seen_urls if seen_urls is not None else set()

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=10.0)

    try:
        resp = await client.get(url)
        if resp.status_code in (401, 403, 404, 422):
            return []
        resp.raise_for_status()
        jobs = resp.json()
        if not isinstance(jobs, list):
            return []
    except (httpx.TimeoutException, httpx.HTTPError, ValueError) as e:
        print(f"[ATS Lever] Fetch failed for {slug}: {e}")
        return []
    finally:
        if owns_client:
            await client.aclose()

    out = []
    for item in jobs:
        title = (item.get("text") or "").strip()
        job_url = (item.get("hostedUrl") or "").strip()
        if not title or not job_url or job_url in known_urls or is_senior_title(title):
            continue
        loc = (item.get("categories") or {}).get("location") or ""
        desc = item.get("descriptionPlain") or _strip_html(item.get("description") or "")
        out.append({
            "title": title,
            "company": parsed["company"],
            "location": loc,
            "url": job_url,
            "description": desc,
        })
        if len(out) >= max_jobs:
            break
    return out


async def fetch_ashby_jobs(
    parsed: dict,
    seen_urls: Optional[set[str]] = None,
    max_jobs: int = 15,
    client: Optional[httpx.AsyncClient] = None,
) -> list[dict]:
    slug = parsed["slug"]
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"
    known_urls = seen_urls if seen_urls is not None else set()

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=10.0)

    try:
        resp = await client.get(url)
        if resp.status_code in (401, 403, 404, 422):
            return []
        resp.raise_for_status()
        jobs = resp.json().get("jobs") or []
    except (httpx.TimeoutException, httpx.HTTPError, ValueError) as e:
        print(f"[ATS Ashby] Fetch failed for {slug}: {e}")
        return []
    finally:
        if owns_client:
            await client.aclose()

    out = []
    for item in jobs:
        title = (item.get("title") or "").strip()
        job_url = (item.get("jobUrl") or item.get("applyUrl") or "").strip()
        if not title or not job_url or job_url in known_urls or is_senior_title(title):
            continue
        loc = item.get("location") or ""
        desc = item.get("descriptionPlain") or _strip_html(item.get("descriptionHtml") or "")
        out.append({
            "title": title,
            "company": parsed["company"],
            "location": loc,
            "url": job_url,
            "description": desc,
        })
        if len(out) >= max_jobs:
            break
    return out


async def test_ats_board(url: str) -> dict:
    """Live 1-page test fetch for POST /sources/test-ats without saving to DB."""
    parsed = parse_ats_url(url)
    if not parsed:
        raise ValueError("Unsupported ATS URL. Supported: myworkdayjobs.com, greenhouse.io, lever.co, ashbyhq.com")

    platform = parsed["platform"]
    if platform == "workday":
        jobs = await fetch_workday_jobs(parsed, queries=["Software", "Intern"], fetch_details=False)
    elif platform == "greenhouse":
        jobs = await fetch_greenhouse_jobs(parsed, max_jobs=20)
    elif platform == "lever":
        jobs = await fetch_lever_jobs(parsed, max_jobs=20)
    elif platform == "ashby":
        jobs = await fetch_ashby_jobs(parsed, max_jobs=20)
    else:
        jobs = []

    return {
        "platform": platform,
        "company": parsed["company"],
        "sample_count": len(jobs),
        "sample_titles": [j["title"] for j in jobs[:5]],
    }


async def poll_ats_sources_for_user(db, user_id: str, profile: dict, schedule: list):
    """Polls all ATS-compatible sources saved by a user and evaluates unseen jobs."""
    res_sources = db.table('sources').select('*').eq('user_id', user_id).execute()
    user_sources = res_sources.data or []

    ats_sources = []
    for src in user_sources:
        parsed = parse_ats_url(src.get('url_or_identifier', ''))
        if parsed:
            ats_sources.append((src, parsed))

    if not ats_sources:
        return 0

    existing_res = db.table('opportunities').select('apply_url').eq('user_id', user_id).execute()
    seen_urls = {r['apply_url'] for r in (existing_res.data or []) if r.get('apply_url')}
    queries = _build_workday_queries(profile)
    inserted_count = 0

    async with httpx.AsyncClient(timeout=10.0) as client:
        for src, parsed in ats_sources:
            platform = parsed["platform"]
            source_name = src.get('name') or f"{parsed['company']} ({platform.title()})"
            print(f"[ATS Poller] Polling {source_name} [{platform}] for user {user_id}...")

            if platform == "workday":
                jobs = await fetch_workday_jobs(parsed, queries=queries, seen_urls=seen_urls, max_details=10, client=client)
            elif platform == "greenhouse":
                jobs = await fetch_greenhouse_jobs(parsed, seen_urls=seen_urls, max_jobs=10, client=client)
            elif platform == "lever":
                jobs = await fetch_lever_jobs(parsed, seen_urls=seen_urls, max_jobs=10, client=client)
            elif platform == "ashby":
                jobs = await fetch_ashby_jobs(parsed, seen_urls=seen_urls, max_jobs=10, client=client)
            else:
                jobs = []

            for job in jobs:
                raw_text = (
                    f"Official ATS Posting ({platform.title()})\n"
                    f"Title: {job['title']}\n"
                    f"Company: {job['company']}\n"
                    f"Location: {job.get('location', 'Unspecified')}\n"
                    f"Apply URL: {job['url']}\n\n"
                    f"{job.get('description', '')[:10000]}"
                )
                link_dict = json.dumps({job['title']: job['url']})

                try:
                    evaluated = await asyncio.to_thread(
                        extract_and_evaluate_opportunities,
                        raw_text,
                        link_dict,
                        profile,
                        schedule,
                        job['url'],
                        source_name,
                    )
                except Exception as e:
                    print(f"[ATS Poller] LLM eval failed for '{job['title']}': {e}")
                    continue

                for eval_job in evaluated:
                    apply_url = eval_job.apply_url or job['url']
                    if apply_url in seen_urls:
                        continue

                    tags = list(eval_job.tags or [])
                    platform_tag = f"{platform.title()} ATS"
                    if platform_tag not in tags:
                        tags.append(platform_tag)

                    record = {
                        'user_id': user_id,
                        'title': eval_job.title,
                        'company': eval_job.company or job['company'],
                        'description': eval_job.description,
                        'source_url': src.get('url_or_identifier'),
                        'apply_url': apply_url,
                        'match_score': eval_job.match_score,
                        'schedule_conflict': eval_job.schedule_conflict,
                        'schedule_conflict_reason': eval_job.schedule_conflict_reason,
                        'legitimacy_score': eval_job.legitimacy_score,
                        'fraud_risk_score': eval_job.fraud_risk_score,
                        'credibility_flags': eval_job.credibility_flags,
                        'pros': eval_job.pros,
                        'cons': eval_job.cons,
                        'raw_text': raw_text[:4000],
                        'source_name': source_name,
                        'source_tier': 'TIER_1_TRUSTED',
                        'category': eval_job.category,
                        'tags': tags,
                        'status': 'INBOX',
                        'eligible_batches': eval_job.eligible_batches,
                        'stipend_or_ctc': eval_job.stipend_or_ctc,
                        'application_deadline': eval_job.application_deadline,
                        'exam_date': eval_job.exam_date,
                        'is_official_source': True,
                        'telegram_notified': False,
                    }

                    dup_tc = db.table('opportunities').select('id').eq('user_id', user_id).eq('title', record['title']).eq('company', record['company']).execute()
                    if dup_tc.data:
                        continue

                    ins = db.table('opportunities').insert(record).execute()
                    if ins.data:
                        record['id'] = ins.data[0]['id']
                        seen_urls.add(apply_url)
                        inserted_count += 1
                        await async_notify_new_opportunity(db, record, profile)

    return inserted_count


async def run_ats_poller_for_all_users():
    print("[ATS Poller] Starting Direct ATS sync across all users...")
    db = get_db()
    users = (db.table('users').select('id').execute()).data or []
    for user in users:
        uid = user['id']
        prof_res = db.table('user_profiles').select('*').eq('user_id', uid).execute()
        if not prof_res.data:
            continue
        profile = prof_res.data[0]
        if not profile.get('ai_filter_directive'):
            continue
        schedule = (db.table('user_schedules').select('*').eq('user_id', uid).execute()).data or []
        await poll_ats_sources_for_user(db, uid, profile, schedule)
    print("[ATS Poller] Sync complete.")


if __name__ == "__main__":
    asyncio.run(run_ats_poller_for_all_users())

from urllib.parse import urlparse, urljoin
import httpx
from lxml import html

SHORTENER_DOMAINS = (
    'bit.ly', 'tinyurl.com', 'cutt.ly', 'rb.gy', 't.co',
    'goo.gl', 'shorturl.at', 'rebrand.ly', 'ow.ly'
)

AGGREGATOR_DOMAINS = (
    'freshersvoice.com', 'offcampusjobs4u.com', 'prepinsta.com',
    'talentbattle.in', 'jobringer.com', 'geekgod.in', 'placementstore.com',
    'jobsandinternships.in', 'freshercamp.com', 'govtjobguru.in',
    'sarkariresult.com', 'freejobalert.com'
)

OFFICIAL_PORTAL_DOMAINS = (
    '.gov.in', '.nic.in', '.ac.in', '.edu.in',
    'greenhouse.io', 'lever.co', 'myworkdayjobs.com', 'jobs.ashbyhq.com',
    'smartrecruiters.com', 'icims.com', 'taleo.net', 'bamboohr.com',
    'tcs.com', 'infosys.com', 'wipro.com', 'accenture.com', 'amazon.jobs',
    'careers.google.com', 'careers.microsoft.com', 'unstop.com',
    'internshala.com', 'wellfound.com', 'summerofcode.withgoogle.com'
)


def is_official_portal(url: str) -> bool:
    if not url or not url.startswith(('http://', 'https://')):
        return False
    parsed = urlparse(url.lower())
    host = parsed.netloc
    if any(agg in host for agg in AGGREGATOR_DOMAINS):
        return False
    if any(dom in host for dom in OFFICIAL_PORTAL_DOMAINS):
        return True
    if host.startswith(('careers.', 'jobs.', 'apply.', 'talent.')):
        return True
    return False


def resolve_opportunity_url(url: str, timeout: float = 5.0) -> tuple[str, bool]:
    """
    Fast 1-hop URL canonicalizer & official portal extractor with strict 5s timeout.
    Returns (resolved_url, is_official_source). Never raises; falls back gracefully.
    """
    if not url or not url.startswith(('http://', 'https://')):
        return url, False

    if is_official_portal(url):
        return url, True

    parsed = urlparse(url.lower())
    host = parsed.netloc
    needs_inspection = any(s in host for s in SHORTENER_DOMAINS) or any(a in host for a in AGGREGATOR_DOMAINS)
    if not needs_inspection:
        return url, is_official_portal(url)

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
            resp = client.get(url)
            final_url = str(resp.url) or url

            if is_official_portal(final_url):
                return final_url, True

            # Inspect 1-hop outbound links on aggregator blog posts for official ATS / .gov.in portals
            if resp.status_code == 200 and 'text/html' in resp.headers.get('content-type', '').lower():
                tree = html.fromstring(resp.text[:150000])
                candidates = []
                for a_el in tree.xpath('//a[@href]'):
                    href = a_el.get('href', '').strip()
                    if not href or href.startswith(('#', 'javascript:', 'mailto:')):
                        continue
                    abs_href = urljoin(final_url, href)
                    if is_official_portal(abs_href):
                        text = (a_el.text_content() or '').lower()
                        score = 2 if any(k in text for k in ('apply', 'official', 'register', 'notification', 'portal')) else 1
                        if any(g in abs_href.lower() for g in ('.gov.in', '.nic.in', '.ac.in')):
                            score += 2
                        candidates.append((score, abs_href))

                if candidates:
                    candidates.sort(key=lambda x: x[0], reverse=True)
                    return candidates[0][1], True

            return final_url, is_official_portal(final_url)
    except Exception:
        return url, is_official_portal(url)

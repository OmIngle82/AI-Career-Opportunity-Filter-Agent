import os
import re
import sys
import argparse
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

def get_db() -> Client:
    raw_url = os.getenv("SUPABASE_URL", "")
    raw_key = os.getenv("SUPABASE_KEY", "")

    clean_url = re.sub(r'[^\x20-\x7E]', '', raw_url).strip().replace('"', '').replace("'", "")
    clean_key = re.sub(r'[^\x20-\x7E]', '', raw_key).strip().replace('"', '').replace("'", "")

    if not clean_url or not clean_key:
        raise ValueError("Database credentials missing in environment (.env)")

    domain_match = re.search(r'([a-zA-Z0-9-]+\.supabase\.co)', clean_url)
    if domain_match:
        clean_url = f"https://{domain_match.group(1)}"
    else:
        parsed_url = urlparse(clean_url)
        if not parsed_url.scheme:
            clean_url = f"https://{clean_url}"
        elif parsed_url.scheme != 'https':
            clean_url = clean_url.replace(parsed_url.scheme + "://", "https://")

    return create_client(clean_url, clean_key)

def purge_expired(days: int = 30, dry_run: bool = False) -> int:
    supabase = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    print(f"\n[Retention Purge] Checking for opportunities created before: {cutoff} ({days} days retention)")

    # First, query how many match
    count_res = supabase.table('opportunities').select('id, title, company, created_at').lt('created_at', cutoff).execute()
    expired_records = count_res.data or []
    count = len(expired_records)

    print(f"[Retention Purge] Found {count} expired opportunities.")

    if count == 0:
        print("[Retention Purge] Database is clean. No action required.")
        return 0

    for rec in expired_records[:5]:
        print(f"  - [{rec.get('created_at')}] {rec.get('title')} ({rec.get('company')})")
    if count > 5:
        print(f"  ... and {count - 5} more.")

    if dry_run:
        print(f"[Retention Purge] DRY-RUN enabled. {count} records would be deleted.")
        return count

    # Perform deletion
    del_res = supabase.table('opportunities').delete().lt('created_at', cutoff).execute()
    deleted_count = len(del_res.data) if del_res.data else count
    print(f"[Retention Purge] Successfully deleted {deleted_count} expired opportunities from Supabase.\n")
    return deleted_count

def main():
    parser = argparse.ArgumentParser(description="Purge opportunities older than N days from Supabase.")
    parser.add_argument("--days", type=int, default=30, help="Retention period in days (default: 30)")
    parser.add_argument("--dry-run", action="store_true", help="Inspect matching records without deleting")
    args = parser.parse_args()

    try:
        purge_expired(days=args.days, dry_run=args.dry_run)
    except Exception as e:
        print(f"[ERROR] Retention cleanup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

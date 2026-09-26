import os
import re
import sys
from urllib.parse import urlparse
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from the parent directory
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

def get_db() -> Client:
    raw_url = os.getenv("SUPABASE_URL", "")
    raw_key = os.getenv("SUPABASE_KEY", "")

    # Aggressive sanitization
    clean_url = re.sub(r'[^\x20-\x7E]', '', raw_url).strip().replace('"', '').replace("'", "")
    clean_key = re.sub(r'[^\x20-\x7E]', '', raw_key).strip().replace('"', '').replace("'", "")

    if not clean_url or not clean_key:
        raise ValueError("Database credentials missing")

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

def main():
    print("Initializing Supabase client...")
    try:
        supabase = get_db()
    except Exception as e:
        print(f"Failed to initialize Supabase client: {e}")
        sys.exit(1)
        
    dummy_uuid = '00000000-0000-0000-0000-000000000000'

    print("Purging 'opportunities' table...")
    try:
        res = supabase.table('opportunities').delete().neq('id', dummy_uuid).execute()
        print(f"Deleted {len(res.data)} rows from 'opportunities'.")
    except Exception as e:
        print(f"Error purging 'opportunities': {e}")

    print("Purging 'sources' table...")
    try:
        res = supabase.table('sources').delete().neq('id', dummy_uuid).execute()
        print(f"Deleted {len(res.data)} rows from 'sources'.")
    except Exception as e:
        print(f"Error purging 'sources': {e}")

    print("Purging 'user_profiles' table...")
    try:
        res = supabase.table('user_profiles').delete().neq('id', dummy_uuid).execute()
        print(f"Deleted {len(res.data)} rows from 'user_profiles'.")
    except Exception as e:
        print(f"Error purging 'user_profiles': {e}")
        
    print("Purging 'user_schedules' table...")
    try:
        res = supabase.table('user_schedules').delete().neq('id', dummy_uuid).execute()
        print(f"Deleted {len(res.data)} rows from 'user_schedules'.")
    except Exception as e:
        print(f"Error purging 'user_schedules': {e}")

    print("\n[SUCCESS] Database completely purged and ready for production!")

if __name__ == "__main__":
    main()

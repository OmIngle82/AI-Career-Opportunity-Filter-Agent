import os
import re
import sys
import json
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
        
    print("\n--- USER PROFILES ---")
    try:
        res = supabase.table('user_profiles').select('*').execute()
        print(json.dumps(res.data, indent=2))
    except Exception as e:
        print(f"Error fetching 'user_profiles': {e}")

    print("\n--- SOURCES ---")
    try:
        res = supabase.table('sources').select('*').execute()
        print(json.dumps(res.data, indent=2))
    except Exception as e:
        print(f"Error fetching 'sources': {e}")

if __name__ == "__main__":
    main()

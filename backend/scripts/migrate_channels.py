import os
import re
import sys
from urllib.parse import urlparse
from supabase import create_client, Client
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from backend.scraper.telegram_listener import TARGET_CHANNELS

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

def get_db() -> Client:
    raw_url = os.getenv("SUPABASE_URL", "")
    raw_key = os.getenv("SUPABASE_KEY", "")

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
        
    print(f"Loaded TARGET_CHANNELS: {TARGET_CHANNELS}")
    
    for channel_url in TARGET_CHANNELS:
        if 'dummytestchannel1' in channel_url:
            print(f"Skipping dummy channel: {channel_url}")
            continue
            
        print(f"Processing {channel_url}...")
        
        # Check if already exists
        existing = supabase.table('sources').select('id').eq('url_or_identifier', channel_url).execute()
        if existing.data:
            print(f"  -> Already exists in database. Skipping.")
            continue
            
        # Determine name (e.g., from URL)
        name = channel_url.split('/')[-1] if '/' in channel_url else channel_url
        
        record = {
            'name': name,
            'url_or_identifier': channel_url,
            'source_type': 'TELEGRAM',
            'source_tier': 'TIER_1_TRUSTED'
        }
        
        try:
            supabase.table('sources').insert(record).execute()
            print(f"  -> Successfully inserted.")
        except Exception as e:
            print(f"  -> Error inserting: {e}")

    print("\nMigration completed.")

if __name__ == "__main__":
    main()

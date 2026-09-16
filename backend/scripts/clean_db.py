import os
import psycopg2
from dotenv import load_dotenv

def clean_database():
    print("Initializing Database Cleanup Utility...")
    
    # Load environment variables
    load_dotenv()
    
    # Get the raw database URL and strip pgbouncer suffix if present (psycopg2 compatibility)
    db_url_raw = os.environ.get('DATABASE_URL')
    if not db_url_raw:
        print("Error: DATABASE_URL not found in .env file.")
        return
        
    db_url = db_url_raw.split('?')[0]
    
    try:
        # Establish connection
        print("Connecting to the database...")
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        
        # Execute TRUNCATE command
        # This instantly deletes all rows from the opportunities table and resets any serial sequences if RESTART IDENTITY is used
        print("Wiping 'opportunities' table...")
        cur.execute("TRUNCATE TABLE opportunities;")
        
        print("\n[SUCCESS]: The 'opportunities' table has been completely wiped.")
        print("NOTE: Sources and User Profiles were intentionally preserved.")
        
        # Close connection
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n[ERROR]: Failed to clean database: {e}")

if __name__ == "__main__":
    clean_database()

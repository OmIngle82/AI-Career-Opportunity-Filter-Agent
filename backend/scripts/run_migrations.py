import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    print("Error: DATABASE_URL not found in .env")
    exit(1)

def run_migrations():
    try:
        # Connect to the database, remove pgbouncer query param if it exists because psycopg2 doesn't like it sometimes
        clean_url = DATABASE_URL.replace("?pgbouncer=true", "").replace("&pgbouncer=true", "")
        conn = psycopg2.connect(clean_url)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Read the schema file
        with open("supabase_schema.sql", "r") as f:
            sql_queries = f.read()
            
        print("Running migrations...")
        cursor.execute(sql_queries)
        print("Migrations executed successfully!")
        
    except Exception as e:
        print(f"Failed to execute migrations: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    run_migrations()

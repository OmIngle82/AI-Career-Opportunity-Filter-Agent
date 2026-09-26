import os
import sys
import psycopg2
from dotenv import load_dotenv

# We need passlib to generate the initial hash
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from auth import get_password_hash

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not found in .env")
        sys.exit(1)

    if "?" in db_url:
        db_url = db_url.split("?")[0]

    print("Connecting to database...")
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
    except Exception as e:
        print(f"Failed to connect: {e}")
        sys.exit(1)

    try:
        # 1. Create users table
        print("Creating users table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.users (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                username VARCHAR(255) UNIQUE NOT NULL,
                hashed_password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
            );
        """)

        # 2. Insert initial user
        print("Inserting initial user 'Om Ingle'...")
        hashed_pw = get_password_hash("om@ingle")
        cur.execute("""
            INSERT INTO public.users (username, hashed_password)
            VALUES (%s, %s)
            ON CONFLICT (username) DO NOTHING
            RETURNING id;
        """, ("Om Ingle", hashed_pw))
        
        row = cur.fetchone()
        if row:
            user_id = row[0]
            print(f"Created user with ID: {user_id}")
        else:
            cur.execute("SELECT id FROM public.users WHERE username = %s;", ("Om Ingle",))
            user_id = cur.fetchone()[0]
            print(f"User already exists. ID: {user_id}")

        # 3. Handle user_profiles and user_schedules legacy user_id columns
        print("Dropping legacy VARCHAR user_id columns...")
        cur.execute("ALTER TABLE public.user_schedules DROP CONSTRAINT IF EXISTS user_schedules_user_id_fkey;")
        cur.execute("ALTER TABLE public.user_profiles DROP COLUMN IF EXISTS user_id;")
        cur.execute("ALTER TABLE public.user_schedules DROP COLUMN IF EXISTS user_id;")

        # 4. Alter tables to add nullable user_id (UUID)
        tables_to_update = ['opportunities', 'sources', 'user_profiles', 'user_schedules']
        for table in tables_to_update:
            print(f"Adding user_id to {table} (nullable)...")
            cur.execute(f"""
                ALTER TABLE public.{table} 
                ADD COLUMN IF NOT EXISTS user_id UUID;
            """)

            # 5. UPDATE existing rows
            print(f"Updating existing rows in {table} to belong to Om Ingle...")
            cur.execute(f"""
                UPDATE public.{table}
                SET user_id = %s
                WHERE user_id IS NULL;
            """, (user_id,))

            # 6. Make user_id NOT NULL and add FK constraint
            print(f"Making user_id NOT NULL and adding FK in {table}...")
            try:
                cur.execute(f"""
                    ALTER TABLE public.{table}
                    ALTER COLUMN user_id SET NOT NULL;
                """)
            except Exception as e:
                print(f"Warning on NOT NULL constraint for {table}: {e}")
                conn.rollback()
                continue
                
            try:
                cur.execute(f"""
                    ALTER TABLE public.{table}
                    ADD CONSTRAINT {table}_user_id_fkey 
                    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;
                """)
            except psycopg2.errors.DuplicateObject:
                print(f"FK constraint already exists for {table}.")
                conn.rollback()
                continue

        conn.commit()
        print("\nMigration completed successfully!")

    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()

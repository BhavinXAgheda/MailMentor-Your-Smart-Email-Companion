import psycopg2
import os
import sys
from psycopg2 import sql
from dotenv import load_dotenv

# --- Load environment variables from .env file ---
load_dotenv()

# --- Configuration ---
DB_NAME = os.getenv("DB_NAME", "email_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "mysecretpassword")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5433")

# The dimension should match your embedding model output
VECTOR_DIMENSION = 384

def setup_database():
    """
    Connects to PostgreSQL, creates the database if it doesn't exist,
    enables the pgvector extension, and creates the necessary table.
    """
    try:
        # Step 1: Connect to the default 'postgres' database
        print(f"--- Step 1: Connecting to PostgreSQL server at {DB_HOST}:{DB_PORT} ---")
        conn = psycopg2.connect(
            dbname="postgres",
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        conn.autocommit = True
        cur = conn.cursor()
        print("✅ Connection to server successful.")

        # Step 2: Check if the target database exists; create if not
        print(f"--- Step 2: Checking for database '{DB_NAME}' ---")
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
        if not cur.fetchone():
            print(f"Database '{DB_NAME}' not found. Creating it now...")
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB_NAME)))
            print(f"✅ Database '{DB_NAME}' created successfully.")
        else:
            print(f"✅ Database '{DB_NAME}' already exists.")

        cur.close()
        conn.close()

        # Step 3: Connect to the target database
        print(f"--- Step 3: Connecting to '{DB_NAME}' database ---")
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cur = conn.cursor()
        print("✅ Connection to database successful.")

        # Step 4: Enable pgvector extension
        print("--- Step 4: Enabling 'vector' extension ---")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        print("✅ 'vector' extension enabled.")

        # Step 5: Create 'emails' table
        print("--- Step 5: Creating 'emails' table ---")
        table_creation_query = f"""
            CREATE TABLE IF NOT EXISTS emails (
                id SERIAL PRIMARY KEY,
                sender VARCHAR(255) NOT NULL,
                recipient VARCHAR(255) NOT NULL,
                subject TEXT,
                body TEXT,
                "timestamp" TIMESTAMPTZ DEFAULT NOW(),
                tags TEXT[],
                embedding VECTOR({VECTOR_DIMENSION})
            );
        """
        cur.execute(table_creation_query)
        print("✅ 'emails' table created or already exists.")

        conn.commit()
        print("\n🎉 Database setup complete! 🎉")

    except psycopg2.OperationalError as e:
        print("\n❌ CRITICAL ERROR: Could not connect to the database.", file=sys.stderr)
        print("   Please check the following:", file=sys.stderr)
        print("   1. Is your Docker container named 'postgres-db' running? (Check with 'docker ps')", file=sys.stderr)
        print(f"   2. Are the DB_HOST ('{DB_HOST}') and DB_PORT ('{DB_PORT}') correct?", file=sys.stderr)
        print("   3. Is the DB_PASSWORD correct?", file=sys.stderr)
        print(f"\n   Original error: {e}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

    finally:
        if 'conn' in locals() and conn:
            if 'cur' in locals() and cur:
                cur.close()
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    setup_database()

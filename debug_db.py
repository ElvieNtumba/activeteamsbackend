import os
from dotenv import load_dotenv
from supabase_helpers.supabase_client import supabase

load_dotenv()

DB_NAME = os.getenv("DB_NAME", "active-teams-db")

async def check_db(table_name):
    print(f"--- Table: {table_name} ---")
    result = supabase.table(table_name).select("id", count="exact").execute()
    count = getattr(result, "count", None)
    print(f"Count: {count}")
    if count and count > 0:
        sample = result.data[:10] if getattr(result, "data", None) else []
        print(f"Sample rows: {sample}")

async def main():
    await check_db("organizations")
    await check_db("users")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

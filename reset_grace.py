import os
from passlib.context import CryptContext
from dotenv import load_dotenv
from Backend.activeteamsbackend.supabase_helpers.supabase_connection import supabase

load_dotenv()
DB_NAME = os.getenv("DB_NAME", "active-teams-db")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def main():
    new_password = pwd_context.hash("test1234")
    result = supabase.table("Users").update({"password": new_password}).eq("email", "grace@test.com").execute()
    print(f"Updated user grace@test.com: {getattr(result, 'count', 'unknown')} rows")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
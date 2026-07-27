import os
from dotenv import load_dotenv
from Backend.activeteamsbackend.supabase_helpers.supabase_connection import supabase

load_dotenv()
DB_NAME = os.getenv("DB_NAME", "active-teams-db")

async def seed_organizations():
    print(f"Using Supabase DB: {DB_NAME}")

    test_orgs = [
        {"name": "Active Church", "tag": "Active Church"},
        {"name": "City Church", "tag": "City Church"},
        {"name": "Grace Chapel", "tag": "Grace Chapel"},
        {"name": "Victory Outreach", "tag": "Victory Outreach"},
        {"name": "New Life Fellowship", "tag": "New Life Fellowship"}
    ]

    existing_result = supabase.table("organizations").select("name").execute()
    existing_names = {row["name"] for row in (existing_result.data or [])}

    for org in test_orgs:
        if org["name"] in existing_names:
            print(f"  [.] Already exists: {org['name']}")
            continue
        supabase.table("organizations").insert(org).execute()
        print(f"  [+] Added: {org['name']}")
    print("Seeding complete!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(seed_organizations())

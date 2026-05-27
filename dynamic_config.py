import os
from datetime import datetime
from dotenv import load_dotenv
from supabase_helpers.supabase_client import supabase

load_dotenv()

DB_NAME = os.getenv("DB_NAME", "active-teams-db")

async def seed():
    print(f"Using Supabase project for DB_NAME: {DB_NAME}")
    print("Seeding OrgConfig...")
    result = supabase.table("OrgConfig").select("id").eq("id", "active-teams").execute()
    existing = result.data[0] if getattr(result, "data", None) else None
    if existing:
        print("Config for 'active-teams' already exists, skipping.")
        return
    config = {
        "id": "active-teams",
        "org_name": "Active Teams",
        "events_collection": "Events",
        "people_collection": "People",
        "recurring_event_type": "Cells",
        "hierarchy": [
            {"level": 1, "field": "leader1",   "label": "Leader @1"},
            {"level": 2, "field": "leader12",  "label": "Leader @12"},
            {"level": 3, "field": "leader144", "label": "Leader @144"}
        ],
        "top_leaders": {"male": "Gavin Enslin", "female": "Vicky Enslin"},
        "allows_create_event": True,
        "allows_create_event_type": True,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "created_by": "seed_script",
        "is_default": True
    }
    supabase.table("OrgConfig").insert(config).execute()
    print("Successfully seeded 'active-teams' config!")

async def main():
    try:
        await seed()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
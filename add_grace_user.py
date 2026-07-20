import os
from passlib.context import CryptContext
from datetime import datetime
from dotenv import load_dotenv
from Backend.activeteamsbackend.supabase_helpers.supabase_connection import supabase

load_dotenv()
DB_NAME = os.getenv("DB_NAME", "active-teams-db")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def main():
    grace_config = {
        "id": "grace-church",
        "org_name": "Grace Community Church",
        "recurring_event_type": "Zones",
        "hierarchy": [
            {"level": 1, "field": "zonePastor",          "label": "Zone Pastor"},
            {"level": 2, "field": "districtLeader",      "label": "District Leader"},
            {"level": 3, "field": "regionalCoordinator", "label": "Regional Coordinator"},
        ],
        "top_leaders": {"male": "Pastor Samuel Dube", "female": "Pastor Ruth Dube"},
        "allows_create_event": True,
        "allows_create_event_type": True,
    }
    supabase.table("OrgConfig").upsert(grace_config, on_conflict="id").execute()
    print("Grace church config added!")

    grace_user = {
        "email": "grace@test.com",
        "name": "Grace",
        "surname": "Test",
        "password": pwd_context.hash("test1234"),
        "role": "admin",
        "org_id": "grace-church",
        "created_at": datetime.utcnow().isoformat(),
    }
    supabase.table("Users").upsert(grace_user, on_conflict="email").execute()
    print("Grace test user added: grace@test.com / test1234")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
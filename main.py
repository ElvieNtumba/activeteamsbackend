import os
from datetime import datetime, timedelta
from typing import List, Optional
from bson import ObjectId
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from auth.models import Event, CheckIn, UncaptureRequest, UserCreate, UserLogin
from auth.utils import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_role,
)

# load env
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
JWT_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# FastAPI app
app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection using motor
client = AsyncIOMotorClient(MONGO_URI)
db = client["active-teams-db"]
events_collection = db["Events"]
people_collection = db["People"]
users_collection = db["Users"]


@app.get("/")
async def root():
    return {"message": "Server is running with MongoDB, Firebase, and AWS!"}


# -------------------------
# Signup (creates user + role)
# -------------------------
# http://localhost:8000/signup
'''
{
  "name": "Alice",
  "surname": "Smith",
  "date_of_birth": "1990-01-01",
  "home_address": "123 Main St",
  "invited_by": "Bob",
  "phone_number": "1234567890",
  "email": "alice@example.com",
  "gender": "female",
  "password": "StrongPass123"
}

'''
@app.post("/signup")
async def signup(user: UserCreate):
    existing = await users_collection.find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    
    role = getattr(user, "role", None) or "user"


    hashed = hash_password(user.password)
    user_dict = {
        "name": user.name,
        "surname": user.surname,
        "date_of_birth": user.date_of_birth,
        "home_address": user.home_address,
        "invited_by": user.invited_by,
        "phone_number": user.phone_number,
        "email": user.email,
        "gender": user.gender,
        "password": hashed,
        "role": role,
        "created_at": datetime.utcnow(),
    }
    await users_collection.insert_one(user_dict)
    return {"message": "User created successfully"}


# -------------------------
# Login (returns JWT)
# -------------------------
# http://localhost:8000/login
'''
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
'''
@app.post("/login")
async def login(user: UserLogin):
    existing = await users_collection.find_one({"email": user.email})
    if not existing or not verify_password(user.password, existing["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token_expires = timedelta(minutes=JWT_EXPIRE_MINUTES)
    token = create_access_token(
        {"user_id": str(existing["_id"]), "email": existing["email"], "role": existing.get("role", "registrant")},
        expires_delta=token_expires
    )
    return {"access_token": token, "token_type": "bearer"}


# -------------------------
# Create Event (admin only)
# -------------------------
# http://localhost:8000/events
'''
{
  "eventType": "Sunday Service",
  "service_name": "Morning Worship",
  "date": "2025-08-10T09:00:00",
  "location": "Main Hall"
}
'''
@app.post("/events", dependencies=[Depends(require_role("admin"))])
async def create_event(event: Event, current=Depends(get_current_user)):
    try:
        event_data = event.dict()
        # ensure date stored as datetime
        try:
            event_data["date"] = datetime.fromisoformat(event_data["date"])
        except Exception:
            # fallback: try parsing naive formats
            event_data["date"] = datetime.utcnow()

        if "attendees" not in event_data or event_data["attendees"] is None:
            event_data["attendees"] = []
        # store who created the event
        event_data["created_by"] = current.get("user_id")
        event_data["created_at"] = datetime.utcnow()
        result = await events_collection.insert_one(event_data)
        return {"message": "Event created", "id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# Search People
# -------------------------
#  http://localhost:8000/people/search?name=Bob
@app.get("/people/search")
async def search_people(name: str = Query(..., min_length=1)):
    try:
        cursor = people_collection.find({"Name": {"$regex": name, "$options": "i"}}).limit(50)
        people = []
        async for p in cursor:
            people.append({"_id": str(p["_id"]), "Name": p["Name"]})
        return {"results": people}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# Check-in (registrant or admin)
# -------------------------
# http://localhost:8000/checkin
'''
{
  "event_id": "6895d097294fa98f5ef2a6f1",
  "name": "keren botombe"
}
'''
@app.post("/checkin", dependencies=[Depends(require_role("registrant", "admin"))])
async def check_in_person(checkin: CheckIn):
    try:
        event = await events_collection.find_one({"_id": ObjectId(checkin.event_id)})
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        person = await people_collection.find_one({"Name": {"$regex": f"^{checkin.name}$", "$options": "i"}})
        if not person:
            raise HTTPException(status_code=400, detail="Person not found in people database")

        already_checked = any(a.get("name", "").lower() == checkin.name.lower() for a in event.get("attendees", []))
        if already_checked:
            raise HTTPException(status_code=400, detail="Person already checked in")

        await events_collection.update_one(
            {"_id": ObjectId(checkin.event_id)},
            {
                "$push": {"attendees": {"name": checkin.name, "time": datetime.utcnow()}},
                "$inc": {"total_attendance": 1}
            }
        )
        return {"message": f"{checkin.name} checked in successfully."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# View Check-ins (any authenticated user)
# -------------------------
# http://localhost:8000/checkins/6895d097294fa98f5ef2a6f1
'''
{
  "event_id": "6895d097294fa98f5ef2a6f1",
  "name": "keren botombe"
}
'''
@app.get("/checkins/{event_id}")
async def get_checkins(event_id: str, dependencies=[Depends(require_role("registrant", "admin"))]):
    try:
        event = await events_collection.find_one({"_id": ObjectId(event_id)})
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        return {
            "event_id": event_id,
            "service_name": event.get("service_name"),
            "attendees": event.get("attendees", []),
            "total_attendance": event.get("total_attendance", 0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# Uncapture (registrant or admin)
# -------------------------
# http://localhost:8000/uncapture
'''
{
  "event_id": "6895d097294fa98f5ef2a6f1",
  "name": "keren botombe"
}
'''
@app.post("/uncapture", dependencies=[Depends(require_role("registrant", "admin"))])
async def uncapture_person(data: UncaptureRequest):
    try:
        update_result = await events_collection.update_one(
            {"_id": ObjectId(data.event_id)},
            {
                "$pull": {"attendees": {"name": data.name}},
                "$inc": {"total_attendance": -1}
            }
        )
        if update_result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Person not found or already removed")

        return {"message": f"{data.name} removed from check-ins."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# Helper: list events (auth required)
# -------------------------
# http://localhost:8000/events
@app.get("/events")
async def list_events(skip: int = 0, limit: int = 50, current=Depends(get_current_user)):
    try:
        role = current.get("role")
        user_id = current.get("user_id")
        if role == "admin":
            cursor = events_collection.find({}).skip(skip).limit(limit)
        elif role == "user":
            # filter by assigned_to (if you prefer another field, adjust accordingly)
            cursor = events_collection.find({"assigned_to": current.get("email")}).skip(skip).limit(limit)
        else:  # registrant
            cursor = events_collection.find({}).skip(skip).limit(limit)

        events = []
        async for e in cursor:
            events.append({
                "id": str(e["_id"]),
                "service_name": e.get("service_name"),
                "date": e.get("date").isoformat() if isinstance(e.get("date"), datetime) else e.get("date"),
                "location": e.get("location"),
                "total_attendance": e.get("total_attendance", 0)
            })
        return {"results": events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# Get single event (auth required)
# -------------------------
# http://localhost:8000/events/6890bf91f79bc29a6d3ae8f0
@app.get("/events/{event_id}")
async def get_event(event_id: str, current=Depends(get_current_user)):
    try:
        event = await events_collection.find_one({"_id": ObjectId(event_id)})
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        return {
            "id": str(event["_id"]),
            "service_name": event.get("service_name"),
            "date": event.get("date").isoformat() if isinstance(event.get("date"), datetime) else event.get("date"),
            "location": event.get("location"),
            "attendees": event.get("attendees", []),
            "total_attendance": event.get("total_attendance", 0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

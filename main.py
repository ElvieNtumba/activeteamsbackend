import os
from datetime import datetime
from bson import ObjectId
from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from auth.models import Event, CheckIn, UncaptureRequest, UserCreate, UserLogin
from auth.utils import hash_password, verify_password
import math

# Load .env variables
load_dotenv()

# FastAPI app
app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI")
client = AsyncIOMotorClient(MONGO_URI)
db = client["active-teams-db"]
events_collection = db["Events"]
people_collection = db["People"]

def sanitize_document(doc):
    """Recursively sanitize document to replace NaN/Infinity float values with None."""
    for k, v in doc.items():
        if isinstance(v, float):
            if math.isnan(v) or math.isinf(v):
                doc[k] = None
        elif isinstance(v, dict):
            sanitize_document(v)
        elif isinstance(v, list):
            for i in range(len(v)):
                if isinstance(v[i], dict):
                    sanitize_document(v[i])
                elif isinstance(v[i], float) and (math.isnan(v[i]) or math.isinf(v[i])):
                    v[i] = None
    return doc

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Server is running with MongoDB, Firebase, and AWS!"}

# Signup
@app.post("/signup")
async def signup(user: UserCreate):
    existing = await db["Users"].find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
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
        "confirm_password": hashed
    }
    await db["Users"].insert_one(user_dict)
    return {"message": "User created successfully"}

# Login
@app.post("/login")
async def login(user: UserLogin):
    existing = await db["Users"].find_one({"email": user.email})
    if not existing or not verify_password(user.password, existing["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {"message": "Login successful"}


# Create Event
@app.post("/events")
async def create_event(event: Event):
    try:
        event_data = event.dict()
        event_data["date"] = datetime.fromisoformat(event_data["date"])
        if "attendees" not in event_data:
            event_data["attendees"] = []
        result = await events_collection.insert_one(event_data)
        return {"message": "Event created", "id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Search People by Name (case-insensitive regex)
@app.get("/people/search")
async def search_people(name: str = Query(..., min_length=1)):
    try:
        cursor = people_collection.find({"Name": {"$regex": name, "$options": "i"}})
        people = []
        async for p in cursor:
            p["_id"] = str(p["_id"])
            p = sanitize_document(p)
            people.append({"_id": p["_id"], "Name": p["Name"]})
        return {"results": people}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Check-in to Event
@app.post("/checkin")
async def check_in_person(checkin: CheckIn):
    try:
        event = await events_collection.find_one({"_id": ObjectId(checkin.event_id)})
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        person = await people_collection.find_one({"Name": {"$regex": f"^{checkin.name}$", "$options": "i"}})
        if not person:
            raise HTTPException(status_code=400, detail="Person not found in people database")

        already_checked = any(a["name"].lower() == checkin.name.lower() for a in event.get("attendees", []))
        if already_checked:
            raise HTTPException(status_code=400, detail="Person already checked in")

        await events_collection.update_one(
            {"_id": ObjectId(checkin.event_id)},
            {
                "$push": {"attendees": {"name": checkin.name, "time": datetime.now()}},
                "$inc": {"total_attendance": 1}
            }
        )
        return {"message": f"{checkin.name} checked in successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Get Check-ins for Event
@app.get("/checkins/{event_id}")
async def get_checkins(event_id: str):
    try:
        event = await events_collection.find_one({"_id": ObjectId(event_id)})
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        event = sanitize_document(event)
        return {
            "event_id": event_id,
            "service_name": event.get("service_name"),
            "attendees": event.get("attendees", []),
            "total_attendance": event.get("total_attendance", 0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Uncapture (Remove Check-in)
@app.post("/uncapture")
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

# Get People with filtering and pagination
@app.get("/people")
async def get_people(
    page: int = Query(1, ge=1),
    perPage: int = Query(100, ge=1, le=500),
    name: str = None,
    gender: str = None,
    dob: str = None,
    location: str = None,
    leader: str = None,
    stage: str = None
):
    try:
        skip = (page - 1) * perPage
        query = {}

        if name:
            query["Name"] = {"$regex": name, "$options": "i"}
        if gender:
            query["Gender"] = {"$regex": gender, "$options": "i"}
        if dob:
            query["DateOfBirth"] = dob
        if location:
            query["Location"] = {"$regex": location, "$options": "i"}
        if leader:
            query["Leader"] = {"$regex": leader, "$options": "i"}
        if stage:
            query["Stage"] = {"$regex": stage, "$options": "i"}

        cursor = people_collection.find(query).skip(skip).limit(perPage)
        people_list = []
        async for person in cursor:
            person["_id"] = str(person["_id"])
            person = sanitize_document(person)
            people_list.append(person)

        total_count = await people_collection.count_documents(query)
        return {
            "page": page,
            "perPage": perPage,
            "total": total_count,
            "results": people_list
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# GET /people/:id
@app.get("/people/{person_id}")
async def get_person_by_id(person_id: str):
    try:
        person = await people_collection.find_one({"_id": ObjectId(person_id)})
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")
        person["_id"] = str(person["_id"])
        person = sanitize_document(person)
        return person
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# POST /people (Create or Update)
@app.post("/people")
async def create_or_update_person(person_data: dict = Body(...)):
    try:
        if "_id" in person_data:  # Update existing person
            person_id = person_data["_id"]
            del person_data["_id"]
            result = await people_collection.update_one(
                {"_id": ObjectId(person_id)},
                {"$set": person_data}
            )
            if result.modified_count == 0:
                raise HTTPException(status_code=404, detail="Person not found or no changes made")
            return {"message": "Person updated successfully"}
        else:  # Create new person
            result = await people_collection.insert_one(person_data)
            return {"message": "Person created successfully", "id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# DELETE /people/:id or /person/:id
@app.delete("/people/{person_id}")
@app.delete("/person/{person_id}")
async def delete_person(person_id: str):
    try:
        result = await people_collection.delete_one({"_id": ObjectId(person_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Person not found")
        return {"message": "Person deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

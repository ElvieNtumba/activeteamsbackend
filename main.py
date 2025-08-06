# # import pandas as pd
# from pymongo import MongoClient
# from datetime import datetime

# This just uploads the spreadsheet named active teams
# try:
#     df = pd.read_excel("active_teams_test.xlsx")
#     client = MongoClient("mongodb+srv://activeteams:helloactiveteams@active-teams.ykghvqr.mongodb.net/")
#     db = client["active-teams-db"]
#     collection = db["People"]

#     records = df.to_dict("rqecords")
#     result = collection.insert_many(records)
#     print(f"{len(result.inserted_ids)} members uploaded successfully.")
# except errors.PyMongoError as e:
#     print(f"Error connecting or inserting to MongoDB: {e}")
# except Exception as e:
#     print(f"Unexpected error: {e}")

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from pymongo import MongoClient
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
from bson import ObjectId


app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB Connection
client = MongoClient("mongodb+srv://activeteams:helloactiveteams@active-teams.ykghvqr.mongodb.net/")
db = client["active-teams-db"]
collection = db["Events"]
people_collection = db["People"]


# Pydantic Model
class Event(BaseModel):
    eventType: str
    service_name: str
    date: str  # keep as str for simplicity, convert later
    location: str
    total_attendance: int = 0
    attendees: list[dict] = []  # list of {"name": ..., "time": ...}

# This workksss
@app.post("/events")
def create_event(event: Event):
    try:
        event_data = event.dict()
        event_data["date"] = datetime.fromisoformat(event_data["date"])
        if "attendees" not in event_data:
            event_data["attendees"] = []
        result = collection.insert_one(event_data)
        return {"message": "Event created", "id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

#ths workkss
@app.get("/people/search")
def search_people(name: str = Query(..., min_length=1)):
    try:
        # Case-insensitive regex search for names starting with or containing the query
        cursor = people_collection.find({"Name": {"$regex": name, "$options": "i"}})
        people = [{"_id": str(p["_id"]), "Name": p["Name"]} for p in cursor]
        return {"results": people}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Check-in model
class CheckIn(BaseModel):
    event_id: str
    name: str

# This worrrkksssss
@app.post("/checkin")
def check_in_person(checkin: CheckIn):
    try:
        # Check if event exists
        event = collection.find_one({"_id": ObjectId(checkin.event_id)})
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        
        # Check if person exists in people collection
        person = people_collection.find_one({"Name": {"$regex": f"^{checkin.name}$", "$options": "i"}})
        if not person:
            raise HTTPException(status_code=400, detail="Person not found in people database")

        # Check if already checked in
        if any(a["name"].lower() == checkin.name.lower() for a in event.get("attendees", [])):
            raise HTTPException(status_code=400, detail="Person already checked in")

        # Add to event attendees
        result = collection.update_one(
            {"_id": ObjectId(checkin.event_id)},
            {
                "$push": {"attendees": {"name": checkin.name, "time": datetime.now()}},
                "$inc": {"total_attendance": 1}
            }
        )
        return {"message": f"{checkin.name} checked in successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# View check-ins for an event
# This worrrkksssss
@app.get("/checkins/{event_id}")
def get_checkins(event_id: str):
    try:
        event = collection.find_one({"_id": ObjectId(event_id)})
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        return {
            "event_id": event_id,
            "service_name": event["service_name"],
            "attendees": event.get("attendees", []),
            "total_attendance": event.get("total_attendance", 0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Uncapture (remove) a person from an event
class UncaptureRequest(BaseModel):
    event_id: str
    name: str

# This woorrrkkkss
@app.post("/uncapture")
def uncapture_person(data: UncaptureRequest):
    try:
        result = collection.update_one(
            {"_id": ObjectId(data.event_id)},
            {
                "$pull": {"attendees": {"name": data.name}},
                "$inc": {"total_attendance": -1}
            }
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Person not found or already removed")

        return {"message": f"{data.name} removed from check-ins."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


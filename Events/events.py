from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from bson import ObjectId
from typing import Optional
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# MongoDB connection
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
client = MongoClient(MONGO_URL)
db = client["active-teams-db"]
events_collection = db.Events  

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def serialize_event(event):
    """Convert MongoDB document to JSON format"""
    if event:
        event["id"] = str(event["_id"])
        del event["_id"]
    return event

# ---------------- Existing Endpoints ---------------- #

@app.get("/events")
async def get_events(
    category: Optional[str] = Query(None),
    event_types: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    is_ticketed: Optional[bool] = Query(None)
):
    try:
        query = {}
        filter_category = category or event_types
        if filter_category:
            if "," in filter_category:
                categories = [cat.strip() for cat in filter_category.split(",")]
                query["category"] = {"$in": categories}
            else:
                query["category"] = filter_category

        if search:
            query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"location": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}}
            ]

        if is_ticketed is not None:
            query["is_ticketed"] = is_ticketed

        events = list(events_collection.find(query))
        return [serialize_event(event) for event in events]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/events/{event_id}")
async def get_single_event(event_id: str):
    try:
        if not ObjectId.is_valid(event_id):
            raise HTTPException(status_code=400, detail="Invalid event ID")
        event = events_collection.find_one({"_id": ObjectId(event_id)})
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        return serialize_event(event)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/")
async def root():
    return {"message": "Church Events API", "status": "running"}

@app.get("/test-db")
async def test_database():
    try:
        db.command('ping')
        total_events = events_collection.count_documents({})
        sample_events = list(events_collection.find().limit(3))
        categories = events_collection.distinct("category")
        return {
            "database_status": "connected",
            "total_events": total_events,
            "available_categories": categories,
            "sample_events": [serialize_event(event) for event in sample_events]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

# ---------------- New Endpoints ---------------- #

@app.post("/events")
async def create_event(event: dict = Body(...)):
    """Create a new event"""
    try:
        # If no date provided, add current datetime
        if "date" not in event:
            event["date"] = datetime.now()
        result = events_collection.insert_one(event)
        new_event = events_collection.find_one({"_id": result.inserted_id})
        return serialize_event(new_event)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not create event: {str(e)}")

@app.put("/events/{event_id}")
async def update_event(event_id: str, updates: dict = Body(...)):
    """Update an event by ID"""
    try:
        if not ObjectId.is_valid(event_id):
            raise HTTPException(status_code=400, detail="Invalid event ID")
        result = events_collection.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": updates}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Event not found")
        updated_event = events_collection.find_one({"_id": ObjectId(event_id)})
        return serialize_event(updated_event)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not update event: {str(e)}")

@app.delete("/events/{event_id}")
async def delete_event(event_id: str):
    """Delete an event by ID"""
    try:
        if not ObjectId.is_valid(event_id):
            raise HTTPException(status_code=400, detail="Invalid event ID")
        result = events_collection.delete_one({"_id": ObjectId(event_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Event not found")
        return {"message": f"Event {event_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not delete event: {str(e)}")

# ---------------- Run ---------------- #
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)

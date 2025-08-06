from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from bson import ObjectId
from typing import Optional, List
import os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()


# MongoDB connection
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
client = MongoClient(MONGO_URL)
db = client.active-teams-db 
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

@app.get("/events")
async def get_events(
    category: Optional[str] = Query(None, description="Filter by event category"),
    event_types: Optional[str] = Query(None, description="Filter by event types (same as category)"),
    search: Optional[str] = Query(None, description="Search in title or location"),
    is_ticketed: Optional[bool] = Query(None, description="Filter by ticketed events")
):
    """
    Get events from MongoDB with filtering options
    Supports both 'category' and 'event_types' parameters for compatibility
    """
    try:
        # Build MongoDB query
        query = {}
        
        # Handle category filtering (support both 'category' and 'event_types' params)
        filter_category = category or event_types
        if filter_category:
            # Handle multiple categories separated by comma
            if "," in filter_category:
                categories = [cat.strip() for cat in filter_category.split(",")]
                query["category"] = {"$in": categories}
            else:
                query["category"] = filter_category
        
        # Handle search
        if search:
            query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"location": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}}
            ]
        
        # Handle ticketed filter
        if is_ticketed is not None:
            query["is_ticketed"] = is_ticketed
        
        print(f"MongoDB Query: {query}")  # Debug print
        
        # Fetch events from MongoDB
        events_cursor = events_collection.find(query)
        events = list(events_cursor)
        
        print(f"Found {len(events)} events")  # Debug print
        
        # Convert ObjectId to string for JSON serialization
        serialized_events = [serialize_event(event) for event in events]
        
        return serialized_events
        
    except Exception as e:
        print(f"Error: {str(e)}")  # Debug print
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/events/{event_id}")
async def get_single_event(event_id: str):
    """Get a single event by ID"""
    try:
        if not ObjectId.is_valid(event_id):
            raise HTTPException(status_code=400, detail="Invalid event ID")
        
        event = events_collection.find_one({"_id": ObjectId(event_id)})
        
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        
        return serialize_event(event)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Church Events API", "status": "running"}

@app.get("/test-db")
async def test_database():
    """Test MongoDB connection and show sample data"""
    try:
        # Test connection
        db.command('ping')
        
        # Count total events
        total_events = events_collection.count_documents({})
        
        # Get sample events
        sample_events = list(events_collection.find().limit(3))
        serialized_samples = [serialize_event(event) for event in sample_events]
        
        # Get unique categories
        categories = events_collection.distinct("category")
        
        return {
            "database_status": "connected",
            "total_events": total_events,
            "available_categories": categories,
            "sample_events": serialized_samples
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)
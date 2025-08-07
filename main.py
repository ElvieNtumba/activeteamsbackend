import os
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient , AsyncIOMotorDatabase
from typing import List
from datetime import datetime
from pydantic import BaseModel, Field

from tasks import (
    get_tasks,
    post_task,
    get_tasks_by_day,
    get_tasks_last_7_days,
    get_tasks_this_week,
    get_tasks_previous_month
)

# Load .env variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Connect to MongoDB

MONGO_URI = os.getenv("MONGO_URI")
client = AsyncIOMotorClient(MONGO_URI)
db = client["active-teams-db"]

def get_db():
    return db

# ----------------- Pydantic Models -----------------
class ContactedPerson(BaseModel):
    name: str
    phone: str
    notes: str = ""

class TaskCreate(BaseModel):
    member_id: str = Field(..., alias="memberID")
    member_name: str = Field(..., alias="name")
    contacted_person: ContactedPerson
    followup_date: datetime
    status: str = "Pending"

# ----------------- API Endpoints -----------------

@app.get("/tasks", summary="Get all Calling/Visiting/Pending tasks")
async def fetch_tasks(db: AsyncIOMotorDatabase = Depends(get_db)):
    return await get_tasks(db)

@app.post("/tasks", summary="Create a new task")
async def create_task(task: TaskCreate, db: AsyncIOMotorDatabase = Depends(get_db)):
    task_id = await post_task(
        db,
        task.member_id,
        task.member_name,
        task.contacted_person.dict(),
        task.followup_date,
        task.status
    )
    return {"inserted_id": task_id}

@app.on_event("startup")
async def startup_event():
    app.mongodb = db

# Routes

@app.get("/tasks/day/{date}", summary="Get tasks by specific date (YYYY-MM-DD)")
async def tasks_by_day(date: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Date must be in format YYYY-MM-DD")
    return await get_tasks_by_day(db, parsed_date)

@app.get("/tasks/last-7-days", summary="Get tasks from the last 7 days")
async def tasks_last_7_days(db: AsyncIOMotorDatabase = Depends(get_db)):
    return await get_tasks_last_7_days(db)

@app.get("/tasks/this-week", summary="Get tasks from Monday to now")
async def tasks_this_week(db: AsyncIOMotorDatabase = Depends(get_db)):
    return await get_tasks_this_week(db)

@app.get("/tasks/previous-month", summary="Get tasks from previous month")
async def tasks_previous_month(db: AsyncIOMotorDatabase = Depends(get_db)):
    return await get_tasks_previous_month(db)

@app.get("/")
async def root():
    return {"message": "Server is running with MongoDB, Firebase, and AWS!"}

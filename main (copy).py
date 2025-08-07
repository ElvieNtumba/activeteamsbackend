import os
from fastapi import FastAPI, Request , APIRouter , HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient , AsyncIOMotorDatabase
from typing import Optional, List
from bson import ObjectId
from db.mongo import db
from pydantic import BaseModel, Field
from datetime import datetime

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

router = APIRouter()

# ----------------- Pydantic Models -----------------

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    due_date: Optional[str] = None  # Format: YYYY-MM-DD
    status: Optional[str] = "Pending"  # Default to Pending


class TaskResponse(TaskCreate):
    id: str

# ----------------- API Endpoints -----------------

@router.post("/tasks", response_model=dict)
async def create_task(task: TaskCreate):
    task_dict = {
        "title": task.title,
        "description": task.description,
        "assigned_to": task.assigned_to,
        "due_date": task.due_date,
        "status": task.status,
        "created_at": datetime.utcnow()
    }

    result = await db["Tasks"].insert_one(task_dict)

    if result.inserted_id:
        return {"message": "Task created successfully", "task_id": str(result.inserted_id)}
    else:
        raise HTTPException(status_code=500, detail="Failed to create task")


@router.get("/tasks", response_model=List[TaskResponse])
async def get_tasks():
    tasks_cursor = db["Tasks"].find()
    tasks = []

    async for task in tasks_cursor:
        tasks.append(TaskResponse(
            id=str(task["_id"]),
            title=task["title"],
            description=task.get("description"),
            assigned_to=task.get("assigned_to"),
            due_date=task.get("due_date"),
            status=task.get("status")
        ))

    return tasks


@app.get("/")
async def root():
    return {"message": "Server is running with MongoDB, Firebase, and AWS!"}

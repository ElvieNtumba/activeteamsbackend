import os
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from auth.routes import router as auth_router
from motor.motor_asyncio import AsyncIOMotorClient

# Load .env variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect to MongoDB

MONGODB_URI = os.getenv("MONGODB_URI")
client = AsyncIOMotorClient(MONGODB_URI)
db = client["active-teams-db"]
users_collection = db["Users"]



@app.on_event("startup")
async def startup_event():
    app.mongodb = db

# Include auth routes
app.include_router(auth_router)


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

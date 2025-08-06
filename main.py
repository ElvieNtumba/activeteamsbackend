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

MONGO_URI = os.getenv("MONGO_URI")
client = AsyncIOMotorClient(MONGO_URI)
db = client["active-teams-backend"]


@app.on_event("startup")
async def startup_event():
    app.mongodb = db

# Include auth routes
app.include_router(auth_router)


# Routes
@app.get("/")
async def root():
    return {"message": "Server is running with MongoDB, Firebase, and AWS!"}

import os
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Load .env variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Connect to MongoDB

MONGO_URI = os.getenv("MONGO_URI")
client = AsyncIOMotorClient(MONGO_URI)
db = client["activeteams"]

# Routes
@app.get("/")
async def root():
    return {"message": "Server is running with MongoDB, Firebase, and AWS!"}

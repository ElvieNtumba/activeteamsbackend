import os
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import motor.motor_asyncio
import firebase_admin
from firebase_admin import credentials, auth
import boto3

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
client = motor.motor_asyncio.AsyncIOMotorClient(os.getenv("MONGO_URI"))
db = client.get_default_database()

# Initialize Firebase Admin SDK
cred = credentials.Certificate("firebaseServiceAccountKey.json")
firebase_admin.initialize_app(cred)

# AWS SDK Setup (S3)
s3 = boto3.client(
    's3',
    region_name=os.getenv("AWS_REGION"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("AWS_SECRET_KEY"),
)

# Firebase Token Verifier
async def verify_firebase_token(request: Request):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = auth_header.split("Bearer ")[1]
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception:
        raise HTTPException(status_code=403, detail="Unauthorized")

# Routes
@app.get("/")
async def root():
    return {"message": "Server is running with MongoDB, Firebase, and AWS!"}

@app.get("/protected")
async def protected(user=Depends(verify_firebase_token)):
    return {"message": "You are verified via Firebase!", "user": user}
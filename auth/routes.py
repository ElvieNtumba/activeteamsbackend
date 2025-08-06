from fastapi import APIRouter, HTTPException
from auth.models import UserCreate, UserLogin
from auth.utils import hash_password, verify_password, create_access_token
from bson.objectid import ObjectId
from main import db  # use db from main.py

router = APIRouter()

@router.post("/signup")
async def signup(user: UserCreate):
    existing = await db["users"].find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed = hash_password(user.password)
    user_dict = {"email": user.email, "password": hashed}
    await db["users"].insert_one(user_dict)
    return {"message": "User created successfully"}

@router.post("/login")
async def login(user: UserLogin):
    existing = await db["users"].find_one({"email": user.email})
    if not existing or not verify_password(user.password, existing["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"user_id": str(existing["_id"])})
    return {"access_token": token, "token_type": "bearer"}

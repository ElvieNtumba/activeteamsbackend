from pydantic import BaseModel, EmailStr
from typing import Optional

# User creation model with role
class UserCreate(BaseModel):
    name: str
    surname: str
    date_of_birth: str
    home_address: str
    invited_by: str
    phone_number: str
    email: EmailStr
    gender: str
    password: str
    role: Optional[str] = None  # Optional role; default to 'user' in signup logic

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Event(BaseModel):
    eventType: str
    service_name: str
    date: str 
    location: str
    total_attendance: int = 0
    attendees: list[dict] = []

class CheckIn(BaseModel):
    event_id: str
    name: str

class UncaptureRequest(BaseModel):
    event_id: str
    name: str

# Authentication models
class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None

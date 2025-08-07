from pydantic import BaseModel, EmailStr

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

# # tasks.py

# from typing import List
# from motor.motor_asyncio import AsyncIOMotorDatabase
# from bson import ObjectId
# from datetime import datetime, timedelta
# import calendar

# # Utility: Convert ObjectId to string
# def format_task(task):
#     task["_id"] = str(task["_id"])
#     return task

# # Get all calling and visiting tasks
# async def get_tasks(db: AsyncIOMotorDatabase) -> List[dict]:
#     cursor = db.tasks.find({"status": {"$in": ["Calling", "Visiting", "Pending"]}})
#     return [format_task(task) async for task in cursor]

# # Post a new calling or visiting task
# async def post_task(
#     db: AsyncIOMotorDatabase,
#     member_id: str,
#     member_name: str,
#     contacted_person: dict,
#     followup_date: datetime,
#     status: str = "Pending"
# ) -> str:
#     task = {
#         "memberID": member_id,
#         "name": member_name,
#         "contacted_person": contacted_person,
#         "followup_date": followup_date,
#         "status": status
#     }
#     result = await db.tasks.insert_one(task)
#     return str(result.inserted_id)

# # Get tasks for a specific day (YYYY-MM-DD)
# async def get_tasks_by_day(db: AsyncIOMotorDatabase, date: datetime) -> List[dict]:
#     start = datetime(date.year, date.month, date.day)
#     end = start + timedelta(days=1)
#     cursor = db.tasks.find({"followup_date": {"$gte": start, "$lt": end}})
#     return [format_task(task) async for task in cursor]

# # Get tasks from previous 7 days
# async def get_tasks_last_7_days(db: AsyncIOMotorDatabase) -> List[dict]:
#     end = datetime.utcnow()
#     start = end - timedelta(days=7)
#     cursor = db.tasks.find({"followup_date": {"$gte": start, "$lt": end}})
#     return [format_task(task) async for task in cursor]

# # Get tasks for this week (Monday to today)
# async def get_tasks_this_week(db: AsyncIOMotorDatabase) -> List[dict]:
#     now = datetime.utcnow()
#     start_of_week = now - timedelta(days=now.weekday())  # Monday
#     start = datetime(start_of_week.year, start_of_week.month, start_of_week.day)
#     cursor = db.tasks.find({"followup_date": {"$gte": start, "$lt": now}})
#     return [format_task(task) async for task in cursor]

# # Get tasks from the previous month
# async def get_tasks_previous_month(db: AsyncIOMotorDatabase) -> List[dict]:
#     now = datetime.utcnow()
#     first_day_this_month = datetime(now.year, now.month, 1)
#     last_month = first_day_this_month - timedelta(days=1)
#     start = datetime(last_month.year, last_month.month, 1)
#     last_day = calendar.monthrange(last_month.year, last_month.month)[1]
#     end = datetime(last_month.year, last_month.month, last_day, 23, 59, 59)

#     cursor = db.tasks.find({"followup_date": {"$gte": start, "$lte": end}})
#     return [format_task(task) async for task in cursor]

from fastapi import APIRouter, HTTPException
from datetime import datetime
from typing import List

from bson.objectid import ObjectId
from db.mongo import db  # same as in your auth routes
from tasks.models import TaskCreate
from tasks.logic import (
    get_tasks,
    post_task,
    get_tasks_by_day,
    get_tasks_last_7_days,
    get_tasks_this_week,
    get_tasks_previous_month
)

router = APIRouter()

@router.get("/tasks")
async def fetch_tasks():
    return await get_tasks(db)

@router.post("/tasks")
async def create_task(task: TaskCreate):
    task_id = await post_task(
        db,
        task.member_id,
        task.member_name,
        task.contacted_person.dict(),
        task.followup_date,
        task.status
    )
    return {"inserted_id": task_id}

@router.get("/tasks/day/{date}")
async def tasks_by_day(date: str):
    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    return await get_tasks_by_day(db, parsed_date)

@router.get("/tasks/last-7-days")
async def tasks_last_7_days():
    return await get_tasks_last_7_days(db)

@router.get("/tasks/this-week")
async def tasks_this_week():
    return await get_tasks_this_week(db)

@router.get("/tasks/previous-month")
async def tasks_previous_month():
    return await get_tasks_previous_month(db)

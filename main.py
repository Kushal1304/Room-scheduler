from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime,timedelta


client = MongoClient("mongodb+srv://krinasoni2603_db_user:5Hnx5iqR55aOqcBr@cluster0.ao5cmqe.mongodb.net/?appName=Cluster0")
db = client["A1-3198101"]  

rooms_collection = db["rooms"]
days_collection = db["days"]
bookings_collection = db["bookings"]

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/templete", StaticFiles(directory="templete"), name="templete")

@app.get("/")
def serve_login():
    return FileResponse("templete/index.html")

@app.get("/dashboard")
def serve_dashboard():
    return FileResponse("templete/dashboard.html")


@app.get("/protected")
def protected_route(Authorization: str = Header(None)):
    if not Authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return {"message": "User is authenticated (token received)"}

@app.post("/add-room")
def add_room(room: dict):
    existing = rooms_collection.find_one({"name": room["name"]})
    if existing:
        return {"error": "Room already exists"}

    rooms_collection.insert_one({
        "name": room["name"],
        "user_email": room["user_email"]
    })

    return {"message": "Room added"}

@app.get("/rooms")
def get_rooms():
    rooms = []
    for room in rooms_collection.find():
        room["_id"] = str(room["_id"])
        rooms.append(room)
    return rooms


@app.post("/add-booking")
def add_booking(booking: dict):

    time_str = booking["time"]
    time_obj = datetime.strptime(time_str, "%H:%M").time()

    if time_obj < datetime.strptime("09:00", "%H:%M").time() or time_obj > datetime.strptime("18:00", "%H:%M").time():
        return {"error": "Booking allowed only between 09:00 and 18:00"}

    room = rooms_collection.find_one({"_id": ObjectId(booking["room_id"])})
    

    existing = bookings_collection.find_one({
        "room_id": booking["room_id"],
        "day_id": booking["day_id"],
        "time": booking["time"]
    })

    bookings_for_day = list(bookings_collection.find({
        "room_id": booking["room_id"],
        "day_id": booking["day_id"]
    }))

    if len(bookings_for_day) >= 9:
        return {"error": "All time slots are fully booked for this day"}
    
    if existing:
        return {"error": "Time slot already booked"}

    bookings_collection.insert_one({
        "room_id": booking["room_id"],
        "room_name": room["name"], 
        "day_id": booking["day_id"],
        "time": booking["time"],
        "user_email": booking["user_email"]
    })

    return {"message": "Booking added"}

@app.get("/bookings")
def get_bookings():
    bookings = []
    for b in bookings_collection.find():
        b["_id"] = str(b["_id"])
        bookings.append(b)
    return bookings

@app.delete("/delete-booking/{id}")
def delete_booking(id: str, email: str):

    booking = bookings_collection.find_one({"_id": ObjectId(id)})

    if not booking:
        return {"error": "Booking not found"}

    if booking.get("user_email") != email:
        return {"error": "You can only delete your own booking"}

    bookings_collection.delete_one({"_id": ObjectId(id)})

    return {"message": "Deleted"}

@app.get("/edit-booking")
def edit_booking_page():
    return FileResponse("templete/edit-booking.html")

from datetime import datetime

@app.put("/update-booking/{id}")
def update_booking(id: str, data: dict, email: str):

    booking = bookings_collection.find_one({"_id": ObjectId(id)})

    if booking.get("user_email") != email:
        return {"error": "You can only edit your own booking"}

    booking_date = datetime.strptime(data["day_id"], "%Y-%m-%d").date()
    today = datetime.today().date()

    if booking_date < today:
        return {"error": "Cannot book or update past dates"}

    time_str = data["time"]
    time_obj = datetime.strptime(time_str, "%H:%M").time()

    if time_obj < datetime.strptime("09:00", "%H:%M").time() or time_obj > datetime.strptime("18:00", "%H:%M").time():
        return {"error": "Booking allowed only between 09:00 and 18:00"}

    if not time_str.endswith(":00"):
        return {"error": "Only hourly bookings allowed"}

    existing = bookings_collection.find_one({
        "room_id": data["room_id"],
        "day_id": data["day_id"],
        "time": data["time"],
        "_id": {"$ne": ObjectId(id)}
    })

    if existing:
        return {"error": "Time slot already booked"}

    bookings_collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": {
            "day_id": data["day_id"],
            "time": data["time"]
        }}
    )

    return {"message": "Booking updated"}

@app.delete("/delete-room/{id}")
def delete_room(id: str, email: str):

    room = rooms_collection.find_one({"_id": ObjectId(id)})

    if not room:
        return {"error": "Room not found"}

    if room.get("user_email") != email:
        return {"error": "You can only delete your own room"}

    existing_booking = bookings_collection.find_one({"room_id": id})

    if existing_booking:
        return {"error": "Room has bookings, cannot delete"}

    rooms_collection.delete_one({"_id": ObjectId(id)})

    return {"message": "Room deleted"}

@app.get("/room-occupancy/{room_id}")
def room_occupancy(room_id: str):

    result = []
    total_slots = 9  # 09:00 → 18:00

    today = datetime.now().date()

    for i in range(5):
        day = today + timedelta(days=i)
        day_str = str(day)

        bookings = list(bookings_collection.find({
            "room_id": room_id,
            "day_id": day_str
        }))

        booked_slots = len(bookings)

        occupancy = (booked_slots / total_slots) * 100 if total_slots else 0

        result.append({
            "date": day_str,
            "booked_slots": booked_slots,
            "total_slots": total_slots,
            "occupancy": round(occupancy, 2)
        })

    return result

@app.get("/my-bookings/{email}")
def get_my_bookings(email: str):
    bookings = []
    for b in bookings_collection.find({"user_email": email}):
        b["_id"] = str(b["_id"])
        bookings.append(b)
    return bookings


from datetime import datetime, timedelta

@app.get("/room-availability/{room_id}")
def room_availability(room_id: str):

    result = []

    today = datetime.today().date()

    time_slots = [f"{hour:02d}:00" for hour in range(9, 19)]  

    for i in range(5):
        day = today + timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")

        bookings = list(bookings_collection.find({
            "room_id": room_id,
            "day_id": day_str
        }))

        booked_times = [b["time"] for b in bookings]

        available_slot = None
        for slot in time_slots:
            if slot not in booked_times:
                available_slot = slot
                break

        result.append({
            "date": day_str,
            "earliest_available": available_slot if available_slot else "Fully booked"
        })

    return result
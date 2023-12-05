from fastapi import FastAPI, Request

from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, joinedload
from motor.motor_asyncio import AsyncIOMotorClient

import shutil
from pathlib import Path

import uuid

# PostgreSQL Database setup
DATABASE_URL = "postgresql://postgres:sathiskar@localhost:5432/xpayback"
engine = create_engine(DATABASE_URL)
Base = declarative_base()

# Connect to MongoDB database
DATABASE_URL_MONGODB = "mongodb://localhost:27017"
client_mongodb = AsyncIOMotorClient(DATABASE_URL_MONGODB)
db_mongodb = client_mongodb["xpayback"]

# Define the directory where uploaded images will be stored
UPLOAD_DIR = Path("image_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI()

# Model for PostgreSQL Users table
class User(Base):
    __tablename__ = "Users"
    user_id = Column(Integer, index=True, primary_key=True, autoincrement=True)
    FirstName = Column(String, index=True)
    Password = Column(String)
    Email = Column(String, unique=True, index=True)
    Phone = Column(String, unique=True, index=True)

    # Relationship to Profile table
    profiles = relationship("Profile", back_populates="user")

class Profile(Base):
    __tablename__ = "Profile"
    user_id = Column(Integer, ForeignKey("Users.user_id"), index=True)
    profile_id = Column(Integer, index=True, primary_key=True, autoincrement=True)
    Profile_picture = Column(String, unique=True, index=True)

    # Relationship to Users table
    user = relationship("User", back_populates="profiles")

Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def generate_profile_picture_name(profile_picture):
    profile_picture_extension = profile_picture.split(".")[-1]
    profile_picture_unique_name = str(uuid.uuid4()) + "." + profile_picture_extension
    return profile_picture_unique_name

def check_existing(email, phone):
    db = SessionLocal()
    existing_email = db.query(User).filter(User.Email == email).first()
    existing_phone = db.query(User).filter(User.Phone == phone).first()
    db.close()
    return existing_email, existing_phone

@app.get("/")
def home(name : str):
    return "hello," + name

@app.post("/register")
async def register(request: Request):
    try:
        form = await request.form()
        first_name = form.get('firstName')
        email = form.get('email')
        password = form.get('password')
        phone = form.get('phone')
        profile_picture = form.get('profilePicture').filename

        if None in [first_name, email, password, phone, profile_picture]:
            response = {
                "code" : 400,
                "message" : "invalidParams",
                "data": []
            }
            return response

        profile_picture_name = generate_profile_picture_name(profile_picture)
        # Save the image to the local file system
        file_path = UPLOAD_DIR / profile_picture_name
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(form.get('profilePicture').file, buffer)

        existing_email,existing_phone = check_existing(email, phone)

        if existing_email:
            response = {
                "code": 400,
                "message": "Email already exist",
                "data": []
            }
            return response

        if existing_phone:
            response = {
                "code": 400,
                "message": "Phone Number already exist",
                "data": []
            }
            return response

        # Create a database session
        db = SessionLocal()

        """create new user"""
        new_user = User(FirstName=first_name, Password=password, Email=email, Phone=phone)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        """create profile for new user"""
        # Save profile picture to MongoDB
        await db_mongodb.users.insert_one(
            {"user_id": new_user.user_id, "profile_picture": profile_picture_name})


        response = {
            "code": 200,
            "message": "success",
            "data": {
                "fullName" : first_name,
                "email" : email,
                "password" : password,
                "phone" : phone,
                "profilePicture" : profile_picture,
            }
        }
        return response
    except Exception as err:
        response = {
            "code": 500,
            "message": "internalServerError",
            "data": err
        }
        return response

# Endpoint to get all users with profiles
@app.get("/register/getall")
async def get_registered_user_details():
    try:
        # Create a database session
        db = SessionLocal()

        users_with_profiles = db.query(User).all()

        user_list = []
        for user in users_with_profiles:
            profile_data = await db_mongodb.users.find_one({"user_id": user.user_id})
            user_data = {
                "user_id": user.user_id,
                "FirstName": user.FirstName,
                "Password": user.Password,
                "Email": user.Email,
                "Phone": user.Phone,
                "profiles": str(profile_data),
            }
            user_list.append(user_data)

        response = {
            "code": 200,
            "message": "success",
            "data": user_list,
        }

        return response

    except Exception as err:
        response = {
            "code": 500,
            "message": "internalServerError",
            "data": err
        }
        return response

    finally:
        db.close()
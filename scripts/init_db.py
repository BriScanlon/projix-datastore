import os
import time
import sys
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, OperationFailure
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from bson import ObjectId


# helper for mongodb ObjectId conversion
class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return str(v)


# user schema for mongodb
class User(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    email: EmailStr = Field(..., description="User's email address, used for login")
    hashed_password: str = Field(..., desdcription="Hashed password for security")
    is_active: bool = Field(default=True, description="Whether the user is active")
    is_verified: bool = Field(
        default=False, description="Whether the user has verified their account"
    )
    roles: List[str] = Field(default=["tenant_user"])
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tenant_id: Optional[str] = Field(
        default=None, description="Optional tenant ID for multi-tenant setup"
    )

    class Config:
        json_encoders = {ObjectId: str}
        schema_extra = {
            "example": {
                "email": "user@example.com",
                "hashed_password": "$2b$12$...",
                "is_active": True,
                "is_verified": False,
                "roles": ["user"],
                "created_at": "2023-12-01T12:00:00Z",
                "updated_at": "2023-12-01T12:00:00Z",
                "tenant_id": "abc123",
            }
        }


# Load environment variables
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_ROOT_USER = os.getenv("DB_ROOT_USER")
DB_ROOT_PASS = os.getenv("DB_ROOT_PASS")
APP_ADMIN_USER = os.getenv("APP_ADMIN_USER")
APP_ADMIN_PASS = os.getenv("APP_ADMIN_PASS")
ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")

# MongoDB URI
mongo_uri = f"mongodb://{DB_ROOT_USER}:{DB_ROOT_PASS}@{DB_HOST}:{DB_PORT}/admin"


# Wait for MongoDB to become available
def wait_for_db():
    print("Waiting for MongoDB to become available...")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)

    while True:
        try:
            client.server_info()
            print("MongoDB is up and running!")
            break
        except ServerSelectionTimeoutError:
            print("Database is not available yet, retrying in 5 seconds...")
            time.sleep(5)


# Check and initialize the database
def check_and_initialise_db():
    client = MongoClient(mongo_uri)
    db = client[DB_NAME]  # Get database object

    # Check if the user already exists
    try:
        existing_users = db.command("usersInfo", APP_ADMIN_USER)["users"]
        if existing_users:
            print(
                f"Admin user '{APP_ADMIN_USER}' already exists, skipping user creation."
            )
    except OperationFailure:
        print(
            "Error checking existing users. Ensure MongoDB authentication is set up correctly."
        )

    else:
        # Create the admin user only if it does not exist
        print(f"Creating Application Admin user '{APP_ADMIN_USER}'...")
        db.command(
            "createUser", APP_ADMIN_USER, pwd=APP_ADMIN_PASS, roles=["readWrite"]
        )
        print("Admin user created successfully.")

    # Ensure 'roles' collection exists
    db_collections = db.list_collection_names()
    if "roles" not in db_collections:
        print("Creating 'roles' collection...")
        db.create_collection("roles")
        print("'roles' collection created.")

    # Ensure sysadmin exists in the 'users' collection
    users_collection = db["users"]
    admin_user = users_collection.find_one({"username": ADMIN_USER})

    if not admin_user:
        print(
            f"Creating application admin user '{ADMIN_USER}' with 'sysadmin' role..."
        )

        # Create the admin user using the `User` schema
        admin_data = User(
            email=ADMIN_USER,
            hashed_password=ADMIN_PASS,  # This should be a pre-hashed password
            is_active=True,
            is_verified=True,
            roles=["sysadmin"],
        ).dict(by_alias=True)

        users_collection.insert_one(admin_data)
        print("Admin user created successfully in users collection.")
    else:
        print(f"Admin user '{ADMIN_USER}' already exists in users collection.")

    print("Database initialization complete.")
    client.close()
    sys.exit(0)


# Run the script
if __name__ == "__main__":
    print(
        f"Beginning MongoDB initialization. Connecting to server: {DB_HOST}:{DB_PORT}"
    )
    wait_for_db()
    check_and_initialise_db()

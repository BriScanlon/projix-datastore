import os
import time
import sys
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, OperationFailure
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from bson import ObjectId
import bcrypt


# Hash password before storing
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


# Verify password during login
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


class PyObjectId(ObjectId):
    """Custom Pydantic Type for MongoDB ObjectId"""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, schema):
        schema.update(type="string")


class User(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,  # ✅ Allow non-standard types like ObjectId
        json_schema_extra={
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
        },
    )

    id: Optional[ObjectId] = Field(
        default_factory=ObjectId, alias="_id"
    )  # ✅ Still stores as ObjectId
    email: EmailStr = Field(..., description="User's email address, used for login")
    hashed_password: str = Field(..., description="Hashed password for security")
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

    # Ensure 'roles' collection exists
    db_collections = db.list_collection_names()
    if "roles" not in db_collections:
        print("Creating 'roles' collection...")
        db.create_collection("roles")
        print("'roles' collection created.")

    # Ensure sysadmin exists in the 'users' collection
    users_collection = db["users"]
    existing_admin = users_collection.find_one(
        {"email": ADMIN_USER}
    )  # ✅ Fixes incorrect query

    if not existing_admin:
        print(f"Creating application admin user '{ADMIN_USER}' with 'sysadmin' role...")

        hashed_password = hash_password(ADMIN_PASS)

        # Create the admin user using the `User` schema
        admin_data = User(
            email=ADMIN_USER,
            hashed_password=hashed_password,
            is_active=True,
            is_verified=True,
            roles=["sysadmin"],
        ).model_dump(by_alias=True)
        admin_data["_id"] = ObjectId()

        users_collection.insert_one(admin_data)
        print("Admin user created successfully in users collection.")
    else:
        print(f"Admin user '{ADMIN_USER}' already exists in users collection.")

    # ✅ Ensure `APP_ADMIN_USER` is created in `admin` database
    admin_db = client["admin"]
    existing_app_admin = admin_db.command("usersInfo", APP_ADMIN_USER)

    if not existing_app_admin["users"]:
        print(f"Creating APP_ADMIN_USER '{APP_ADMIN_USER}' in admin database...")

        admin_db.command(
            "createUser",
            APP_ADMIN_USER,
            pwd=APP_ADMIN_PASS,
            roles=[
                {"role": "readWrite", "db": DB_NAME}
            ],  # ✅ Grant readWrite access to `projix_db`
        )

        print(
            f"APP_ADMIN_USER '{APP_ADMIN_USER}' created successfully in admin database."
        )
    else:
        print(f"APP_ADMIN_USER '{APP_ADMIN_USER}' already exists in admin database.")

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

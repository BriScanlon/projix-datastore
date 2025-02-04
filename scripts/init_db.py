import os
import time
import sys
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

# load environment variables
DB_HOST = os.getenv("DB_HOST", "mongodb")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_ROOT_USER = os.getenv("DB_ROOT_USER")
DB_ROOT_PASS = os.getenv("DB_ROOT_PASS")
APP_ADMIN_USER = os.getenv("APP_ADMIN_USER")
APP_ADMIN_PASS = os.getenv("APP_ADMIN_PASS")

# mondgodb URI
mongo_uri = f"mongodb://{DB_ROOT_USER}:{DB_ROOT_PASS}@{DB_HOST}:{DB_PORT}/admin"


# wait for Database to come online
def wait_for_db():
    print("Waiting for MongoDB to become available...")
    client = MongoClient(mongo_uri, ServerSelectionTimeoutMS=5000)

    while True:
        try:
            client.server_info()
            print("MongoDB is up and running!")
            break
        except ServerSelectionTimeoutError:
            print("Database is not available yet, retrying in 5 seconds...")
            time.sleep(5)


def check_and_initialise_db():
    client = MongoClient(mongo_uri)
    db_list = client.list_database_names()

    if DB_NAME in db_list:
        print(f"Database '{DB_NAME}' already exists. Exiting initialisation.")
    else:
        print(f"Creating database '{DB_NAME}'...")
        db = client[DB_NAME]

        print(f"Creating Application Admin user '{APP_ADMIN_USER}'...")
        db.command(
            "createUser", APP_ADMIN_USER, pwd=APP_ADMIN_PASS, roles=["readWrite"]
        )
        print("Admin user created successfully.")

    print("Database initialisation complete.")
    client.close()
    sys.exit(0)


if __name__ == "__main__":
    print(f"Beginning mongodb initialisation. Connecting to server: {DB_HOST}:{DB_PORT}")
    wait_for_db()
    check_and_initialise_db()

import pymongo
from pymongo import MongoClient
import hashlib
import logging
import json
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Set up logging
logger = logging.getLogger("MongoDBSetup")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler("mongodb_setup.log", maxBytes=5*1024*1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.addHandler(logging.StreamHandler())

def load_mongo_uri():
    return os.getenv("DROIDWARE_MONGO_URI", "mongodb://127.0.0.1:27017")

# MongoDB configuration
MONGO_URI = load_mongo_uri()
MONGO_HOST = MONGO_URI.replace("mongodb://", "").split(":")[0]
MONGO_PORT = int(MONGO_URI.rsplit(":", 1)[1].split("/")[0])
DATABASE_NAME = "federated_learning_db"
COLLECTION_NAME = "users"
DEFAULT_ADMIN_USERNAME = os.getenv("DROIDWARE_ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("DROIDWARE_ADMIN_PASSWORD", "change-me-admin-password")
DEFAULT_ADMIN_EMAIL = os.getenv("DROIDWARE_ADMIN_EMAIL", "admin@droidware.local")

def hash_password(password):
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def configure_mongodb():
    """Configure MongoDB for the federated learning server."""
    client = None
    try:
        # Connect to MongoDB
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)  # 5-second timeout
        client.admin.command("ping")  # Test connection
        logger.info(f"Connected to MongoDB at {MONGO_HOST}:{MONGO_PORT}")

        # Select or create the database
        db = client[DATABASE_NAME]
        logger.info(f"Selected database: {DATABASE_NAME}")

        # Select or create the users collection
        users_collection = db[COLLECTION_NAME]
        logger.info(f"Selected collection: {COLLECTION_NAME}")

        # Create unique indexes
        users_collection.create_index("username", unique=True, name="username_unique_idx")
        users_collection.create_index("email", unique=True, name="email_unique_idx")
        logger.info("Created unique indexes on 'username' and 'email'")

        # Check if admin user already exists
        admin_username = DEFAULT_ADMIN_USERNAME
        if users_collection.find_one({"username": admin_username}):
            logger.info(f"Admin user '{admin_username}' already exists, skipping insertion")
        else:
            # Insert initial admin user
            admin_user = {
                "username": admin_username,
                "password_hash": hash_password(DEFAULT_ADMIN_PASSWORD),
                "email": DEFAULT_ADMIN_EMAIL,
                "phone": None,
                "is_admin": True,
                "totp_secret": None
            }
            users_collection.insert_one(admin_user)
            logger.info(f"Inserted admin user: {admin_username}, Email: {DEFAULT_ADMIN_EMAIL}")

        # Verify the setup
        user_count = users_collection.count_documents({})
        logger.info(f"Total users in collection: {user_count}")
        admin_doc = users_collection.find_one({"username": admin_username})
        if admin_doc:
            logger.info(f"Admin user details: {admin_doc}")
        else:
            logger.warning("Admin user not found after insertion, something went wrong")

    except pymongo.errors.ServerSelectionTimeoutError as e:
        logger.error(f"Could not connect to MongoDB at {MONGO_HOST}:{MONGO_PORT}: {e}")
        raise
    except pymongo.errors.ConfigurationError as e:
        logger.error(f"Configuration error with MongoDB: {e}")
        raise
    except pymongo.errors.DuplicateKeyError as e:
        logger.error(f"Duplicate key error during setup: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during MongoDB setup: {e}")
        raise
    finally:
        if client:
            client.close()
            logger.info("MongoDB connection closed")

if __name__ == "__main__":
    try:
        configure_mongodb()
        print(f"MongoDB configuration completed successfully at {MONGO_HOST}:{MONGO_PORT}. Check mongodb_setup.log for details.")
    except Exception as e:
        print(f"Error configuring MongoDB: {e}")

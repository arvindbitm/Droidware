#!/usr/bin/env python3
import os
from pathlib import Path

import pyotp
from pymongo import MongoClient


ROOT = Path(__file__).resolve().parent
ADMIN_USERNAME = "admin"
ISSUER = "Droidware"
MONGO_URI = os.getenv("DROIDWARE_MONGO_URI", "mongodb://127.0.0.1:27017")


def main():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")

    users = client["federated_learning_db"]["users"]
    secret = pyotp.random_base32()
    result = users.update_one(
        {"username": ADMIN_USERNAME},
        {"$set": {"totp_secret": secret, "is_admin": True}},
    )
    if result.matched_count != 1:
        raise SystemExit(f"Admin user '{ADMIN_USERNAME}' not found.")

    uri = pyotp.TOTP(secret).provisioning_uri(
        name=ADMIN_USERNAME,
        issuer_name=ISSUER,
    )
    print(f"Updated TOTP secret for '{ADMIN_USERNAME}'.")
    print(f"Secret: {secret}")
    print(f"Authenticator URI: {uri}")
    print("Add this secret/URI to your authenticator app, then restart the server.")


if __name__ == "__main__":
    main()

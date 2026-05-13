import hashlib
import logging
import os
from logging.handlers import RotatingFileHandler
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
import json
import time
import aiofiles
from logging_manager import get_logger

# Logger setup
# auth_logger = logging.getLogger("Auth")
# auth_logger.setLevel(logging.DEBUG)
# auth_handler = RotatingFileHandler("auth.log", maxBytes=5*1024*1024, backupCount=5)
# auth_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
# auth_handler.setFormatter(auth_formatter)
# auth_logger.addHandler(auth_handler)
# auth_logger.addHandler(logging.StreamHandler())
auth_logger = get_logger("Auth","auth.log")
auth_logger.addHandler(logging.getLogger("MasterLog").handlers[0])

# Audit logger for admin actions
# audit_logger = logging.getLogger("Audit")
# audit_logger.setLevel(logging.INFO)
# audit_handler = RotatingFileHandler("audit.log", maxBytes=5*1024*1024, backupCount=5)
# audit_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
# audit_logger.addHandler(audit_handler)
audit_logger = get_logger("Audit","audit.log")


from device_fingerprint import generate_device_fingerprint, verify_device_fingerprint
from token_manager import create_token, verify_token, revoke_token, rotate_hmac_key, sign_request, verify_signature
from mfa import generate_otp, send_otp_email, send_otp_sms, verify_otp, generate_totp_secret, verify_totp
from firewall import check_geo_location, update_approved_locations, rate_limit, check_admin_whitelist, update_admin_whitelist
from security_engine import destroy_session, prompt_reauthentication

def get_mongo_uri():
    return os.getenv("DROIDWARE_MONGO_URI", "mongodb://127.0.0.1:27017")
# MongoDB setup
mongo_client = MongoClient(get_mongo_uri())
db = mongo_client["federated_learning_db"]
users_collection = db["users"]
# Check and create indexes if they don’t exist
existing_indexes = users_collection.index_information()
if "username_unique_idx" not in existing_indexes:
    users_collection.create_index("username", unique=True, name="username_unique_idx")
if "email_unique_idx" not in existing_indexes:
    users_collection.create_index("email", unique=True, name="email_unique_idx")
class AuthManager:
    def __init__(self):
        self.sessions = {}  # {token: {"username": str, "fingerprint": str, "ip": str, "otp": str, "otp_time": float, "hmac_key": str, "refresh_token": str, "admin_token": str}}
        self.last_registration_error = None
        self.last_admin_error = None

    def hash_password(self, password):
        """Hash a password and log the action."""
        hashed = hashlib.sha256(password.encode()).hexdigest()
        auth_logger.info(f"Password hashed for registration or login")
        return hashed

    def register_user(self, username, password, email, phone=None, is_admin=False):
        """Register a user and log the process."""
        self.last_registration_error = None
        existing_user = users_collection.find_one({"username": username})
        if existing_user:
            self.last_registration_error = "username already exists"
            auth_logger.info(f"User registration skipped: {username} already exists")
            return False, existing_user.get("totp_secret") if is_admin else None

        existing_email = users_collection.find_one({"email": email})
        if existing_email:
            self.last_registration_error = "email already exists"
            auth_logger.info(f"User registration skipped: email already exists for {email}")
            return False, None

        password_hash = self.hash_password(password)
        totp_secret = generate_totp_secret() if is_admin else None
        user_doc = {
            "username": username,
            "password_hash": password_hash,
            "email": email,
            "phone": phone,
            "is_admin": is_admin,
            "totp_secret": totp_secret
        }
        try:
            users_collection.insert_one(user_doc)
            auth_logger.info(f"User registered: {username}, Email: {email}, Admin: {is_admin}, TOTP Secret: {totp_secret if is_admin else 'N/A'}")
            return True, totp_secret if is_admin else None
        except DuplicateKeyError as e:
            duplicate_value = e.details.get('keyValue') if e.details else "unknown duplicate"
            self.last_registration_error = f"duplicate {duplicate_value}"
            auth_logger.error(f"Registration failed for {username}: Duplicate {duplicate_value}")
            return False, None
        except Exception as e:
            self.last_registration_error = str(e)
            auth_logger.error(f"Registration failed for {username}: {e}")
            return False, None

    async def authenticate_step1(self, username, password, client_ip):
        """Step 1: Verify username/password and log."""
        auth_logger.info(f"Authentication step 1 initiated for {username} from {client_ip}")
        user = users_collection.find_one({"username": username})
        if not user or user["password_hash"] != self.hash_password(password):
            auth_logger.warning(f"Authentication failed for {username} at {client_ip}: Invalid credentials")
            return None, None
        email = user["email"]
        auth_logger.info(f"Step 1 passed for {username} at {client_ip}")
        return username, email

    async def authenticate_step2(self, username, email, client_ip, mfa_method="email"):
        """Step 2: Send OTP and log."""
        auth_logger.info(f"Authentication step 2 initiated for {username} from {client_ip}")
        if not await rate_limit(client_ip) or not await check_geo_location(client_ip):
            auth_logger.warning(f"Authentication blocked for {username} at {client_ip}: Firewall restriction")
            return None
        user = users_collection.find_one({"username": username})
        if user["is_admin"] and not check_admin_whitelist(client_ip):
            auth_logger.warning(f"Admin access denied for {username} at {client_ip}: Not in whitelist")
            return None

        fingerprint, ip = generate_device_fingerprint(client_ip=client_ip)
        otp, otp_time = generate_otp()
        if mfa_method == "email":
            send_otp_email(email, otp)
        elif mfa_method == "sms":
            phone = user.get("phone")
            if phone:
                send_otp_sms(phone, otp)
            else:
                auth_logger.error(f"No phone number for {username} at {client_ip}")
                return None

        self.sessions[f"{username}_temp"] = {
            "username": username,
            "fingerprint": fingerprint,
            "ip": ip,
            "otp": otp,
            "otp_time": otp_time,
            "is_admin": user["is_admin"],
            "totp_secret": user.get("totp_secret")
        }
        auth_logger.info(f"Step 2 completed for {username} at {client_ip}: OTP sent via {mfa_method}")
        return "OTP_SENT"

    async def authenticate_step3(self, username, client_ip, otp, totp_code=None):
        """Step 3: Verify OTP/TOTP and issue tokens, logging everything."""
        auth_logger.info(f"Authentication step 3 initiated for {username} from {client_ip}")
        temp_key = f"{username}_temp"
        if temp_key not in self.sessions:
            auth_logger.warning(f"No pending session for {username} at {client_ip}")
            return None

        session = self.sessions.pop(temp_key)
        if not verify_otp(session["otp"], session["otp_time"], otp):
            auth_logger.warning(f"OTP verification failed for {username} at {client_ip}")
            return None
        if session["is_admin"] and not verify_totp(session["totp_secret"], totp_code):
            auth_logger.warning(f"TOTP verification failed for admin {username} at {client_ip}")
            return None

        token = create_token(session["fingerprint"])
        refresh_token = create_token(session["fingerprint"], is_refresh=True)
        admin_token = create_token(session["fingerprint"], is_admin=True) if session["is_admin"] else None
        hmac_key, _ = rotate_hmac_key()
        self.sessions[token] = {
            "username": username,
            "fingerprint": session["fingerprint"],
            "ip": client_ip,
            "otp": None,
            "otp_time": None,
            "hmac_key": hmac_key,
            "refresh_token": refresh_token,
            "admin_token": admin_token,
            "last_active": time.time()
        }
        auth_logger.info(f"Authentication completed for {username} at {client_ip}: Token {token}, Refresh {refresh_token}, Admin Token {admin_token if admin_token else 'N/A'}")
        return token, refresh_token, hmac_key, admin_token

    async def refresh_token(self, refresh_token, client_ip):
        """Refresh a token and log the process."""
        auth_logger.info(f"Token refresh requested from {client_ip} with refresh token {refresh_token}")
        fingerprint, ip = generate_device_fingerprint()
        is_valid, token_type = verify_token(refresh_token, fingerprint)
        if not is_valid or token_type != "refresh":
            auth_logger.warning(f"Refresh token invalid for {client_ip}: {refresh_token}")
            return None
        for token, session in list(self.sessions.items()):
            if session["refresh_token"] == refresh_token:
                new_token = create_token(fingerprint)
                hmac_key, _ = rotate_hmac_key()
                new_admin_token = create_token(fingerprint, is_admin=True) if session["admin_token"] else None
                self.sessions[new_token] = {
                    "username": session["username"],
                    "fingerprint": fingerprint,
                    "ip": ip,
                    "otp": None,
                    "otp_time": None,
                    "hmac_key": hmac_key,
                    "refresh_token": refresh_token,
                    "admin_token": new_admin_token,
                    "last_active": time.time()
                }
                del self.sessions[token]
                auth_logger.info(f"Token refreshed for {session['username']} at {client_ip}: New Token {new_token}, Admin Token {new_admin_token if new_admin_token else 'N/A'}")
                return new_token, hmac_key, new_admin_token
        auth_logger.warning(f"No session found for refresh token {refresh_token} at {client_ip}")
        return None

    async def verify_request(self, token, client_ip, request_data, signature, is_admin_action=False):
        """Verify a request with full logging."""
        auth_logger.info(f"Verifying request from {client_ip} with token {token}, Admin Action: {is_admin_action}")
        if token not in self.sessions:
            auth_logger.warning(f"No session for token {token} at {client_ip}")
            return False

        session = self.sessions[token]
        current_fp, current_ip = generate_device_fingerprint(client_ip=client_ip)

        if not verify_device_fingerprint(session["fingerprint"], current_fp):
            auth_logger.warning(f"Fingerprint mismatch for {client_ip}, destroying session")
            session["token"] = destroy_session(token, "Fingerprint mismatch")
            del self.sessions[token]
            return False

        is_valid, token_type = verify_token(token, session["fingerprint"])
        if not is_valid:
            auth_logger.warning(f"Token invalid/expired for {client_ip}, destroying session")
            session["token"] = destroy_session(token, "Invalid/expired token")
            del self.sessions[token]
            return False

        if is_admin_action:
            if not session["admin_token"] or not verify_token(session["admin_token"], session["fingerprint"])[0]:
                auth_logger.warning(f"Admin token invalid or missing for {client_ip}")
                return False
            if not check_admin_whitelist(client_ip):
                auth_logger.warning(f"Admin action denied for {client_ip}: Not in whitelist")
                return False

        session_key = session.get("hmac_key")
        if not session_key or not verify_signature(request_data, signature, session_key, None):
            auth_logger.warning(f"Signature invalid for {client_ip}, destroying session")
            session["token"] = destroy_session(token, "Invalid signature")
            del self.sessions[token]
            return False

        if session["ip"] != client_ip:
            auth_logger.warning(f"IP mismatch for {client_ip}, prompting re-auth")
            action = prompt_reauthentication(token, "IP mismatch")
            return action

        if time.time() - session["last_active"] > 600:
            auth_logger.warning(f"Session expired for {client_ip} due to inactivity, destroying session")
            session["token"] = destroy_session(token, "Session inactivity")
            del self.sessions[token]
            return False

        session["last_active"] = time.time()
        auth_logger.info(f"Request verified successfully for {client_ip} with token {token}")
        return True

    async def admin_block_ip(self, admin_token, ip_to_block):
        """Admin command to block an IP with logging."""
        auth_logger.info(f"Admin block IP request for {ip_to_block} with token {admin_token}")
        if not await self._verify_admin(admin_token):
            auth_logger.warning(f"Admin block IP denied for token {admin_token}")
            return False
        audit_logger.info(f"Admin {self.sessions[admin_token]['username']} blocked IP {ip_to_block}")
        auth_logger.info(f"IP {ip_to_block} blocked by admin {self.sessions[admin_token]['username']}")
        return True

    async def admin_add_user(self, admin_token, username, email, password, phone=None):
        """Admin command to add a user with logging."""
        self.last_admin_error = None
        auth_logger.info(f"Admin add user request for {username} with token {admin_token}")
        if not await self._verify_admin(admin_token):
            self.last_admin_error = "admin privilege required"
            auth_logger.warning(f"Admin add user denied for token {admin_token}")
            return False
        success, _ = self.register_user(username, password, email, phone, is_admin=False)
        if success:
            audit_logger.info(f"Admin {self.sessions[admin_token]['username']} added user {username}")
            auth_logger.info(f"User {username} added by admin {self.sessions[admin_token]['username']}")
        else:
            self.last_admin_error = self.last_registration_error or "user registration failed"
            auth_logger.warning(f"Failed to add user {username} by admin {self.sessions[admin_token]['username']}")
        return success

    async def admin_delete_user(self, admin_token, username):
        """Admin command to delete a user with logging."""
        auth_logger.info(f"Admin delete user request for {username} with token {admin_token}")
        if not await self._verify_admin(admin_token):
            auth_logger.warning(f"Admin delete user denied for token {admin_token}")
            return False
        result = users_collection.delete_one({"username": username})
        if result.deleted_count > 0:
            audit_logger.info(f"Admin {self.sessions[admin_token]['username']} deleted user {username}")
            auth_logger.info(f"User {username} deleted by admin {self.sessions[admin_token]['username']}")
        else:
            auth_logger.warning(f"User {username} not found for deletion by admin {self.sessions[admin_token]['username']}")
        return result.deleted_count > 0

    async def admin_list_sessions(self, admin_token):
        """Admin command to list sessions with logging."""
        auth_logger.info(f"Admin list sessions request with token {admin_token}")
        if not await self._verify_admin(admin_token):
            auth_logger.warning(f"Admin list sessions denied for token {admin_token}")
            return None
        sessions_info = [{k: v for k, v in s.items() if k != "otp"} for s in self.sessions.values()]
        audit_logger.info(f"Admin {self.sessions[admin_token]['username']} listed sessions")
        auth_logger.info(f"Sessions listed by admin {self.sessions[admin_token]['username']}: {len(sessions_info)} sessions")
        return sessions_info

    async def admin_terminate_session(self, admin_token, target_token):
        """Admin command to terminate a session with logging."""
        auth_logger.info(f"Admin terminate session request for {target_token} with token {admin_token}")
        if not await self._verify_admin(admin_token):
            auth_logger.warning(f"Admin terminate session denied for token {admin_token}")
            return False
        if target_token in self.sessions:
            del self.sessions[target_token]
            revoke_token(target_token)
            audit_logger.info(f"Admin {self.sessions[admin_token]['username']} terminated session {target_token}")
            auth_logger.info(f"Session {target_token} terminated by admin {self.sessions[admin_token]['username']}")
            return True
        auth_logger.warning(f"Session {target_token} not found for termination by admin {self.sessions[admin_token]['username']}")
        return False

    async def admin_update_geo(self, admin_token, country, action):
        """Admin command to update geo-locations with logging."""
        auth_logger.info(f"Admin update geo request for {country} ({action}) with token {admin_token}")
        if not await self._verify_admin(admin_token):
            auth_logger.warning(f"Admin update geo denied for token {admin_token}")
            return False
        update_approved_locations(None, country, approved_by_admin=(action == "add"))
        audit_logger.info(f"Admin {self.sessions[admin_token]['username']} updated geo: {country} {action}")
        auth_logger.info(f"Geo updated by admin {self.sessions[admin_token]['username']}: {country} {action}")
        return True

    async def admin_update_whitelist(self, admin_token, ip, action):
        """Admin command to update whitelist with logging."""
        auth_logger.info(f"Admin update whitelist request for {ip} ({action}) with token {admin_token}")
        if not await self._verify_admin(admin_token):
            auth_logger.warning(f"Admin update whitelist denied for token {admin_token}")
            return False
        update_admin_whitelist(ip, action)
        audit_logger.info(f"Admin {self.sessions[admin_token]['username']} updated whitelist: {ip} {action}")
        auth_logger.info(f"Whitelist updated by admin {self.sessions[admin_token]['username']}: {ip} {action}")
        return True

    async def admin_set_rate_limit(self, admin_token, ip, threshold):
        """Admin command to set rate limit with logging."""
        auth_logger.info(f"Admin set rate limit request for {ip} to {threshold} with token {admin_token}")
        if not await self._verify_admin(admin_token):
            auth_logger.warning(f"Admin set rate limit denied for token {admin_token}")
            return False
        r.set(f"custom_rate:{ip}", threshold)
        audit_logger.info(f"Admin {self.sessions[admin_token]['username']} set rate limit for {ip} to {threshold}")
        auth_logger.info(f"Rate limit set by admin {self.sessions[admin_token]['username']}: {ip} to {threshold}")
        return True

    async def _verify_admin(self, admin_token):
        """Verify admin status with logging."""
        auth_logger.info(f"Verifying admin status for token {admin_token}")
        if admin_token not in self.sessions or not self.is_admin(self.sessions[admin_token]["username"]):
            auth_logger.warning(f"Admin verification failed for token {admin_token}: Not an admin or no session")
            return False
        auth_logger.info(f"Admin verified for token {admin_token}: {self.sessions[admin_token]['username']}")
        return True

    def is_admin(self, username):
        """Check if a user is an admin and log."""
        user = users_collection.find_one({"username": username})
        is_admin = user and user["is_admin"]
        auth_logger.info(f"Checked admin status for {username}: {is_admin}")
        return is_admin
        

import os
import time
import hmac
import hashlib
import json
import base64
import secrets
import logging
from http.cookies import SimpleCookie

# Logger setup
cookie_logger = logging.getLogger("CookieManager")
cookie_logger.setLevel(logging.DEBUG)
cookie_handler = logging.FileHandler("cookies.log")
cookie_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
cookie_handler.setFormatter(cookie_formatter)
cookie_logger.addHandler(cookie_handler)
cookie_logger.addHandler(logging.StreamHandler())

# Master log setup
master_logger = logging.getLogger("MasterLog")
cookie_logger.addHandler(master_logger.handlers[0])  # Link to master log

# Secure secret key for signing cookies
COOKIE_SECRET = os.getenv("COOKIE_SECRET", secrets.token_hex(32))
COOKIE_EXPIRATION = 300  # 5 minutes


def sign_data(data):
    """Create a secure HMAC signature for the given data."""
    return hmac.new(COOKIE_SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()


def create_cookie(session_id, user_data):
    """Generate a secure cookie for session handling."""
    timestamp = int(time.time())
    payload = json.dumps({"session_id": session_id, "user": user_data, "timestamp": timestamp})
    payload_encoded = base64.b64encode(payload.encode()).decode()
    signature = sign_data(payload_encoded)
    
    cookie_value = f"{payload_encoded}|{signature}"
    cookie_logger.info(f"Created secure cookie for session: {session_id}")
    master_logger.info(f"Session cookie issued for user: {user_data}")
    
    return cookie_value


def verify_cookie(cookie_value):
    """Verify and decode the cookie, ensuring integrity."""
    try:
        payload_encoded, signature = cookie_value.split("|")
        expected_signature = sign_data(payload_encoded)
        
        if not hmac.compare_digest(signature, expected_signature):
            cookie_logger.warning("Cookie signature mismatch. Possible tampering detected.")
            master_logger.warning("Cookie signature mismatch detected!")
            return None
        
        payload_decoded = json.loads(base64.b64decode(payload_encoded).decode())
        session_id, timestamp = payload_decoded["session_id"], payload_decoded["timestamp"]
        
        if time.time() - timestamp > COOKIE_EXPIRATION:
            cookie_logger.warning("Cookie has expired.")
            master_logger.info("Session expired due to inactivity.")
            return None
        
        return payload_decoded
    except Exception as e:
        cookie_logger.error(f"Failed to verify cookie: {e}")
        master_logger.error(f"Cookie verification failure: {e}")
        return None


def invalidate_cookie():
    """Return an invalidated cookie value."""
    master_logger.info("Session cookie invalidated.")
    return "deleted; expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; Secure; SameSite=Strict"

import jwt
import time
import hmac
import hashlib
import ntplib
import logging
# from logging.handlers import RotatingFileHandler
from logging_manager import get_logger

# Logger setup
# tm_logger = logging.getLogger("TokenManager")
# tm_logger.setLevel(logging.DEBUG)
# tm_handler = RotatingFileHandler("token_manager.log", maxBytes=5*1024*1024, backupCount=5)
# tm_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
# tm_handler.setFormatter(tm_formatter)
# tm_logger.addHandler(tm_handler)
# tm_logger.addHandler(logging.StreamHandler())
tm_logger = get_logger("TokenManager","token_manager.log")
tm_logger.addHandler(logging.getLogger("MasterLog").handlers[0])

SECRET_KEY = "super-secret-key"  # Use a secrets manager in production
current_hmac_key = None
key_timestamp = 0
previous_hmac_key = None
REVOKED_TOKENS = set()
ENABLE_NTP_SYNC = False

def sync_clock():
    """Synchronize clock with NTP and log the result."""
    if not ENABLE_NTP_SYNC:
        return time.time()
    try:
        client = ntplib.NTPClient()
        response = client.request('pool.ntp.org', timeout=1)
        tm_logger.info(f"Clock synchronized with NTP offset: {response.offset}")
        return time.time() + response.offset
    except Exception as e:
        tm_logger.error(f"Failed to sync clock with NTP: {e}")
        return time.time()

def create_token(fingerprint, is_refresh=False, is_admin=False):
    """Create a token and log its creation."""
    try:
        synced_time = sync_clock()
        expiry = 300 if is_admin else (86400 if is_refresh else 900)  # 5min admin, 24h refresh, 15min access
        payload = {
            "fingerprint": fingerprint,
            "exp": int(synced_time) + expiry,
            "type": "admin" if is_admin else ("refresh" if is_refresh else "access")
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        tm_logger.info(f"Created {'admin' if is_admin else 'refresh' if is_refresh else 'access'} token: {token}")
        return token
    except Exception as e:
        tm_logger.error(f"Failed to create token: {e}")
        raise

def verify_token(token, fingerprint):
    """Verify a token and log the outcome."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        is_valid = payload["fingerprint"] == fingerprint and token not in REVOKED_TOKENS
        tm_logger.info(f"Token verification: {is_valid} (Token: {token}, Type: {payload['type']})")
        if not is_valid:
            tm_logger.warning(f"Token invalid or revoked: {token}")
        return is_valid, payload["type"]
    except jwt.ExpiredSignatureError:
        tm_logger.warning(f"Token expired: {token}")
        return False, None
    except Exception as e:
        tm_logger.error(f"Failed to verify token {token}: {e}")
        return False, None

def revoke_token(token):
    """Revoke a token and log the action."""
    REVOKED_TOKENS.add(token)
    tm_logger.info(f"Token revoked: {token}")

def rotate_hmac_key():
    """Rotate HMAC key and log the rotation."""
    global current_hmac_key, key_timestamp, previous_hmac_key
    synced_time = sync_clock()
    if synced_time - key_timestamp >= 60:
        previous_hmac_key = current_hmac_key
        current_hmac_key = hashlib.sha256(str(synced_time).encode()).hexdigest()
        key_timestamp = synced_time
        tm_logger.info(f"Rotated HMAC key: {current_hmac_key}")
    return current_hmac_key, previous_hmac_key

def sign_request(data, key):
    """Sign a request and log the signature."""
    signature = hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()
    tm_logger.info(f"Signed request: {data} -> {signature}")
    return signature

def verify_signature(data, signature, current_key, previous_key):
    """Verify a signature and log the result."""
    tm_logger.info(f"Data : {data}")
    expected_current = hmac.new(current_key.encode(), data.encode(), hashlib.sha256).hexdigest()
    if expected_current == signature:
        tm_logger.info(f"Signature verified with current key: {signature}")
        return True
    if previous_key and hmac.new(previous_key.encode(), data.encode(), hashlib.sha256).hexdigest() == signature:
        tm_logger.info(f"Signature verified with previous key: {signature}")
        return True
    tm_logger.warning(f"Signature verification failed (Expected: {expected_current}, Received: {signature})")
    return False

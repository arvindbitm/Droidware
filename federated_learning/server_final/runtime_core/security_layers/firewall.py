import geoip2.database
import redis
import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime
import json
import ipaddress
from pathlib import Path
from logging_manager import get_logger

# Logger setup
# fw_logger = logging.getLogger("Firewall")
# fw_logger.setLevel(logging.DEBUG)
# fw_handler = RotatingFileHandler("firewall.log", encoding='utf-8',maxBytes=5*1024*1024, backupCount=5)
# fw_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
# fw_handler.setFormatter(fw_formatter)
# fw_logger.addHandler(fw_handler)
# fw_logger.addHandler(logging.StreamHandler())
fw_logger = get_logger("Firewall","firewall.log")
fw_logger.addHandler(logging.getLogger("MasterLog").handlers[0])

ROOT = Path(__file__).resolve().parent
GEOIP_DB_PATH = ROOT / "GeoLite2-City.mmdb"

def get_redis_config():
    host = os.getenv("DROIDWARE_REDIS_HOST", "127.0.0.1")
    port = int(os.getenv("DROIDWARE_REDIS_PORT", "6379"))
    db = int(os.getenv("DROIDWARE_REDIS_DB", "0"))
    return host, port, db

host ,port,db = get_redis_config()
r = redis.Redis(host=host, port=port, db=db)
APPROVED_COUNTRIES = ["India"]
TRAFFIC_HISTORY = {}
ADMIN_WHITELIST = {"127.0.0.1", "localhost"}  # Initial whitelist

async def check_geo_location(ip):
    """Check geo-location and log the result."""
    try:
        ip_obj = ipaddress.ip_address(ip)
        if ip_obj.is_private or ip_obj.is_loopback:
            fw_logger.info(f"Geo check bypassed for private/local IP {ip}")
            return True
        reader = geoip2.database.Reader(str(GEOIP_DB_PATH))
        response = reader.city(ip)

        country = response.country.name
        fw_logger.debug(f"country {country}")
        is_allowed = country in APPROVED_COUNTRIES
        fw_logger.info(f"Geo check for IP {ip}: {country} - Allowed: {is_allowed}")
        if not is_allowed:
            fw_logger.warning(f"Geo-location blocked for IP {ip}: {country} not in {APPROVED_COUNTRIES}")
        return is_allowed
    except Exception as e:
        fw_logger.error(f"Failed to check geo for IP {ip}: {e}")
        return False

def update_approved_locations(ip, country, approved_by_admin=False):
    """Update approved countries and log the action."""
    if approved_by_admin and country not in APPROVED_COUNTRIES:
        APPROVED_COUNTRIES.append(country)
        fw_logger.info(f"Added {country} to approved locations by admin")
    is_allowed = country in APPROVED_COUNTRIES
    fw_logger.info(f"Updated geo check for IP {ip}: {country} - Allowed: {is_allowed}")
    return is_allowed

def update_admin_whitelist(ip, action):
    """Update admin whitelist and log the action."""
    if action == "add" and ip not in ADMIN_WHITELIST:
        ADMIN_WHITELIST.add(ip)
        fw_logger.info(f"Added {ip} to admin whitelist")
    elif action == "remove" and ip in ADMIN_WHITELIST:
        ADMIN_WHITELIST.remove(ip)
        fw_logger.info(f"Removed {ip} from admin whitelist")
    fw_logger.info(f"Admin whitelist updated: {ADMIN_WHITELIST}")

def check_admin_whitelist(ip):
    """Check admin whitelist and log the result."""
    is_allowed = ip in ADMIN_WHITELIST
    fw_logger.info(f"Admin whitelist check for IP {ip}: {is_allowed}")
    if not is_allowed:
        fw_logger.warning(f"IP {ip} not in admin whitelist: {ADMIN_WHITELIST}")
    return is_allowed

# def get_dynamic_threshold(ip):
#     """Calculate dynamic threshold and log it."""
#     now = datetime.now()
#     TRAFFIC_HISTORY[ip] = TRAFFIC_HISTORY.get(ip, []) + [now]
#     TRAFFIC_HISTORY[ip] = [t for t in TRAFFIC_HISTORY[ip] if (now - t).seconds < 3600]
#     attempt_count = len(TRAFFIC_HISTORY[ip])
#     threshold = max(5, min(10, attempt_count // 2))
#     custom = r.get(f"custom_rate:{ip}")
#     if custom:
#         threshold = int(custom)
#     fw_logger.info(f"Dynamic threshold for IP {ip}: {threshold} (Attempts: {attempt_count})")
#     return threshold

# async def rate_limit(ip):
#     """Enforce rate limiting and log the result."""
#     try:
#         key = f"rate:{ip}"
#         count = r.incr(key)
#         if count == 1:
#             r.expire(key, 60)
#         threshold = get_dynamic_threshold(ip)
#         is_allowed = count <= threshold
#         fw_logger.info(f"Rate limit check for IP {ip}: Count {count}, Threshold {threshold} - Allowed: {is_allowed}")
#         if not is_allowed:
#             fw_logger.warning(f"Rate limit exceeded for IP {ip}: {count} > {threshold}")
#         return is_allowed
#     except Exception as e:
#         fw_logger.error(f"Failed to rate limit IP {ip}: {e}")
#         return False



def get_dynamic_threshold(ip):
    """Calculate dynamic threshold using Redis storage and log it."""
    now = datetime.now().timestamp()

    # Store the timestamp in a Redis sorted set with expiration
    key = f"traffic:{ip}"
    r.zadd(key, {now: now})  # Add timestamp with itself as a score
    r.expire(key, 3600)  # Auto-expire after 1 hour

    # Remove expired entries and get valid request count
    r.zremrangebyscore(key, '-inf', now - 3600)
    attempt_count = r.zcard(key)

    # Adaptive rate limiting logic
    threshold = max(5, min(10, attempt_count // 2))

    # Custom threshold override
    custom = r.get(f"custom_rate:{ip}")
    if custom:
        threshold = int(custom)

    fw_logger.info(f"Dynamic threshold for IP {ip}: {threshold} (Attempts: {attempt_count})")
    return threshold

async def rate_limit(ip):
    """Enforce rate limiting with Redis and log the result."""
    try:
        key = f"rate:{ip}"
        count = r.incr(key)

        if count == 1:
            r.expire(key, 60)

        threshold = get_dynamic_threshold(ip)
        is_allowed = count <= threshold

        fw_logger.info(f"Rate limit check for IP {ip}: Count {count}, Threshold {threshold} - Allowed: {is_allowed}")

        if not is_allowed:
            fw_logger.warning(f"Rate limit exceeded for IP {ip}: {count} > {threshold}")
            

        return is_allowed
    except Exception as e:
        fw_logger.error(f"Failed to rate limit IP {ip}: {e}")
        return False

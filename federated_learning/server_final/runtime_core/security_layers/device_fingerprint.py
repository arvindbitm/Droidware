# import hashlib
# import uuid
# import socket
# import platform
# import logging
# from logging.handlers import RotatingFileHandler


# # Logger setup
# fp_logger = logging.getLogger("DeviceFingerprint")
# fp_logger.setLevel(logging.DEBUG)
# fp_handler = RotatingFileHandler("device_fingerprint.log", maxBytes=5*1024*1024, backupCount=5)
# fp_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
# fp_handler.setFormatter(fp_formatter)
# fp_logger.addHandler(fp_handler)
# fp_logger.addHandler(logging.StreamHandler())
# fp_logger.addHandler(logging.getLogger("MasterLog").handlers[0])

# def generate_device_fingerprint(client_ip = None):
#     """Generate a unique device fingerprint and log the process."""
#     ip = "unknown"
#     try:
#         mac = ':'.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff) for i in range(0, 48, 8)])
#         fp_logger.debug("Generated MAC address: %s" % mac)
#         # Generate a UUID based on a stable hardware identifier (e.g., MAC address + hostname)
#         device_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, mac + socket.gethostname()))
#         fp_logger("device_uuid : %s" % device_uuid)
#         system_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, platform.node()))
        
#         fp_logger.debug("system_uuid : %s"% system_uuid)
#         os_info = platform.platform()
#         fp_logger.debug("os_info : %s" % os_info)
#         # ip = client_ip if client_ip else socket.gethostbyname(socket.gethostname())
#         fp_logger.debug("client_ip : %s" % client_ip)
#         ip = client_ip if client_ip else socket.gethostbyname(socket.gethostname())

#         fp_logger.debug("ip : %s" % ip)
#         hardware_info = platform.processor() or "unknown"
#         fp_logger.debug("hardware_info : %s", hardware_info)
#         fingerprint = f"{mac}{system_uuid}{os_info}{ip}{hardware_info}"
#         fp_logger.debug("fingerprint : %s" % fingerprint)
#         hashed_fp = hashlib.sha256(fingerprint.encode()).hexdigest()
#         fp_logger.debug("hashed_fp : %s" % hashed_fp)
#         fp_logger.info(f"Generated fingerprint for IP {ip}: {hashed_fp}")
#         return hashed_fp, ip
#     except Exception as e:
#         fp_logger.error(f"Failed to generate fingerprint for IP {ip}: {e}")
#         raise

# def verify_device_fingerprint(stored_fp, current_fp):
#     """Verify a device fingerprint and log the result."""
#     is_valid = stored_fp == current_fp
#     fp_logger.info(f"Fingerprint verification: {is_valid} (Stored: {stored_fp}, Current: {current_fp})")
#     if not is_valid:
#         fp_logger.warning(f"Fingerprint mismatch detected (Stored: {stored_fp}, Current: {current_fp})")
#     return is_valid

import hashlib
import uuid
import socket
import platform
import logging
# from logging.handlers import 

from logging_manager import get_logger

# Logger setup
# fp_logger = logging.getLogger("DeviceFingerprint")
# fp_logger.setLevel(logging.DEBUG)
# fp_handler = RotatingFileHandler("device_fingerprint.log", maxBytes=5*1024*1024, backupCount=5)
# fp_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
# fp_handler.setFormatter(fp_formatter)
# fp_logger.addHandler(fp_handler)
# fp_logger.addHandler(logging.StreamHandler())
# Only add MasterLog handler if it exists and has handlers

fp_logger = get_logger("DeviceFingerprint","device_fingerprint.log")
master_logger = logging.getLogger("MasterLog")
if master_logger.handlers:
    fp_logger.addHandler(master_logger.handlers[0])

def generate_device_fingerprint(client_ip = None):
    """Generate a unique device fingerprint and log the process."""
    ip = "unknown"
    try:
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff) for i in range(0, 48, 8)])
        fp_logger.debug("Generated MAC address: %s" % mac)
        # Generate a UUID based on a stable hardware identifier (e.g., MAC address + hostname)
        device_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, mac + socket.gethostname()))
        fp_logger.debug("device_uuid : %s" % device_uuid)  # Fixed logging call
        system_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, platform.node()))
        
        fp_logger.debug("system_uuid : %s" % system_uuid)
        os_info = platform.platform()
        fp_logger.debug("os_info : %s" % os_info)
        ip = client_ip if client_ip else socket.gethostbyname(socket.gethostname())
        fp_logger.debug("client_ip : %s" % client_ip)
        fp_logger.debug("ip : %s" % ip)
        hardware_info = platform.processor() or "unknown"
        fp_logger.debug("hardware_info : %s" % hardware_info)
        fingerprint = f"{mac}{device_uuid}{system_uuid}{os_info}{ip}{hardware_info}"
        fp_logger.debug("fingerprint : %s" % fingerprint)
        hashed_fp = hashlib.sha256(fingerprint.encode()).hexdigest()
        fp_logger.debug("hashed_fp : %s" % hashed_fp)
        fp_logger.info(f"Generated fingerprint for IP {ip}: {hashed_fp}")
        return hashed_fp, ip
    except Exception as e:
        fp_logger.error(f"Failed to generate fingerprint for IP {ip}: {e}")
        raise

def verify_device_fingerprint(stored_fp, current_fp):
    """Verify a device fingerprint and log the result."""
    is_valid = stored_fp == current_fp
    fp_logger.info(f"Fingerprint verification: {is_valid} (Stored: {stored_fp}, Current: {current_fp})")
    if not is_valid:
        fp_logger.warning(f"Fingerprint mismatch detected (Stored: {stored_fp}, Current: {current_fp})")
    return is_valid
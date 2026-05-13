import smtplib
import os
import random
import time
from logging_manager import get_logger
from twilio.rest import Client
import pyotp

# Logger setup
mfa_logger = get_logger("MFA", "mfa.log")

TWILIO_SID = os.getenv("DROIDWARE_TWILIO_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("DROIDWARE_TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE = os.getenv("DROIDWARE_TWILIO_PHONE", "")
SMTP_SENDER = os.getenv("DROIDWARE_SMTP_SENDER", "")
SMTP_PASSWORD = os.getenv("DROIDWARE_SMTP_PASSWORD", "")
SMTP_HOST = os.getenv("DROIDWARE_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("DROIDWARE_SMTP_PORT", "587"))

def generate_otp():
    """Generate an OTP and log it."""
    otp = str(random.randint(100000, 999999))
    timestamp = time.time()
    mfa_logger.info(f"Generated OTP: {otp} at {timestamp}")
    return otp, timestamp

def generate_totp_secret():
    """Generate a TOTP secret and log it."""
    secret = pyotp.random_base32()
    mfa_logger.info(f"Generated TOTP secret: {secret}")
    return secret

def get_totp(secret):
    """Get the current TOTP code and log it."""
    totp = pyotp.TOTP(secret)
    code = totp.now()
    mfa_logger.info(f"Generated TOTP code: {code} for secret {secret}")
    return code

def verify_totp(secret, totp_code):
    """Verify a TOTP code and log the result."""
    totp = pyotp.TOTP(secret)
    is_valid = totp.verify(str(totp_code).strip().replace(" ", ""), valid_window=1)
    mfa_logger.info(f"TOTP verification: {is_valid} (Received: {totp_code})")
    if not is_valid:
        mfa_logger.warning(f"Invalid TOTP code received: {totp_code}")
    return is_valid

def send_otp_email(email, otp):
    """Send an OTP via email and log the action."""
    try:
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        if not SMTP_SENDER or not SMTP_PASSWORD:
            raise RuntimeError("SMTP credentials are not configured.")

        message = MIMEMultipart()
        message['From'] = SMTP_SENDER
        message['To'] = email
        message['Subject'] = "Your OTP of Federated Learning Server"
        message['X-Priority'] = '1'
        message['X-MSMail-Priority'] = 'High'
        message['Importance'] = 'high'
        body = f"Your OTP is: {otp} (Valid for 5 minutes)"
        message.attach(MIMEText(body, 'plain'))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
          server.starttls()
          server.login(SMTP_SENDER, SMTP_PASSWORD)
          server.sendmail(SMTP_SENDER, email, message.as_string())
        mfa_logger.info(f"Sent OTP via email to {email}: {otp}")
    except Exception as e:
        mfa_logger.error(f"Failed to send OTP email to {email}: {e}")
        raise

def send_otp_sms(phone, otp):
    """Send an OTP via SMS and log the action."""
    try:
        if not TWILIO_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE:
            raise RuntimeError("Twilio credentials are not configured.")
        client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(body=f"Your OTP is: {otp} (Valid for 5 minutes)", from_=TWILIO_PHONE, to=phone)
        mfa_logger.info(f"Sent OTP via SMS to {phone}: {otp}")
    except Exception as e:
        mfa_logger.error(f"Failed to send OTP SMS to {phone}: {e}")
        raise

def verify_otp(stored_otp, stored_timestamp, received_otp):
    """Verify an OTP and log the result."""
    current_time = time.time()
    is_valid = stored_otp == received_otp and (current_time - stored_timestamp) <= 300
    mfa_logger.info(f"OTP verification: {is_valid} (Stored: {stored_otp}, Received: {received_otp})")
    if not is_valid:
        mfa_logger.warning(f"Invalid or expired OTP received: {received_otp}")
    return is_valid

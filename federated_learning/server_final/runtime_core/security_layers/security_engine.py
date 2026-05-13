import logging
from logging.handlers import RotatingFileHandler
from logging_manager import get_logger
# Logger setup
# se_logger = logging.getLogger("SecurityEngine")
# se_logger.setLevel(logging.DEBUG)
# se_handler = RotatingFileHandler("security_engine.log", maxBytes=5*1024*1024, backupCount=5)
# se_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
# se_handler.setFormatter(se_formatter)
# se_logger.addHandler(se_handler)
# se_logger.addHandler(logging.StreamHandler())
se_logger = get_logger("SecurityEngine","Security_engine.log")
se_logger.addHandler(logging.getLogger("MasterLog").handlers[0])

def destroy_session(token, reason):
    """Destroy a session and log the action."""
    se_logger.info(f"Session destroyed for token {token}: {reason}")
    return None

def prompt_reauthentication(token, reason):
    """Prompt re-authentication and log the action."""
    se_logger.info(f"Prompting re-authentication for token {token}: {reason}")
    return "REAUTH_REQUIRED"
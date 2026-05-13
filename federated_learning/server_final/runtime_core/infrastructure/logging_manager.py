import logging
import os
from logging.handlers import RotatingFileHandler
import threading
import uuid
from functools import partial
from typing import Optional, Callable

# Thread-local storage for request-specific logging
thread_local = threading.local()

# Custom filter for master logs
class MasterLogFilter(logging.Filter):
    def filter(self, record):
        record.file_name = os.path.basename(record.pathname)
        record.request_id = getattr(thread_local, 'request_id', 'N/A')
        return True

class LoggingManager:
    """Singleton class to manage logging across multiple files/modules"""
    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls, log_dir: str = "logs"):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    # Initialize here since __init__ won't be called again
                    cls._instance.log_dir = log_dir
                    cls._instance.loggers = {}
                    cls._instance.master_logger = None
                    cls._instance._setup_logging()
                    cls._instance._initialized = True
        return cls._instance

    def __init__(self, log_dir: str = "logs"):
        # Only initialize if not already done via __new__
        if not self._initialized:
            with self._lock:  # 🔒 Lock only this critical section
                
                self.log_dir = log_dir
                self.loggers = {}
                self.master_logger = None
                self._setup_logging() 
                # ✅ Prevent multiple handlers on master_logger
                if self.master_logger and not self.master_logger.handlers:
                    file_handler = RotatingFileHandler(
                        os.path.join(self.log_dir, "app.log"), maxBytes=5 * 1024 * 1024, backupCount=5
                    )
                    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
                    file_handler.setLevel(logging.INFO)
    
                    console_handler = logging.StreamHandler()
                    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
                    console_handler.setLevel(logging.INFO)
    
                    self.master_logger.addHandler(file_handler)
                    self.master_logger.addHandler(console_handler)
    
                self._initialized = True

    def _setup_logging(self):
        """Initialize master logger and directory"""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        # Master logger configuration
        MASTER_FORMAT = '%(asctime)s - %(levelname)s - %(file_name)s - %(request_id)s - %(message)s'
        DEFAULT_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

        self.master_logger = self._create_logger(
            name="MasterLog",
            filename="master_log.log",
            format_string=MASTER_FORMAT,
            master_filter=True
        )

        # Default server logger (can be overridden by specific modules)
        self.loggers['server'] = self._create_logger(
            name="ServerLog",
            filename="server_log.log",
            format_string=DEFAULT_FORMAT
        )

    def _create_logger(self, name: str, filename: str, format_string: str, 
                      max_bytes: int = 5*1024*1024, backup_count: int = 5,
                      master_filter: bool = False) -> logging.Logger:
        """Create and configure a logger"""
        logger = logging.getLogger(name)
        if logger.handlers:  # Prevent duplicate handlers
            return logger
            
        logger.setLevel(logging.DEBUG)
        
        file_handler = RotatingFileHandler(
            os.path.join(self.log_dir, filename),
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        console_handler = logging.StreamHandler()
        
        formatter = logging.Formatter(format_string)
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        if master_filter:
            file_handler.addFilter(MasterLogFilter())
            
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        # Propagate critical events to master logger
        if not master_filter:
            logger.addHandler(self.master_logger.handlers[0])  # Share master file handler for critical logs
        
        return logger

    def get_logger(self, name: str, filename: Optional[str] = None) -> logging.Logger:
        """Get or create a logger for a specific module/file"""
        if name not in self.loggers:
            filename = filename or f"{name.lower()}_log.log"
            self.loggers[name] = self._create_logger(
                name=name,
                filename=filename,
                format_string='%(asctime)s - %(levelname)s - %(message)s'
            )
        return self.loggers[name]

    def get_master_logger(self) -> logging.Logger:
        """Get the master logger for high-priority events"""
        return self.master_logger

    def log_to_master(self, level: int, message: str, request_id: Optional[str] = None):
        """Explicitly log a message to the master log"""
        with RequestContext(request_id or str(uuid.uuid4())):
            self.master_logger.log(level, message)

# Request context manager
class RequestContext:
    def __init__(self, request_id: str):
        self.request_id = request_id
    
    def __enter__(self):
        thread_local.request_id = self.request_id
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(thread_local, 'request_id'):
            del thread_local.request_id

# Global instance
logger_manager = LoggingManager(log_dir="logs")

# Convenience functions
def get_logger(name: str, filename: Optional[str] = None) -> logging.Logger:
    return logger_manager.get_logger(name, filename)

def get_master_logger() -> logging.Logger:
    return logger_manager.get_master_logger()

def log_to_master(level: int, message: str, request_id: Optional[str] = None):
    logger_manager.log_to_master(level, message, request_id)

# Predefined logging levels for master log
master_info = partial(log_to_master, logging.INFO)
master_warning = partial(log_to_master, logging.WARNING)
master_error = partial(log_to_master, logging.ERROR)
master_critical = partial(log_to_master, logging.CRITICAL)
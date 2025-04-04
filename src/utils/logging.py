import logging
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure logging
def setup_logging():
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    log_file = f'logs/task_agent_{datetime.now().strftime("%Y%m%d")}.log'
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(levelname)s - %(message)s'
    )
    
    # Create file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(file_formatter)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)
    
    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Create logger instance
logger = setup_logging()

def log_task_creation(task_id, title):
    """Log task creation"""
    logger.info(f"Task created - ID: {task_id}, Title: {title}")

def log_task_estimation(task_id, estimated_duration, confidence):
    """Log task estimation"""
    logger.info(
        f"Task estimated - ID: {task_id}, "
        f"Duration: {estimated_duration} minutes, "
        f"Confidence: {confidence}"
    )

def log_task_scheduling(task_id, start_time, end_time):
    """Log task scheduling"""
    logger.info(
        f"Task scheduled - ID: {task_id}, "
        f"Start: {start_time}, End: {end_time}"
    )

def log_task_feedback(task_id, actual_duration, accuracy):
    """Log task feedback"""
    logger.info(
        f"Task feedback - ID: {task_id}, "
        f"Actual Duration: {actual_duration} minutes, "
        f"Accuracy: {accuracy}"
    )

def log_error(error_message, error_type=None):
    """Log error messages"""
    if error_type:
        logger.error(f"{error_type}: {error_message}")
    else:
        logger.error(error_message) 
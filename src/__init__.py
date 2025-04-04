from src.utils.config import validate_settings
from src.utils.database import init_db
from src.utils.logging import logger

def initialize_app():
    """Initialize the application"""
    try:
        # Validate settings
        validate_settings()
        logger.info("Settings validated successfully")
        
        # Initialize database
        init_db()
        logger.info("Database initialized successfully")
        
        # Create necessary directories
        import os
        os.makedirs("logs", exist_ok=True)
        os.makedirs(".chroma", exist_ok=True)
        
        logger.info("Application initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        return False 
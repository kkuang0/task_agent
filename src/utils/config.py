import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from src.utils.logging import logger

load_dotenv()

class Settings(BaseSettings):
    # Mistral Configuration
    MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "")
    
    # Google Calendar Configuration
    GOOGLE_CALENDAR_CREDENTIALS: str = os.getenv("GOOGLE_CALENDAR_CREDENTIALS", "")
    
    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./task_agent.db")
    
    # Vector Database Configuration
    CHROMA_DB_PATH: str = os.getenv("CHROMA_DB_PATH", ".chroma")
    
    # Application Settings
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Agent Settings
    PLANNER_AGENT_MODEL: str = "mistral-large-latest"
    ESTIMATOR_AGENT_MODEL: str = "mistral-large-latest"
    SCHEDULER_AGENT_MODEL: str = "mistral-small-latest"
    MEMORY_AGENT_MODEL: str = "mistral-small-latest"
    
    # Task Settings
    DEFAULT_TASK_PRIORITY: int = 3
    MAX_TASK_DURATION_MINUTES: int = 480  # 8 hours
    MIN_TASK_DURATION_MINUTES: int = 15
    
    # Feedback Settings
    FEEDBACK_REMINDER_HOURS: int = 24
    MIN_FEEDBACK_SAMPLES: int = 5
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create settings instance
settings = Settings()

def get_settings() -> Settings:
    """Get the application settings"""
    return settings

def validate_settings():
    """Validate that all required settings are present"""
    missing_settings = []
    
    if not settings.MISTRAL_API_KEY:
        missing_settings.append("MISTRAL_API_KEY")
    
    if not settings.GOOGLE_CALENDAR_CREDENTIALS:
        missing_settings.append("GOOGLE_CALENDAR_CREDENTIALS")
        logger.debug(f"Environment variables: {dict(os.environ)}")
        logger.debug(f"Current working directory: {os.getcwd()}")
        logger.debug(f"Files in directory: {os.listdir('.')}")
    
    if missing_settings:
        raise ValueError(
            f"Missing required settings: {', '.join(missing_settings)}. "
            "Please check your .env file."
        ) 
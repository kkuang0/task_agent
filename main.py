import asyncio
from src import initialize_app
from src.app import main
from src.utils.logging import logger

if __name__ == "__main__":
    # Initialize the application
    if not initialize_app():
        logger.error("Failed to initialize application. Exiting...")
        exit(1)
    
    # Run the Streamlit app
    try:
        main()
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        exit(1)
from email_manager import main_executor
from log_handler import logger

def main(request):
    logger.info("Starting cold email campaign execution")
    main_executor()
    return "Batch complete", 200


if __name__ == "__main__":
    main(None)  # For local testing, pass None or a mock request object
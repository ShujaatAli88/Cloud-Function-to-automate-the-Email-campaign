import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration class to hold environment variables."""
    PROJECT_ID = os.getenv("PROJECT_ID")
    DATASET = os.getenv("DATASET")
    TABLE = os.getenv("TABLE")
    SMARTLEAD_CAMPAIGN_ID = os.getenv("SMARTLEAD_CAMPAIGN_ID")
    SMARTLEAD_API_KEY = os.getenv("SMARTLEAD_API_KEY")
    EMAIL_LIMIT = int(os.getenv("EMAIL_LIMIT"))
    WAIT_SECONDS = int(os.getenv("WAIT_SECONDS"))
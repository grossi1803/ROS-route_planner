import os
from dotenv import load_dotenv
import urllib

# Explicitly load the .env file using its full path
load_dotenv('/var/www/route_planner/.env')

class Config:
    """Configuration settings loaded from environment variables."""
    
    # MongoDB Settings
    MONGO_URI = os.getenv("MONGO_URI")
    MONGO_DB = os.getenv("MONGO_DB")

    #Settings
    TYPE_OF_MAP = os.getenv("TYPE_OF_MAP")
    SIMPLIFY = os.getenv("SIMPLIFY")
    TRUNCATE_EDGE = os.getenv("TRUNCATE_EDGE")
    RETAIN = os.getenv("RETAIN")
    # Logging Settings
    LOG_DIR = os.getenv("LOG_DIR", "/var/www/route_planner/logs")
    LOG_FILE = os.path.join(LOG_DIR, os.getenv("LOG_FILE", "app.log"))
    
    # Cache Settings
    CUSTOM_CACHE_DIR = os.getenv("CUSTOM_CACHE_DIR", "/var/www/route_planner/custom_cache")
    
    # Flask Settings
    FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
    FLASK_PORT = int(os.getenv("FLASK_PORT", 4000))
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() in ("true", "1")

# Ensure directories exist
os.makedirs(Config.LOG_DIR, exist_ok=True)
os.makedirs(Config.CUSTOM_CACHE_DIR, exist_ok=True)

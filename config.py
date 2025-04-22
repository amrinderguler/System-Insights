import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

class Config:
    # MongoDB Configuration
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DB_NAME = os.getenv("DB_NAME", "system_monitor")
    COLLECTION_NAME = os.getenv("COLLECTION_NAME", "metrics")
    
    # Redis Configuration
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
    REDIS_URL = os.getenv("REDIS_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
    
    # Queue Configuration
    QUEUE_NAME = os.getenv("QUEUE_NAME", "monitor_tasks")
    RESULT_TTL = int(os.getenv("RESULT_TTL", "86400"))  # 24 hours
    
    # Monitoring Parameters
    MIN_INTERVAL = int(os.getenv("MIN_INTERVAL", "30"))  # seconds
    MAX_INTERVAL = int(os.getenv("MAX_INTERVAL", "600"))  # seconds
    RETRAIN_CYCLES = int(os.getenv("RETRAIN_CYCLES", "10"))
    
    # Path Configuration
    BASE_DIR = Path(__file__).parent.parent
    MODEL_DIR = BASE_DIR / "models"
    LOG_DIR = BASE_DIR / "logs"
    
    # Create required directories
    MODEL_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
    
    @classmethod
    def validate(cls):
        """Validate essential configurations"""
        required = ['MONGO_URI', 'REDIS_URL']
        for var in required:
            if not getattr(cls, var):
                raise ValueError(f"Missing required configuration: {var}")

# Initialize and validate config
config = Config()
config.validate()
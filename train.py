import eventlet
# This MUST be at the very top of the file.
eventlet.monkey_patch()

import logging
import os
import pickle
import pandas as pd
from celery import Celery
from pymongo import MongoClient  # Use the standard synchronous client
from trend_model import TrendForecaster

# Import the shared Celery app instance
from celery_app import app

logger = logging.getLogger(__name__)

@app.task(name="train.run_train_task")
def run_train_task(mac_address: str):
    """
    Celery task that performs the model training synchronously.
    """
    logger.info(f"Celery task started for MAC address: {mac_address}")
    try:
        # Directly call the new synchronous function
        train_model_and_save_sync(mac_address)
    except Exception as e:
        logger.error(f"An error occurred in the celery task: {e}", exc_info=True)
        return "Task failed"

def train_model_and_save_sync(mac_address: str):
    """
    Synchronous version of the training logic for the Celery worker.
    """
    from monitor import SystemMonitor # Keep this local import to prevent circular dependencies

    logger.info(f"Starting model training for MAC address: {mac_address}")
    
    # --- Database Connection (Synchronous) ---
    client = None
    try:
        mongo_uri = os.getenv("MONGO_URI")
        db_name = os.getenv("DB_NAME")
        collection_name = os.getenv("COLLECTION_NAME")
        
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        client.admin.command('ping') # Verify connection
        collection = client[db_name][collection_name]
        logger.info("Worker successfully connected to MongoDB.")
    except Exception as e:
        logger.error(f"Worker failed to connect to MongoDB: {e}")
        if client:
            client.close()
        return

    # --- Data Fetching and Training (Synchronous) ---
    try:
        min_data_points = 20
        cursor = collection.find(
            {'mac_address': mac_address},
            {'_id': 0, 'timestamp': 1, 'cpu.cpu_usage': 1, 'cpu.cpu_system': 1, 
             'memory.memory_usage_percent': 1, 'disk.total_read_mb': 1,
             'network.packets_sent': 1, 'processes.total_processes': 1}
        ).sort("timestamp", 1)

        documents = list(cursor)

        if len(documents) < min_data_points:
            logger.warning(f"Not enough data points ({len(documents)}) for training.")
            return

        historical = pd.json_normalize(documents).ffill().bfill()
        if historical.empty:
            logger.warning("No valid data for training after processing.")
            return
            
        forecaster = TrendForecaster(
            df=historical,
            target='cpu.cpu_usage',
            regressors=['cpu.cpu_system', 'memory.memory_usage_percent', 'disk.total_read_mb', 
                        'network.packets_sent', 'processes.total_processes']
        )
        
        sanitized_mac = TrendForecaster.sanitize_mac_address(mac_address)
        model_path = os.path.join('models', f"{sanitized_mac}_trend_model.pkl")
        os.makedirs('models', exist_ok=True)
        
        with open(model_path, 'wb') as f:
            pickle.dump(forecaster, f)
            
        logger.info(f"Successfully trained and saved model to {model_path}")

    except Exception as e:
        logger.error(f"Error during model training: {e}", exc_info=True)
    finally:
        if client:
            client.close()
from redis import Redis
from rq import Queue
from config import config
from logging_setup import logger
from retrain import retrain_model

redis_conn = Redis.from_url("redis://localhost:6379/0")
q = Queue(connection=redis_conn)

def enqueue_retrain(mac_address=None):
    """
    Enqueue a retrain job for a specific MAC address
    Args:
        mac_address: Optional MAC address, prompts if not provided
    """
    try:
        if mac_address is None:
            mac_address = input("Enter MAC address to retrain model for: ")
        
        q.enqueue(retrain_model, mac_address)
        
        logger.info(f"Enqueued retrain job for {mac_address}")
        print(f"🔧 Retrain job queued for {mac_address}")
        
    except Exception as e:
        logger.error(f"Failed to queue retrain job: {str(e)}")
        print(f"❌ Error: {str(e)}")
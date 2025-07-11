from redis import Redis
from rq import Queue
from config import config
from logging_setup import logger

def enqueue_retrain(mac_address=None):
    """
    Enqueue a retrain job for a specific MAC address
    Args:
        mac_address: Optional MAC address, prompts if not provided
    """
    try:
        if mac_address is None:
            mac_address = input("Enter MAC address to retrain model for: ")
        
        q = Queue(connection=Redis.from_url(config.REDIS_URL))
        q.enqueue('tasks.retrain_prophet', mac_address)
        
        logger.info(f"Enqueued retrain job for {mac_address}")
        print(f"🔧 Retrain job queued for {mac_address}")
        
    except Exception as e:
        logger.error(f"Failed to queue retrain job: {str(e)}")
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    enqueue_retrain()
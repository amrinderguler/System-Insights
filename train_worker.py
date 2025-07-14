import os
import asyncio
from redis import Redis
from rq import Queue, Worker, Connection
from rq.job import Job
from monitor import SystemMonitor
import logging

# Windows-specific setup
if os.name == 'nt':
    from rq.worker import Worker
    import warnings
    warnings.filterwarnings("ignore", message="Windows is only supported with the 'threading' worker class")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def train_model_task(mac_address: str):
    """Async task that trains the model"""
    try:
        monitor = SystemMonitor()
        monitor.collection = await monitor._connect_to_mongodb()
        if monitor.collection is None:
            raise Exception("Failed to connect to MongoDB")
        return await monitor.train_model_and_save(mac_address)
    except Exception as e:
        logger.error(f"Training failed: {str(e)}")
        raise

def run_train_task(job: Job):
    """Wrapper that runs the async task in an event loop"""
    try:
        mac_address = job.args[0] if isinstance(job.args, (list, tuple)) else job.args
        logger.info(f"Starting training for {mac_address}")
        return asyncio.run(train_model_task(mac_address))
    except Exception as e:
        logger.error(f"Task execution failed: {str(e)}")
        raise

if __name__ == "__main__":
    redis_conn = Redis()
    
    with Connection(redis_conn):
        # Windows-specific worker class
        if os.name == 'nt':
            worker = Worker(['train_queue'], worker_class='rq.worker.ThreadWorker')
        else:
            worker = Worker(['train_queue'])
        
        worker.work()
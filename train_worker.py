import os
import asyncio
from redis import Redis
from rq import Queue
from monitor import SystemMonitor  

async def train_model_task(mac_address: str):
    """Task that will be run by the RQ worker"""
    monitor = SystemMonitor()
    monitor.collection = await monitor._connect_to_mongodb()
    return await monitor.train_model_and_save(mac_address)

def run_train_task(mac_address: str):
    """Wrapper that runs the async task in an event loop"""
    return asyncio.run(train_model_task(mac_address))

if __name__ == "__main__":
    # Start worker if run directly
    q = Queue("train_queue", connection=Redis())
    worker = q.run(run_train_task)

    # Start worker
    with Connection(redis_conn):
        worker = Worker([queue])
        worker.work()
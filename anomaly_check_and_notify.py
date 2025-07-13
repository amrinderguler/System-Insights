import os
import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from anomaly_detector import detect_anomalies, format_anomaly_report_html, send_notification
from dotenv import load_dotenv
from redis.asyncio import Redis as AsyncRedis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('anomaly_worker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")
IT_SUPPORT_EMAIL = os.getenv("IT_SUPPORT_EMAIL", "your-it-support@example.com")
REDIS_URL = os.getenv("REDIS_URL")

def flatten_metrics(record):
    return {
        "cpu_util": record.get("cpu", {}).get("cpu_usage"),
        "amb_temp": record.get("system_health", {}).get("amb_temp"),
        "cpu_watts": record.get("cpu", {}).get("cpu_watts"),
        "dimm_watts": record.get("memory", {}).get("dimm_watts"),
        "timestamp": record.get("timestamp"),
        "time_str": record.get("timestamp").strftime("%Y-%m-%d, %H:%M") if record.get("timestamp") else ""
    }

async def push_all_macs(redis, collection):
    macs = await collection.distinct("mac_address")
    logger.info(f"Found {len(macs)} MAC addresses in MongoDB to push to queue.")
    for mac in macs:
        await redis.lpush("train_queue", mac)
        logger.info(f"Pushed {mac} to train_queue")
    logger.info("All MAC addresses pushed to Redis queue.")

async def anomaly_worker():
    logger.info("Starting anomaly worker...")
    redis = await AsyncRedis.from_url(REDIS_URL)
    client = AsyncIOMotorClient(MONGO_URI)
    collection = client[DB_NAME][COLLECTION_NAME]
    logger.info("Connected to MongoDB and Redis. Waiting for MAC addresses in Redis queue...")

    PUSH_INTERVAL = 600  # seconds (10 minutes)
    last_push = 0

    while True:
        try:
            now = asyncio.get_event_loop().time()
            if now - last_push > PUSH_INTERVAL:
                await push_all_macs(redis, collection)
                last_push = now

            mac_address = await redis.lpop("train_queue")
            if not mac_address:
                logger.debug("No MAC address in queue. Sleeping for 2 seconds.")
                await asyncio.sleep(2)
                continue
            mac_address = mac_address.decode() if isinstance(mac_address, bytes) else mac_address
            logger.info(f"Processing MAC address: {mac_address}")
            cursor = collection.find({'mac_address': mac_address}).sort("timestamp", -1).limit(30)
            records = await cursor.to_list(length=30)
            if not records:
                logger.warning(f"No records found for MAC address: {mac_address}")
                continue
            flattened_records = [flatten_metrics(r) for r in records]
            anomalies = detect_anomalies(flattened_records, server_serial=mac_address)

            # --- Filter out already reported anomalies ---
            if anomalies:
                reported_key = f"reported:{mac_address}"
                # Get all reported timestamps for this MAC
                reported_timestamps = await redis.smembers(reported_key)
                # Convert bytes to str if needed
                reported_timestamps = set(ts.decode() if isinstance(ts, bytes) else ts for ts in reported_timestamps)
                # Only keep anomalies with new timestamps
                new_anomalies = [a for a in anomalies if a["time_str"] not in reported_timestamps]
                if new_anomalies:
                    median_baselines = {}
                    for metric in ["cpu_util", "amb_temp", "cpu_watts", "dimm_watts"]:
                        vals = [r[metric] for r in flattened_records if r[metric] is not None]
                        if vals:
                            median_baselines[metric] = sorted(vals)[len(vals)//2]
                    report = format_anomaly_report_html(new_anomalies, median_baselines, server_serial=mac_address)
                    await send_notification(IT_SUPPORT_EMAIL, f"System Anomaly Detected: {mac_address}", report)
                    logger.info(f"Anomaly detected and email sent for {mac_address}")
                    # Mark these timestamps as reported
                    if new_anomalies:
                        await redis.sadd(reported_key, *[a["time_str"] for a in new_anomalies])
                else:
                    logger.info(f"No new anomalies to report for {mac_address}")
            else:
                logger.info(f"No significant anomalies detected for {mac_address}")
        except Exception as e:
            logger.error(f"Error in anomaly_worker loop: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(anomaly_worker())
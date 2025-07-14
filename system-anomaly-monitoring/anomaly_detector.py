import os
import smtplib
import logging
from collections import Counter
from typing import List, Dict, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

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

def detect_anomalies(records: List[Dict[str, Any]], server_serial: str = None) -> List[Dict[str, Any]]:
    METRIC_KEYS = ["cpu_util", "amb_temp", "cpu_watts", "dimm_watts"]
    anomalies = []
    median_baselines = {}
    if not records or len(records) < 3:
        logger.warning("Not enough records to detect anomalies.")
        return []
    for metric in METRIC_KEYS:
        values = []
        timestamps = []
        for record in records:
            val = record.get(metric)
            if val is not None:
                values.append(float(val))
                timestamps.append(record.get("time_str") or str(record.get("timestamp")))
        if len(values) < 3:
            logger.info(f"Not enough values for metric {metric} to detect anomalies.")
            continue
        median = sorted(values)[len(values)//2]
        deviations = [abs(x - median) for x in values]
        mad = sorted(deviations)[len(deviations)//2]
        if mad == 0:
            logger.info(f"MAD is zero for metric {metric}, skipping anomaly detection for this metric.")
            continue
        base_threshold = 3.5
        threshold = base_threshold
        if len(values) < 10:
            threshold = 3.0
        elif len(values) > 100:
            threshold = base_threshold + (len(values) / 500)
        modified_z_scores = [0.6745 * (x - median) / mad for x in values]
        for i, score in enumerate(modified_z_scores):
            if abs(score) > threshold:
                anomalies.append({
                    "value": values[i],
                    "z_score": round(score, 2),
                    "metric": metric,
                    "server": server_serial,
                    "time_str": timestamps[i]
                })
        median_baselines[metric] = median
    logger.info(f"Detected {len(anomalies)} anomalies for server {server_serial}.")
    return anomalies

def format_anomaly_report_html(anomalies: List[Dict[str, Any]], median_baselines: Dict[str, float], server_serial: str = None) -> str:
    if not anomalies:
        logger.info(f"No significant anomalies detected for server {server_serial}.")
        return "<b>No significant anomalies detected.</b>"
    critical = [a for a in anomalies if abs(a["z_score"]) > 5]
    major = [a for a in anomalies if 3.5 < abs(a["z_score"]) <= 5]
    anomaly_hours = [
        a.get('time_str', '').split(' ')[1][:2]
        for a in anomalies
        if 'time_str' in a and a['time_str'] and ' ' in a['time_str']
    ]
    hour_dist = Counter(anomaly_hours).most_common(3)
    output = []
    output.append(f"<h2>📊Anomaly Report for server <b>{server_serial}</b></h2>")
    output.append("<h3>🔍 Normal Ranges (median values):</h3><ul>")
    for metric, median in median_baselines.items():
        output.append(f"<li><b>{metric}</b>: {median}</li>")
    output.append("</ul>")
    if critical:
        output.append("<h3 style='color:red;'>🚨 CRITICAL ANOMALIES (z-score &gt; 5):</h3><ul>")
        for a in critical[:5]:
            output.append(
                f"<li><b>{a['server']}</b> | <b>{a['metric']}</b> = {a['value']} "
                f"(z-score: {a['z_score']}) at {a['time_str']}</li>"
            )
        output.append("</ul>")
    if major:
        output.append("<h3 style='color:orange;'>⚠️ MAJOR ANOMALIES (3.5 &lt; z-score ≤ 5):</h3><ul>")
        for a in major[:5]:
            output.append(
                f"<li><b>{a['server']}</b> | <b>{a['metric']}</b> = {a['value']} "
                f"(z-score: {a['z_score']}) at {a['time_str']}</li>"
            )
        output.append("</ul>")
    if hour_dist:
        output.append("<h3>⏰ Frequent Anomaly Times:</h3><ul>")
        for hour, count in hour_dist:
            output.append(f"<li>{hour}:00 - {count} anomalies</li>")
        output.append("</ul>")
    output.append("<h3>🔧 Potential Investigation Paths:</h3><ul>")
    if 'cpu_watts' in median_baselines:
        output.append("<li>CPU Power Spikes: Check workload scheduler and cooling</li>")
    if 'amb_temp' in median_baselines:
        output.append("<li>Temp Fluctuations: Verify HVAC and rack airflow</li>")
    if 'dimm_watts' in median_baselines:
        output.append("<li>Memory Power: Run DIMM diagnostics</li>")
    output.append("</ul>")
    total_anomalies = len(critical) + len(major)
    output.append(f"<b>📈 Found {total_anomalies} significant anomalies</b>")
    logger.info(f"Formatted anomaly report for server {server_serial}.")
    return "\n".join(output)

async def send_notification(email_to: str, subject: str, body: str):
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    gmail_user = os.getenv("GMAIL_USER")
    gmail_pass = os.getenv("GMAIL_PASS") or os.getenv("GMAIL_PASSWORD")
    if not gmail_user or not gmail_pass:
        logger.critical("GMAIL_USER and GMAIL_PASS must be set in environment variables.")
        raise RuntimeError("GMAIL_USER and GMAIL_PASS must be set in environment variables.")
    msg = MIMEMultipart()
    msg["From"] = gmail_user
    msg["To"] = email_to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(gmail_user, gmail_pass)
        server.sendmail(gmail_user, email_to, msg.as_string())
        server.quit()
        logger.info(f"Notification email sent to {email_to} with subject '{subject}'.")
    except Exception as e:
        logger.error(f"Failed to send email: {e}", exc_info=True)

def flatten_metrics(record):
    return {
        "cpu_util": record.get("cpu", {}).get("cpu_usage"),
        "amb_temp": record.get("system_health", {}).get("amb_temp"),
        "cpu_watts": record.get("cpu", {}).get("cpu_watts"),
        "dimm_watts": record.get("memory", {}).get("dimm_watts"),
        "timestamp": record.get("timestamp"),
        "time_str": str(record.get("timestamp")) if record.get("timestamp") else ""
    }

async def anomaly_worker():
    MONGO_URI = os.getenv("MONGO_URI")
    DB_NAME = os.getenv("DB_NAME")
    COLLECTION_NAME = os.getenv("COLLECTION_NAME")
    REDIS_URL = os.getenv("REDIS_URL")
    IT_SUPPORT_EMAIL = os.getenv("IT_SUPPORT_EMAIL")
    redis = await AsyncRedis.from_url(REDIS_URL)
    mongo_client = AsyncIOMotorClient(MONGO_URI)
    collection = mongo_client[DB_NAME][COLLECTION_NAME]
    logger.info("Anomaly worker started. Waiting for MAC addresses in Redis queue...")
    while True:
        try:
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
            if anomalies:
                median_baselines = {}
                for metric in ["cpu_util", "amb_temp", "cpu_watts", "dimm_watts"]:
                    vals = [r[metric] for r in flattened_records if r[metric] is not None]
                    if vals:
                        median_baselines[metric] = sorted(vals)[len(vals)//2]
                report_html = format_anomaly_report_html(anomalies, median_baselines, server_serial=mac_address)
                await send_notification(IT_SUPPORT_EMAIL, f"System Anomaly Detected: {mac_address}", report_html)
                logger.info(f"Anomaly detected and email sent for {mac_address}")
            else:
                logger.info(f"No significant anomalies detected for {mac_address}")
        except Exception as e:
            logger.error(f"Error in anomaly_worker loop: {e}", exc_info=True)

if __name__ == "__main__":
    import asyncio
    asyncio.run(anomaly_worker())
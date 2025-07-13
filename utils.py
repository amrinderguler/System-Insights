def send_email_notification(subject: str, message: str, recipient: str) -> None:
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from dotenv import load_dotenv
    import os

    load_dotenv()
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient
    msg['Subject'] = subject

    msg.attach(MIMEText(message, 'plain'))

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            print("Email notification sent successfully.")
    except Exception as e:
        print(f"Failed to send email notification: {str(e)}")


async def check_for_anomalies(redis_queue: str, mongo_collection) -> None:
    import asyncio

    while True:
        try:
            # Check for messages in the Redis queue
            redis = await AsyncRedis.from_url("redis://localhost:6379")
            mac_address = await redis.lpop(redis_queue)

            if mac_address:
                # Fetch the latest metrics from MongoDB
                latest_metrics = await mongo_collection.find_one(
                    {'mac_address': mac_address},
                    sort=[('timestamp', -1)]
                )

                if latest_metrics:
                    # Call the anomaly detection function
                    anomalies = detect_anomalies(latest_metrics)

                    if anomalies:
                        subject = f"Anomaly Detected for {mac_address}"
                        message = f"Anomalies detected: {anomalies}"
                        recipient = os.getenv("IT_SUPPORT_EMAIL")
                        send_email_notification(subject, message, recipient)

            await asyncio.sleep(5)  # Wait before checking the queue again
        except Exception as e:
            print(f"Error in check_for_anomalies: {str(e)}")
            await asyncio.sleep(60)  # Wait before retrying in case of error
# System Insights

A comprehensive system monitoring and analytics tool that collects system metrics, performs trend analysis, detects anomalies, and dynamically adjusts monitoring intervals based on machine learning predictions.

## Overview

System Insights continuously monitors computer systems and collects detailed metrics about CPU usage, memory utilization, disk activity, network traffic, GPU performance, and process information. The collected data is stored in MongoDB for later analysis and visualization.

The application features intelligent monitoring with adaptive collection intervals—using machine learning to analyze trends and adjust monitoring frequency based on system behavior patterns. When a system becomes more active or shows unusual patterns, monitoring frequency increases automatically. The system also detects anomalies and can send email notifications to IT support.

## Features

- **Comprehensive System Monitoring**: Collects metrics for CPU, memory, disk, network, GPU, processes, and overall system health
- **Adaptive Monitoring**: Dynamically adjusts collection intervals based on system activity and predictive analytics
- **Machine Learning Integration**: Uses trend forecasting to predict optimal monitoring intervals
- **Anomaly Detection**: Detects anomalies in system metrics and sends email notifications
- **Distributed Architecture**: Supports Redis-based job queuing for model retraining and anomaly processing
- **Asynchronous Operation**: Utilizes Python's asyncio for efficient non-blocking operation
- **Persistent Storage**: Stores all metrics in MongoDB for historical analysis
- **Streamlit Dashboard**: Visualizes system metrics and trends

## Requirements

- Python 3.8+
- MongoDB
- Redis (for distributed job queue and anomaly detection)
- The following Python packages (see [`requirements.txt`](requirements.txt)):
  - `psutil`, `GPUtil`, `pymongo`, `pandas`, `numpy`, `prophet`, `redis`, `rq`, `python-dotenv`, `streamlit`, `plotly`, `pytest`, `loguru`, `aiofiles`, `uptime`, `motor`, `setuptools`, `load_dotenv`

## Installation

1. **Clone the repository:**
   ```bash
   git clone --single-branch --branch Model https://github.com/amrinderguler/System-Insights.git
   cd System-Insights
   ```

2. **Set up a virtual environment:**
   ```bash
   python -m venv myvenv
   source myvenv/bin/activate  # On Windows: myvenv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**

   Create a `.env` file in the root directory with the following variables (example values shown):

   ```
   MONGO_URI="mongodb+srv://<user>:<password>@<cluster>.mongodb.net/"
   DB_NAME="system_monitoring"
   COLLECTION_NAME="system_activity"
   REDIS_URL=redis://localhost:6379/0
   MIN_INTERVAL=30
   MAX_INTERVAL=180
   RETRAIN_CYCLES=10
   GMAIL_USER="your_gmail_address@gmail.com"
   GMAIL_PASS="your_gmail_app_password"
   IT_SUPPORT_EMAIL="your_it_support@example.com"
   ```

   - `GMAIL_USER` and `GMAIL_PASS` are required for sending anomaly notification emails.
   - `IT_SUPPORT_EMAIL` is the recipient for anomaly notifications.

5. **Install and start MongoDB** (if not already installed).

6. **Install and start Redis:**
   - **Windows**: Use WSL or Redis Windows port
   - **macOS**: `brew install redis && brew services start redis`
   - **Linux**: `sudo apt install redis-server && sudo service redis-server start`

## Usage

### Running the Monitor

```bash
python monitor.py
```

The system will start collecting metrics at default intervals and store them in MongoDB. If Redis is available, it will queue model retraining tasks.

### Running the Dashboard

```bash
streamlit run dashboard.py
```

### Retraining the Model

Retraining jobs are processed asynchronously using Redis and RQ. Make sure Redis is running, then start an RQ worker:

```bash
rq worker train_queue --name model_trainer
```

### Anomaly Detection Worker

To run the anomaly detection and notification worker:

```bash
python system-anomaly-monitoring/anomaly_check_and_notify.py
```

This process listens for MAC addresses in the Redis queue, checks for anomalies, and sends notifications.

## Configuration

The monitor and anomaly detection have several configurable parameters, set via `.env` or in [`config.py`](config.py):

- `MIN_INTERVAL`: Minimum collection interval in seconds (default: 30)
- `MAX_INTERVAL`: Maximum collection interval in seconds (default: 180)
- `RETRAIN_CYCLES`: Number of cycles before retraining (default: 10)
- `GMAIL_USER`/`GMAIL_PASS`: Credentials for sending email notifications
- `IT_SUPPORT_EMAIL`: Email address to notify on anomalies

## Project Structure

```
.env
config.py
dashboard.py
logging_setup.py
retrain.py
tasks.py
trend_model.py
requirements.txt
README.md
models/
system-anomaly-monitor/
   anomaly_check_and_notify.py
   anomaly_detector.py
   utils.py
```

## Architecture

System Insights consists of several components:

1. **SystemMonitor**: The main class responsible for metric collection and storage (see `monitor.py`)
2. **TrendForecaster**: Machine learning component for analyzing metrics and predicting optimal intervals ([`trend_model.py`](trend_model.py))
3. **Anomaly Detection**: Detects anomalies and sends notifications ([`system-anomaly-monitor/anomaly_detector.py`](system-anomaly-monitor/anomaly_detector.py))
4. **Dashboard**: Visualizes metrics ([`dashboard.py`](dashboard.py))
5. **MongoDB**: Backend database for storing metrics and system information
6. **Redis**: Queue system for distributed model training and anomaly processing

## Notes

- Ensure your Gmail account allows app passwords or "less secure apps" for email notifications.
- All environment variables must be set for the application to function correctly.
- For more details, see the code and comments in
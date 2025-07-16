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
  - **Distributed Architecture**: Utilizes **Celery** and **Redis** for a robust, cross-platform job queue
  - **Asynchronous Operation**: Utilizes Python's `asyncio` for efficient non-blocking operation
  - **Persistent Storage**: Stores all metrics in MongoDB for historical analysis
  - **Streamlit Dashboard**: Visualizes system metrics and trends

## Requirements

  - Python 3.8+
  - MongoDB
  - Redis
  - The following Python packages (see [`requirements.txt`](https://www.google.com/search?q=requirements.txt)):
      - `psutil`, `GPUtil`, `pymongo`, `pandas`, `numpy`, `prophet`, `python-dotenv`, `streamlit`, `plotly`, `pytest`, `loguru`, `aiofiles`, `uptime`, `motor`, `setuptools`
      - **`celery<5`**: The task queue framework.
      - **`eventlet`**: Required for running Celery workers on Windows.

## Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/amrinderguler/System-Insights.git
    cd System-Insights
    ```

2.  **Set up a virtual environment:**

    ```bash
    python -m venv myvenv
    source myvenv/bin/activate  # On Windows: myvenv\Scripts\activate
    ```

3.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

    *(Note: Ensure your `requirements.txt` has been updated to replace `rq` with `celery<5` and `eventlet`)*

4.  **Configure environment variables:**

    Create a `.env` file in the root directory with the following variables:

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

5.  **Install and start MongoDB** (if not already installed).

6.  **Install and start Redis** (if not already installed).

## Usage

The application consists of three main components that you need to run: the monitor, the background worker, and the dashboard.

### 1\. Running the Background Worker (Required)

The Celery worker processes all background tasks, including model retraining. It must be running for the system to function correctly.

**On Windows:**
You **must** use the `eventlet` pool for compatibility. Open a terminal, activate the virtual environment, and run:

```bash
celery -A celery_app worker --pool=eventlet -l info
```

**On Linux or macOS:**
You can use the default, more performant worker:

```bash
celery -A celery_app worker -l info
```

### 2\. Running the Monitor

This script starts the data collection process and sends tasks to the Celery worker. Open a **second terminal** and run:

```bash
python monitor.py
```

### 3\. Running the Dashboard

Open a **third terminal** to view the live metrics and trends:

```bash
streamlit run dashboard.py
```

## Project Structure

```
.env
celery_app.py
config.py
dashboard.py
logging_setup.py
monitor.py
train.py
trend_model.py
requirements.txt
README.md
models/
system-anomaly-monitor/
    anomaly_detector.py
    utils.py
```

## Architecture

System Insights consists of several components:

1.  **SystemMonitor**: The main class responsible for metric collection and storage (`monitor.py`).
2.  **TrendForecaster**: Machine learning component for analyzing metrics and predicting optimal intervals (`trend_model.py`).
3.  **Anomaly Detection**: Logic for detecting anomalies (`system-anomaly-monitor/`), executed as a background task.
4.  **Dashboard**: Visualizes metrics (`dashboard.py`).
5.  **MongoDB**: Backend database for storing metrics and system information.
6.  **Celery & Redis**: **Celery** is the distributed task queue framework, using **Redis** as the message broker to manage background jobs.

## Notes

  - Ensure your Gmail account allows app passwords or "less secure apps" for email notifications.
  - All environment variables must be set for the application to function correctly.

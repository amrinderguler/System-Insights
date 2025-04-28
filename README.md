# System Insights

A comprehensive system monitoring and analytics tool that collects system metrics, performs trend analysis, and dynamically adjusts monitoring intervals based on machine learning predictions.

## Overview

System Insights continuously monitors computer systems and collects detailed metrics about CPU usage, memory utilization, disk activity, network traffic, GPU performance, and process information. The collected data is stored in MongoDB for later analysis and visualization.

The application features intelligent monitoring with adaptive collection intervals - it uses machine learning to analyze trends and adjust monitoring frequency based on system behavior patterns. When a system becomes more active or shows unusual patterns, monitoring frequency increases automatically.

## Features

- **Comprehensive System Monitoring**: Collects metrics for CPU, memory, disk, network, GPU, processes, and overall system health
- **Adaptive Monitoring**: Dynamically adjusts collection intervals based on system activity and predictive analytics
- **Machine Learning Integration**: Uses trend forecasting to predict optimal monitoring intervals
- **Distributed Architecture**: Supports Redis-based job queuing for model retraining
- **Asynchronous Operation**: Utilizes Python's asyncio for efficient non-blocking operation
- **Persistent Storage**: Stores all metrics in MongoDB for historical analysis

## Requirements

- Python 3.8+
- MongoDB
- Redis (optional - for distributed model training)
- Dependencies listed in `requirements.txt`

## Installation

1. Clone the repository:
   ```bash
   git clone --single-branch --branch Model https://github.com/amrinderguler/System-Insights.git
   cd System-Insights
   ```

2. Set up a virtual environment:
   ```bash
   python -m venv myvenv
   source myvenv/bin/activate  # On Windows: myvenv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   Create a `.env` file with the following variables:
   ```
   MONGO_URI=mongodb://localhost:27017
   DB_NAME=system_metrics
   COLLECTION_NAME=metrics
   ```

5. Install and start MongoDB (if not already installed)

6. (Optional) Install and start Redis:
   - **Windows**: Use WSL or Redis Windows port
   - **macOS**: `brew install redis && brew services start redis`
   - **Linux**: `sudo apt install redis-server && sudo service redis-server start`

## Usage

### Running the Monitor

```bash
python monitor.py
```

The system will start collecting metrics at default intervals and store them in MongoDB. If Redis is available, it will queue model retraining tasks.

### Configuration

The monitor has several configurable parameters:

- `min_data_points_for_training`: Minimum data points required before model training (default: 20)
- `min_interval`: Minimum collection interval in seconds (default: 30)
- `max_interval`: Maximum collection interval in seconds (default: 600)
- `default_interval`: Default collection interval in seconds (default: 300)

These can be modified in the `SystemMonitor` class initialization.

## Architecture

System Insights consists of several components:

1. **SystemMonitor**: The main class responsible for metric collection and storage
2. **TrendForecaster**: Machine learning component for analyzing metrics and predicting optimal intervals
3. **MongoDB**: Backend database for storing metrics and system information
4. **Redis**: Optional queue system for distributed model training

## Troubleshooting

### Redis Connection Error

If you see the error `Failed to queue retrain: Error 22 connecting to localhost:6379`, Redis is either not installed or not running. You can:

1. Install and start Redis
2. Modify the script to handle Redis failures gracefully
3. Implement an alternative queueing mechanism

### MongoDB Connection Issues

If MongoDB connection fails, the monitor will log errors and retry. Ensure MongoDB is installed and running correctly.

## Future Enhancements

- Web dashboard for metric visualization
- Alerting system for anomaly detection
- Cross-system correlation analysis
- Support for containerized environments
- Remote monitoring capabilities

## License

[MIT License](LICENSE)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

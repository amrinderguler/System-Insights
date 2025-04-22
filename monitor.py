import psutil
import platform
import socket
import datetime
import uuid
import GPUtil
from uptime import uptime
import time
from pymongo import MongoClient
import os
import pickle
import logging
from typing import Optional, Dict, Any, List
from collections import defaultdict
from dotenv import load_dotenv
import pandas as pd
import threading
import queue
from trend_model import TrendForecaster
import aiofiles
from aiouptime import uptime
import asyncio
from aioredis import Redis as AsyncRedis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('system_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

# MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")

class SystemMonitor:
    def __init__(self):
        self.collection = self._connect_to_mongodb()
        self.system_id = socket.gethostname()
        self.mac_address = self._get_mac_address()
        self.system_info = self._get_system_info()
        self.min_data_points_for_training = 20
        self.min_interval = 30
        self.max_interval = 600
        self.default_interval = 300
        self.is_windows = platform.system() == 'Windows'
        logger.debug("SystemMetricsCollector initialized")

    async def _connect_to_mongodb(self) -> Optional[MongoClient]:
        """Connect to MongoDB with retry logic"""
        max_retries = 3
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                client = MongoClient(
                    MONGO_URI,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=10000,
                    socketTimeoutMS=10000,
                    retryWrites=True,
                    retryReads=True
                )
                await client.admin.command('ping')
                logger.info("Successfully connected to MongoDB")
                return client[DB_NAME][COLLECTION_NAME]
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed to connect to MongoDB: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)

                    continue
                logger.error("Failed to connect to MongoDB after multiple attempts")
                return None

    def _get_mac_address(self) -> str:
        """Get system MAC address with fallback"""
        try:
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                          for elements in range(0, 2*6, 8)][::-1])
            if not mac or mac == "00:00:00:00:00:00":
                raise ValueError("Invalid MAC address")
            return mac
        except Exception as e:
            logger.warning(f"Could not get MAC address: {str(e)}. Using hostname as fallback.")
            return f"hostname_{socket.gethostname()}"

    def _get_network_interfaces(self) -> Dict[str, Any]:
        try:
            interfaces = psutil.net_if_addrs()
            net_info = {}
            for iface, addrs in interfaces.items():
                net_info[iface] = [
                    {"family": str(addr.family), "address": addr.address}
                    for addr in addrs if addr.family.name in ["AF_INET", "AF_PACKET"]
                ]
            return net_info
        except Exception as e:
            logger.error(f"Error collecting network info: {str(e)}")
            return {}


    def _get_system_info(self) -> Dict[str, Any]:
        """Collect comprehensive system information."""
        try:
            return {
                "system_id": self.system_id,
                "mac_address": self.mac_address,
                "os": platform.system(),
                "os_version": platform.version(),
                "kernel_version": platform.release(),
                "architecture": platform.architecture()[0],
                "processor": platform.processor(),
                "cpu_cores_physical": psutil.cpu_count(logical=False),
                "cpu_cores_logical": psutil.cpu_count(logical=True),
                "ram_size_gb": round(psutil.virtual_memory().total / (1024 ** 3), 2),
                "disks": self._get_disk_info(),
                "network_interfaces": self._get_network_interfaces(),
                "initial_timestamp": datetime.datetime.utcnow(),
                "python_version": platform.python_version(),
                "hostname": socket.gethostname(),
                "fqdn": socket.getfqdn()
            }
        except Exception as e:
            logger.error(f"Error getting system info: {str(e)}")
            return {
                "system_id": self.system_id,
                "mac_address": self.mac_address,
                "error": f"System info collection failed: {str(e)}"
            }

    def _get_disk_info(self) -> List[Dict[str, Any]]:
        """Get detailed disk information"""
        disks = []
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disk_info = {
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                    "total_gb": round(usage.total / (1024 ** 3), 2),
                    "read_only": 'ro' in partition.opts.split(',')
                }
                disks.append(disk_info)
            except Exception as e:
                logger.warning(f"Could not get disk info for {partition.mountpoint}: {str(e)}")
                continue
        return disks

    def _get_network_interfaces(self) -> List[Dict[str, Any]]:
        """Get network interface information"""
        interfaces = []
        try:
            for name, addrs in psutil.net_if_addrs().items():
                interface_info = {
                    "name": name,
                    "addresses": [addr.address for addr in addrs],
                    "is_up": False
                }
                
                try:
                    stats = psutil.net_if_stats().get(name)
                    if stats:
                        interface_info.update({
                            "is_up": stats.isup,
                            "speed_mbps": stats.speed,
                            "mtu": stats.mtu
                        })
                except Exception:
                    pass
                
                interfaces.append(interface_info)
        except Exception as e:
            logger.warning(f"Could not get network interfaces: {str(e)}")
        return interfaces

    async def _get_cpu_metrics_async(self) -> Dict[str, Any]:
        """Get CPU metrics asynchronously"""
        # For CPU intensive or blocking operations, use asyncio.to_thread
        return await asyncio.to_thread(self._get_cpu_metrics)

    def _get_cpu_metrics(self) -> Dict[str, Any]:
        """Get CPU metrics"""
        metrics = {}
        try:
            cpu_times = psutil.cpu_times_percent(interval=1)
            metrics.update({
                "cpu_usage": psutil.cpu_percent(interval=1),
                "cpu_user": cpu_times.user,
                "cpu_system": cpu_times.system,
                "cpu_idle": cpu_times.idle,
                "cpu_cores_usage": psutil.cpu_percent(interval=1, percpu=True)
            })
            
            if hasattr(psutil, 'cpu_freq'):
                freq = psutil.cpu_freq()
                if freq:
                    metrics.update({
                        "cpu_frequency_mhz": freq.current,
                        "cpu_frequency_min_mhz": freq.min,
                        "cpu_frequency_max_mhz": freq.max
                    })
            
            if hasattr(psutil, "getloadavg"):
                load_avg = psutil.getloadavg()
                metrics.update({
                    "load_1min": load_avg[0],
                    "load_5min": load_avg[1],
                    "load_15min": load_avg[2]
                })
                
        except Exception as e:
            logger.error(f"Error getting CPU metrics: {str(e)}")
            metrics["error"] = f"CPU metrics collection failed: {str(e)}"
        
        return metrics

    async def _get_memory_metrics_async(self) -> Dict[str, Any]:
        """Get memory metrics asynchronously"""
        return await asyncio.to_thread(self._get_memory_metrics)

    def _get_memory_metrics(self) -> Dict[str, Any]:
        """Get memory metrics"""
        metrics = {}
        try:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            metrics.update({
                "memory_usage_percent": mem.percent,
                "memory_used_gb": round(mem.used / (1024 ** 3), 2),
                "memory_available_gb": round(getattr(mem, 'available', mem.free) / (1024 ** 3), 2),
                "swap_usage_percent": swap.percent,
                "swap_used_gb": round(swap.used / (1024 ** 3), 2)
            })
            
        except Exception as e:
            logger.error(f"Error getting memory metrics: {str(e)}")
            metrics["error"] = f"Memory metrics collection failed: {str(e)}"
        
        return metrics
    
    async def _get_disk_metrics_async(self) -> Dict[str, Any]:
        """Get disk metrics asynchronously"""
        return await asyncio.to_thread(self._get_disk_metrics)

    def _get_disk_metrics(self) -> Dict[str, Any]:
        """Get disk metrics"""
        disk_metrics = {"partitions": []}
        try:
            disk_io = psutil.disk_io_counters()
            if disk_io:
                disk_metrics.update({
                    "total_read_mb": round(disk_io.read_bytes / (1024 ** 2), 2),
                    "total_write_mb": round(disk_io.write_bytes / (1024 ** 2), 2)
                })
            
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_metrics["partitions"].append({
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "usage_percent": usage.percent,
                        "used_gb": round(usage.used / (1024 ** 3), 2),
                        "free_gb": round(usage.free / (1024 ** 3), 2)
                    })
                except Exception as e:
                    logger.warning(f"Could not get metrics for partition {partition.mountpoint}: {str(e)}")
                    continue
                
        except Exception as e:
            logger.error(f"Error getting disk metrics: {str(e)}")
            disk_metrics["error"] = f"Disk metrics collection failed: {str(e)}"
        
        return disk_metrics
    
    async def _get_network_metrics_async(self) -> Dict[str, Any]:
        """Get network metrics asynchronously"""
        return await asyncio.to_thread(self._get_network_metrics)

    def _get_network_metrics(self) -> Dict[str, Any]:
        """Get network metrics"""
        metrics = {}
        try:
            net_io = psutil.net_io_counters()
            metrics.update({
                "bytes_sent_mb": round(net_io.bytes_sent / (1024 ** 2), 2),
                "bytes_recv_mb": round(net_io.bytes_recv / (1024 ** 2), 2),
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv
            })
            
        except Exception as e:
            logger.error(f"Error getting network metrics: {str(e)}")
            metrics["error"] = f"Network metrics collection failed: {str(e)}"
        
        return metrics
    
    async def _get_gpu_metrics_async(self) -> Optional[List[Dict[str, Any]]]:
        """Get GPU metrics asynchronously"""
        return await asyncio.to_thread(self._get_gpu_metrics)

    def _get_gpu_metrics(self) -> Optional[List[Dict[str, Any]]]:
        """Get GPU metrics"""
        try:
            gpus = GPUtil.getGPUs()
            if not gpus:
                return None
            
            return [{
                "name": gpu.name,
                "load_percent": gpu.load * 100,
                "memory_usage_percent": gpu.memoryUtil * 100,
                "memory_used_gb": round(gpu.memoryUsed / 1024, 2),
                "memory_total_gb": round(gpu.memoryTotal / 1024, 2),
                "temperature": gpu.temperature
            } for gpu in gpus]
            
        except Exception as e:
            logger.warning(f"Could not get GPU metrics: {str(e)}")
            return None
        
    async def _get_process_metrics_async(self) -> Dict[str, Any]:
        """Get process metrics asynchronously"""
        return await asyncio.to_thread(self._get_process_metrics)

    def _get_process_metrics(self) -> Dict[str, Any]:
        """Get process metrics"""
        processes = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent']):
                try:
                    processes.append({
                        "pid": proc.info['pid'],
                        "name": proc.info['name'],
                        "user": proc.info['username'],
                        "cpu_percent": proc.info['cpu_percent'],
                        "memory_percent": proc.info['memory_percent']
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                except Exception as e:
                    logger.warning(f"Could not get process info: {str(e)}")
                    continue
            
            top_cpu = sorted(processes, key=lambda x: x['cpu_percent'], reverse=True)[:5]
            top_mem = sorted(processes, key=lambda x: x['memory_percent'], reverse=True)[:5]
            
            return {
                "total_processes": len(processes),
                "top_cpu_processes": top_cpu,
                "top_memory_processes": top_mem
            }
            
        except Exception as e:
            logger.error(f"Error getting process metrics: {str(e)}")
            return {
                "error": f"Process metrics collection failed: {str(e)}",
                "total_processes": 0
            }

    async def _get_system_health(self) -> Dict[str, Any]:
        """Get system health metrics"""
        health = {}
        try:
            health.update({
                "uptime_seconds": uptime(),
                "boot_time": datetime.datetime.fromtimestamp(psutil.boot_time()).isoformat(),
                "users": [u.name for u in psutil.users()]
            })
            
            if hasattr(psutil, "getloadavg"):
                try:
                    load_avg = psutil.getloadavg()
                    health.update({
                        "load_1min": load_avg[0],
                        "load_5min": load_avg[1],
                        "load_15min": load_avg[2]
                    })
                except Exception:
                    pass
                
        except Exception as e:
            logger.error(f"Error getting system health metrics: {str(e)}")
            health["error"] = f"System health collection failed: {str(e)}"
        
        return health

    async def collect_metrics(self) -> bool:
        """Collect and store all system metrics"""
        if self.collection is None:
            logger.error("No MongoDB connection available")
            return False
            
        timestamp = datetime.datetime.utcnow()
        try:
            metrics = {
                "timestamp": timestamp,
                "mac_address": self.mac_address,
                "system_id": self.system_id,
                "cpu": self._get_cpu_metrics(),
                "memory": self._get_memory_metrics(),
                "disk": self._get_disk_metrics(),
                "network": self._get_network_metrics(),
                "gpu": self._get_gpu_metrics(),
                "processes": self._get_process_metrics(),
                "system_health": self._get_system_health()
            }
            
            if not hasattr(self, 'system_info_added'):
                metrics.update(self.system_info)
                self.system_info_added = True
            
            await self.collection.insert_one(metrics)
            logger.info(f"Metrics stored for {self.system_id} at {timestamp.isoformat()}")
            return True
                
        except Exception as e:
            logger.error(f"Error during metrics collection: {str(e)}", exc_info=True)
            return False

    async def train_model_and_save(self, mac_address: str) -> Optional[TrendForecaster]:
        """Train and save a new model"""
        try:
            if self.collection is None:
                return None
                
            sanitized_mac = TrendForecaster.sanitize_mac_address(mac_address)
            model_path = os.path.join('models', f"{sanitized_mac}_trend_model.pkl")
            
            historical = pd.json_normalize(list(
                self.collection.find(
                    {'mac_address': mac_address},
                    {
                        '_id': 0,
                        'timestamp': 1,
                        'cpu.cpu_usage': 1,
                        'cpu.cpu_system': 1,
                        'memory.memory_usage_percent': 1,
                        'disk.total_read_mb': 1,
                        'network.packets_sent': 1,
                        'processes.total_processes': 1
                    }
                ).sort("timestamp", 1)
            ))

            if len(historical) < self.min_data_points_for_training:
                return None
                
            historical.ffill(inplace=True)
            historical.bfill(inplace=True)
            
            forecaster =await asyncio.to_thread(
                lambda: TrendForecaster(
                df=historical,
                target='cpu.cpu_usage',
                regressors=[
                    'cpu.cpu_system',
                    'memory.memory_usage_percent',
                    'disk.total_read_mb',
                    'network.packets_sent',
                    'processes.total_processes'
                ]
            )
        )

            os.makedirs('models', exist_ok=True)
            async with aiofiles.open(model_path, 'wb') as f:
                await f.write(pickle.dumps(forecaster))
            
            logger.info(f"Model trained and saved to {model_path}")
            return forecaster

        except Exception as e:
            logger.error(f"Error during model training: {str(e)}")
            return None

    async def _load_model_with_timeout(self, model_path: str) -> Optional[TrendForecaster]:
        """Platform-agnostic model loading with timeout"""
        def load_model(q):
            try:
                with open(model_path, 'rb') as f:
                    q.put(pickle.load(f))
            except Exception as e:
                q.put(e)
        
        q = queue.Queue()
        t = threading.Thread(target=load_model, args=(q,))
        t.start()
        t.join(timeout=5)

        if t.is_alive():
            logger.error("Model loading timed out")
            return None

        result = q.get()
        if isinstance(result, Exception):
            logger.error(f"Error loading model: {str(result)}")
            return None
            
        return result if isinstance(result, TrendForecaster) else None

    async def load_trend_model(self, mac_address: str) -> Optional[TrendForecaster]:
        """Load an existing model"""
        try:
            sanitized_mac = TrendForecaster.sanitize_mac_address(mac_address)
            model_path = os.path.join('models', f"{sanitized_mac}_trend_model.pkl")

            if not os.path.exists(model_path) or os.path.getsize(model_path) == 0:
                return None
                
            forecaster = self._load_model_with_timeout(model_path)
            if forecaster and hasattr(forecaster, 'is_valid') and not forecaster.is_valid():
                logger.warning("Loaded model failed validation")
                return None
                
            return forecaster
            
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            return None

    async def calculate_next_interval(self, forecaster: Optional[TrendForecaster], latest: Dict[str, Any]) -> int:
        """Calculate next collection interval"""
        if forecaster is None:
            return self.default_interval
            
        try:
            input_data = {
                "ds": latest["timestamp"],
                "cpu.cpu_usage": latest["cpu"]["cpu_usage"],
                "cpu.cpu_system": latest["cpu"]["cpu_system"],
                "memory.memory_usage_percent": latest["memory"]["memory_usage_percent"],
                "disk.total_read_mb": latest["disk"]["total_read_mb"],
                "network.packets_sent": latest["network"]["packets_sent"],
                "processes.total_processes": latest["processes"]["total_processes"]
            }
            
            interval = await asyncio.to_thread(forecaster.get_next_interval, input_data)
            return max(self.min_interval, min(self.max_interval, interval))
            
        except Exception as e:
            logger.error(f"Error calculating interval: {str(e)}")
            return self.default_interval

    async def run(self, initial_interval: Optional[int] = None) -> None:
        """Main monitoring loop"""
        await self.connect_to_mongodb()
        current_interval = initial_interval if initial_interval is not None else self.default_interval
        cycle = 0
        retrain_every = 12
        
        os.makedirs("models", exist_ok=True)
        forecaster = await self.load_trend_model(self.mac_address)
        
        if forecaster is None:
            logger.info("Training initial model...")
            forecaster =await self.train_model_and_save(self.mac_address)
        
        while True:
            try:
                start_time = time.time()
                
                if not await self.collect_metrics():
                    await asyncio.sleep(60)
                    continue
                
                cycle += 1
                
                if cycle % retrain_every == 0:
                    logger.info("Queueing model retrain...")
                    try:
                        redis = await AsyncRedis.from_url("redis://localhost:6379")
                        await redis.rpush("train_queue", self.mac_address)
                    except Exception as e:
                        logger.error(f"Failed to queue retrain: {str(e)}")
                
                latest = self.collection.find_one(
                    {'mac_address': self.mac_address},
                    sort=[('timestamp', -1)]
                )
                
                if latest:
                    current_interval = self.calculate_next_interval(forecaster, latest)
                
                elapsed = time.time() - start_time
                sleep_time = max(1, current_interval - elapsed)
                logger.info(f"Next collection in {sleep_time:.1f}s")
                time.sleep(sleep_time)
                
            except KeyboardInterrupt:
                logger.info("Shutting down...")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                time.sleep(60)

async def main():
    try:
        logger.info("Starting Async System Monitor")
        monitor =  SystemMonitor()
        await monitor.run()
    except Exception as e:
        logger.critical(f"Fatal error: {str(e)}")
    finally:
        logger.info("Monitor stopped")
if __name__ == "__main__":
    asyncio.run(main())
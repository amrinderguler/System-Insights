import psutil
import platform
import shutil
import socket
import getpass
import datetime
import uuid
import GPUtil
from uptime import uptime
import time
from pymongo import MongoClient
import os
import subprocess
import re
import socket
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

# MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")

class SystemMonitor:
    """A class to monitor system metrics and store them in MongoDB."""
    def __init__(self):
        self.collection = self._connect_to_mongodb()
        self.system_id = socket.gethostname()
        self.mac_address = self._get_mac_address()
        self.system_info = self._get_system_info()
        
    def _connect_to_mongodb(self):
        """Establishes connection to MongoDB with proper error handling."""
        try:
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            client.admin.command('ping')  # Test connection
            return client[DB_NAME][COLLECTION_NAME]
        except Exception as e:
            print(f"Failed to connect to MongoDB: {str(e)}")
            return None

    def _get_mac_address(self):
        """Gets MAC address more reliably across platforms."""
        try:
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                           for elements in range(0, 2*6, 8)][::-1])
            return mac
        except:
            return "unknown"

    def _get_system_info(self):
        """Gets static system information that doesn't change."""
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
            "initial_timestamp": datetime.datetime.utcnow()
        }

    def _get_disk_info(self):
        """Gets detailed disk partition information."""
        disks = []
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disks.append({
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                    "total_gb": round(usage.total / (1024 ** 3), 2)
                })
            except Exception:
                continue
        return disks

    def _get_network_interfaces(self):
        """Gets network interface information."""
        interfaces = []
        for name, addrs in psutil.net_if_addrs().items():
            interfaces.append({
                "name": name,
                "addresses": [addr.address for addr in addrs]
            })
        return interfaces

    def _get_cpu_metrics(self):
        """Gets detailed CPU metrics."""
        cpu_times = psutil.cpu_times_percent(interval=1)
        cpu_freq = psutil.cpu_freq().current if hasattr(psutil.cpu_freq(), 'current') else None
        load_avg = psutil.getloadavg() if hasattr(psutil, "getloadavg") else (None, None, None)
        
        return {
            "cpu_usage": psutil.cpu_percent(interval=1),
            "cpu_user": cpu_times.user,
            "cpu_system": cpu_times.system,
            "cpu_idle": cpu_times.idle,
            "cpu_iowait": getattr(cpu_times, 'iowait', None),
            "cpu_steal": getattr(cpu_times, 'steal', None),
            "cpu_frequency_mhz": cpu_freq,
            "load_1min": load_avg[0],
            "load_5min": load_avg[1],
            "load_15min": load_avg[2],
            "cpu_cores_usage": psutil.cpu_percent(interval=1, percpu=True)
        }

    def _get_memory_metrics(self):
        """Gets detailed memory metrics with proper attribute checking."""
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        metrics = {
            "memory_usage_percent": mem.percent,
            "memory_used_gb": round(mem.used / (1024 ** 3), 2),
            "memory_available_gb": round(getattr(mem, 'available', mem.free) / (1024 ** 3), 2),
            "swap_usage_percent": swap.percent,
            "swap_used_gb": round(swap.used / (1024 ** 3), 2)
        }
        
        # Add cached memory if available
        if hasattr(mem, 'cached'):
            metrics["memory_cached_gb"] = round(mem.cached / (1024 ** 3), 2)
        else:
            metrics["memory_cached_gb"] = None
        
        # Add buffers if available
        if hasattr(mem, 'buffers'):
            metrics["memory_buffers_gb"] = round(mem.buffers / (1024 ** 3), 2)
        else:
            metrics["memory_buffers_gb"] = None
        
        # Add page faults if available
        if hasattr(mem, 'page_faults'):
            metrics["page_faults"] = mem.page_faults
        else:
            metrics["page_faults"] = None
        
        return metrics

    def _get_disk_metrics(self):
        """Gets detailed disk metrics."""
        disk_io = psutil.disk_io_counters()
        disk_metrics = {
            "partitions": [],
            "total_read_mb": round(disk_io.read_bytes / (1024 ** 2), 2) if disk_io else None,
            "total_write_mb": round(disk_io.write_bytes / (1024 ** 2), 2) if disk_io else None,
            "read_ops": disk_io.read_count if disk_io else None,
            "write_ops": disk_io.write_count if disk_io else None
        }
        
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
            except Exception:
                continue
                
        return disk_metrics

    def _get_network_metrics(self):
        """Gets detailed network metrics."""
        net_io = psutil.net_io_counters()
        connections = psutil.net_connections(kind='inet')
        
        return {
            "bytes_sent_mb": round(net_io.bytes_sent / (1024 ** 2), 2),
            "bytes_recv_mb": round(net_io.bytes_recv / (1024 ** 2), 2),
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
            "errors_in": net_io.errin,
            "errors_out": net_io.errout,
            "active_connections": len(connections),
            "tcp_states": self._get_tcp_connection_states()
        }

    def _get_tcp_connection_states(self):
        """Counts TCP connections by state."""
        states = defaultdict(int)
        for conn in psutil.net_connections(kind='tcp'):
            states[conn.status] += 1
        return dict(states)

    def _get_gpu_metrics(self):
        """Gets GPU metrics if available."""
        gpus = GPUtil.getGPUs()
        if not gpus:
            return None
            
        return [{
            "name": gpu.name,
            "load_percent": gpu.load * 100,
            "memory_usage_percent": gpu.memoryUtil * 100,
            "memory_used_gb": round(gpu.memoryUsed / 1024, 2),
            "memory_total_gb": round(gpu.memoryTotal / 1024, 2),
            "temperature": gpu.temperature,
            "uuid": gpu.uuid
        } for gpu in gpus]

    def _get_process_metrics(self):
        """Gets process metrics."""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 
                                       'memory_percent', 'memory_info', 'status']):
            try:
                processes.append({
                    "pid": proc.info['pid'],
                    "name": proc.info['name'],
                    "user": proc.info['username'],
                    "cpu_percent": proc.info['cpu_percent'],
                    "memory_percent": proc.info['memory_percent'],
                    "memory_rss_mb": round(proc.info['memory_info'].rss / (1024 ** 2), 2),
                    "status": proc.info['status']
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        top_cpu = sorted(processes, key=lambda x: x['cpu_percent'], reverse=True)[:10]
        top_mem = sorted(processes, key=lambda x: x['memory_percent'], reverse=True)[:10]
        
        return {
            "total_processes": len(processes),
            "top_cpu_processes": top_cpu,
            "top_memory_processes": top_mem,
            "zombie_processes": len([p for p in processes if p['status'] == psutil.STATUS_ZOMBIE])
        }

    def _get_system_health(self):
        """Gets system health indicators."""
        return {
            "uptime_seconds": uptime(),
            "boot_time": datetime.datetime.fromtimestamp(psutil.boot_time()).isoformat(),
            "users": [u.name for u in psutil.users()],
            "file_descriptors": {
                "used": psutil.Process().num_fds() if hasattr(psutil.Process(), 'num_fds') else None,
                "limit": None  # Will be filled differently per OS
            },
            "temperature": self._get_cpu_temperature()
        }

    def _get_cpu_temperature(self):
        """Gets CPU temperature if available."""
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if temps and 'coretemp' in temps:
                    return max([t.current for t in temps['coretemp'] if hasattr(t, 'current')])
            return None
        except:
            return None

    def collect_metrics(self):
        """Collects all metrics and stores them in MongoDB."""
        if self.collection is None:  # Check if MongoDB connection is available
            print("No MongoDB connection available")
            return
            
        timestamp = datetime.datetime.utcnow()
        
        metrics = {
            "timestamp": timestamp,
            **self.system_info,
            "cpu": self._get_cpu_metrics(),
            "memory": self._get_memory_metrics(),
            "disk": self._get_disk_metrics(),
            "network": self._get_network_metrics(),
            "gpu": self._get_gpu_metrics(),
            "processes": self._get_process_metrics(),
            "system_health": self._get_system_health()
        }
        
        try: 
            self.collection.insert_one(metrics)
            print(f"Metrics logged at {timestamp.isoformat()}")
        except Exception as e:
            print(f"Failed to store metrics: {str(e)}")

    def run(self, interval=300):
        """Runs the monitoring loop."""
        while True:
            try:
                self.collect_metrics()
                time.sleep(interval)
            except KeyboardInterrupt:
                print("Monitoring stopped by user")
                break
            except Exception as e:
                print(f"Monitoring error: {str(e)}")
                time.sleep(60)  # Wait before retrying

if __name__ == "__main__":
    monitor = SystemMonitor()
    monitor.run()
import os
import sys


sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from celery import Celery
app = Celery('system_monitor_tasks',
             broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
             backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
             include=['train'])
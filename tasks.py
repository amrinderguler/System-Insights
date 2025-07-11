from monitor import SystemMonitor
from config import config
from logging_setup import logger

def retrain_prophet(mac_address):
    """
    Task to retrain the Prophet model for a specific MAC address
    Args:
        mac_address: The system's MAC address to retrain for
    """
    logger.info(f"Starting model retrain for {mac_address}")
    
    try:
        monitor = SystemMonitor()
        monitor.mac_address = mac_address
        forecaster = monitor.train_model_and_save()
        
        if forecaster:
            logger.info(f"Successfully retrained model for {mac_address}")
            return True
        else:
            logger.warning(f"Model retrain failed for {mac_address}")
            return False
            
    except Exception as e:
        logger.error(f"Retrain task failed for {mac_address}: {str(e)}")
        raise
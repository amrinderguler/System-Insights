import os
import re
import numpy as np
import pandas as pd
from prophet import Prophet
from config import config
from logging_setup import logger

class TrendForecaster:
    def __init__(self, df=None, target='cpu.cpu_user', regressors=[], existing_model=None):
        """
        Initialize trend forecaster with:
        - df: Training data
        - target: Target metric column
        - regressors: List of regressor columns
        - existing_model: Pre-trained Prophet model
        """
        if existing_model:
            self.model = existing_model
            self.df = None
            self.target = target
            self.regressors = regressors
        else:
            self._initialize_new_model(df, target, regressors)

    def _initialize_new_model(self, df, target, regressors):
        """Initialize and train new Prophet model"""
        self.df = df.copy()
        self.target = target
        self.regressors = [r for r in regressors if r in df.columns]
        
        self.model = Prophet(
            daily_seasonality=True,
            changepoint_prior_scale=0.05,
            seasonality_prior_scale=10.0
        )
        
        for reg in self.regressors:
            self.model.add_regressor(reg)
        
        self.df.rename(columns={'timestamp': 'ds', self.target: 'y'}, inplace=True)
        
        try:
            self.model.fit(self.df[['ds', 'y'] + self.regressors])
            logger.info("Successfully trained new Prophet model")
        except Exception as e:
            logger.error(f"Model training failed: {str(e)}")
            raise

    def get_next_interval(self, latest_point):
        """
        Calculate next monitoring interval based on:
        - latest_point: Dict containing current system metrics
        Returns: Recommended interval in seconds
        """
        try:
            # Emergency check for critical system state
            if latest_point['cpu.cpu_system'] > 90:
                logger.warning("Emergency mode - using minimum interval")
                return config.MIN_INTERVAL
                
            # Prepare prediction data
            future = pd.DataFrame([latest_point])
            forecast = self.model.predict(future)
            trend = forecast['trend'].iloc[0]
            
            # Dynamic blending based on system state
            current_load = latest_point['cpu.cpu_system']
            blend_weight = 0.7 if current_load < 70 else 0.3
            blended_score = blend_weight * trend + (1-blend_weight) * current_load
            
            # Calculate interval based on historical percentiles
            low, high = self.df['y'].quantile([0.1, 0.9])
            interval = np.interp(
                blended_score,
                [low, high],
                [config.MAX_INTERVAL, config.MIN_INTERVAL]
            )
            
            # Ensure interval stays within bounds
            final_interval = int(np.clip(interval, config.MIN_INTERVAL, config.MAX_INTERVAL))
            logger.debug(f"Calculated interval: {final_interval}s (Score: {blended_score:.2f})")
            return final_interval
            
        except Exception as e:
            logger.error(f"Interval prediction failed: {str(e)}")
            return config.MIN_INTERVAL
        
    

    @staticmethod
    def sanitize_mac_address(mac_address):
        """Convert MAC address to filesystem-safe string"""
        return re.sub(r'[^a-zA-Z0-9]', '_', mac_address)
    
    def is_valid(self) -> bool:
        """Validate that the model was trained properly"""
        try:
            # Check if model exists and has required attributes
            return (
                hasattr(self, 'model') and 
                self.model is not None and
                hasattr(self.model, 'params') and
                len(self.model.params) > 0
            )
        except Exception:
            return False

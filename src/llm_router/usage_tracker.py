"""Usage tracking system for LLM rate limiting with persistent storage."""

import json
import time
import sqlite3
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pathlib import Path
import threading
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class UsageStorage(ABC):
    """Abstract base class for usage storage backends."""
    
    @abstractmethod
    def load_usage(self) -> Dict:
        """Load usage data from storage."""
        pass
    
    @abstractmethod
    def save_usage(self, usage_data: Dict) -> None:
        """Save usage data to storage."""
        pass
    
    @abstractmethod
    def cleanup_old_data(self) -> None:
        """Clean up old usage data."""
        pass


class JSONStorage(UsageStorage):
    """JSON file-based storage for usage tracking."""
    
    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.lock = threading.Lock()
    
    def load_usage(self) -> Dict:
        """Load usage data from JSON file."""
        with self.lock:
            if not self.storage_path.exists():
                return {}
            
            try:
                with open(self.storage_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Error loading usage data: {e}")
                return {}
    
    def save_usage(self, usage_data: Dict) -> None:
        """Save usage data to JSON file."""
        with self.lock:
            try:
                # Ensure directory exists
                self.storage_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(self.storage_path, 'w') as f:
                    json.dump(usage_data, f, indent=2)
            except IOError as e:
                logger.error(f"Error saving usage data: {e}")
    
    def cleanup_old_data(self) -> None:
        """Clean up old timestamps (older than 1 hour) from JSON storage."""
        current_time = time.time()
        cutoff_time = current_time - 3600  # 1 hour ago
        
        usage_data = self.load_usage()
        modified = False
        
        for model_key, data in usage_data.items():
            if 'minute_timestamps' in data:
                old_count = len(data['minute_timestamps'])
                data['minute_timestamps'] = [
                    ts for ts in data['minute_timestamps'] 
                    if ts > cutoff_time
                ]
                if len(data['minute_timestamps']) != old_count:
                    modified = True
        
        if modified:
            self.save_usage(usage_data)
            logger.debug("Cleaned up old usage data")


class SQLiteStorage(UsageStorage):
    """SQLite-based storage for usage tracking (for concurrent access)."""
    
    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.lock = threading.Lock()
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS usage_tracking (
                    model_key TEXT PRIMARY KEY,
                    minute_timestamps TEXT,
                    daily_count INTEGER DEFAULT 0,
                    last_reset TEXT,
                    updated_at REAL
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_updated_at ON usage_tracking(updated_at)
            ''')
    
    def load_usage(self) -> Dict:
        """Load usage data from SQLite."""
        with self.lock:
            try:
                with sqlite3.connect(self.storage_path) as conn:
                    cursor = conn.execute(
                        'SELECT model_key, minute_timestamps, daily_count, last_reset FROM usage_tracking'
                    )
                    
                    usage_data = {}
                    for row in cursor.fetchall():
                        model_key, timestamps_json, daily_count, last_reset = row
                        timestamps = json.loads(timestamps_json) if timestamps_json else []
                        
                        usage_data[model_key] = {
                            'minute_timestamps': timestamps,
                            'daily_count': daily_count,
                            'last_reset': last_reset
                        }
                    
                    return usage_data
            except (sqlite3.Error, json.JSONDecodeError) as e:
                logger.warning(f"Error loading usage data from SQLite: {e}")
                return {}
    
    def save_usage(self, usage_data: Dict) -> None:
        """Save usage data to SQLite."""
        with self.lock:
            try:
                with sqlite3.connect(self.storage_path) as conn:
                    for model_key, data in usage_data.items():
                        timestamps_json = json.dumps(data.get('minute_timestamps', []))
                        
                        conn.execute('''
                            INSERT OR REPLACE INTO usage_tracking 
                            (model_key, minute_timestamps, daily_count, last_reset, updated_at)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (
                            model_key,
                            timestamps_json,
                            data.get('daily_count', 0),
                            data.get('last_reset'),
                            time.time()
                        ))
            except sqlite3.Error as e:
                logger.error(f"Error saving usage data to SQLite: {e}")
    
    def cleanup_old_data(self) -> None:
        """Clean up old data from SQLite."""
        cutoff_time = time.time() - 3600  # 1 hour ago
        
        with self.lock:
            try:
                with sqlite3.connect(self.storage_path) as conn:
                    # Get all records
                    cursor = conn.execute(
                        'SELECT model_key, minute_timestamps FROM usage_tracking'
                    )
                    
                    for model_key, timestamps_json in cursor.fetchall():
                        if timestamps_json:
                            timestamps = json.loads(timestamps_json)
                            new_timestamps = [ts for ts in timestamps if ts > cutoff_time]
                            
                            if len(new_timestamps) != len(timestamps):
                                conn.execute(
                                    'UPDATE usage_tracking SET minute_timestamps = ?, updated_at = ? WHERE model_key = ?',
                                    (json.dumps(new_timestamps), time.time(), model_key)
                                )
            except (sqlite3.Error, json.JSONDecodeError) as e:
                logger.warning(f"Error cleaning up SQLite data: {e}")


class UsageTracker:
    """Tracks API usage with rate limiting for LLM requests."""
    
    def __init__(self, storage_backend: str = 'json', storage_path: str = 'usage_counters.json'):
        """Initialize usage tracker with specified storage backend."""
        if storage_backend == 'sqlite':
            self.storage = SQLiteStorage(storage_path)
        else:
            self.storage = JSONStorage(storage_path)
        
        self.usage_data = self.storage.load_usage()
        
        # Start cleanup timer
        self._last_cleanup = time.time()
        
        logger.info(f"Initialized usage tracker with {storage_backend} backend")
    
    def _ensure_model_entry(self, model_key: str) -> None:
        """Ensure model entry exists in usage data."""
        if model_key not in self.usage_data:
            self.usage_data[model_key] = {
                'minute_timestamps': [],
                'daily_count': 0,
                'last_reset': datetime.now(timezone.utc).strftime('%Y-%m-%d')
            }
    
    def _cleanup_if_needed(self) -> None:
        """Perform cleanup if enough time has passed."""
        current_time = time.time()
        if current_time - self._last_cleanup > 3600:  # 1 hour
            self.storage.cleanup_old_data()
            self._last_cleanup = current_time
    
    def _reset_daily_if_needed(self, model_key: str) -> None:
        """Reset daily counter if it's a new day."""
        self._ensure_model_entry(model_key)
        
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        last_reset = self.usage_data[model_key]['last_reset']
        
        if last_reset != today:
            self.usage_data[model_key]['daily_count'] = 0
            self.usage_data[model_key]['last_reset'] = today
            logger.debug(f"Reset daily counter for {model_key}")
    
    def can_make_request(self, provider: str, model: str, rpm_limit: int, rpd_limit: int) -> bool:
        """Check if a request can be made without exceeding rate limits."""
        model_key = f"{provider}:{model}"
        current_time = time.time()
        
        self._ensure_model_entry(model_key)
        self._reset_daily_if_needed(model_key)
        self._cleanup_if_needed()
        
        # Check RPM (requests per minute)
        minute_timestamps = self.usage_data[model_key]['minute_timestamps']
        recent_requests = [ts for ts in minute_timestamps if current_time - ts < 60]
        
        if len(recent_requests) >= rpm_limit:
            logger.debug(f"RPM limit reached for {model_key}: {len(recent_requests)}/{rpm_limit}")
            return False
        
        # Check RPD (requests per day)
        daily_count = self.usage_data[model_key]['daily_count']
        if daily_count >= rpd_limit:
            logger.debug(f"RPD limit reached for {model_key}: {daily_count}/{rpd_limit}")
            return False
        
        return True
    
    def record_request(self, provider: str, model: str) -> None:
        """Record a successful request."""
        model_key = f"{provider}:{model}"
        current_time = time.time()
        
        self._ensure_model_entry(model_key)
        self._reset_daily_if_needed(model_key)
        
        # Add timestamp for RPM tracking
        self.usage_data[model_key]['minute_timestamps'].append(current_time)
        
        # Increment daily counter
        self.usage_data[model_key]['daily_count'] += 1
        
        # Clean old timestamps (keep only last minute)
        self.usage_data[model_key]['minute_timestamps'] = [
            ts for ts in self.usage_data[model_key]['minute_timestamps']
            if current_time - ts < 60
        ]
        
        # Persist changes
        self.storage.save_usage(self.usage_data)
        
        logger.debug(f"Recorded request for {model_key}")
    
    def get_usage_stats(self, provider: str, model: str) -> Dict:
        """Get current usage statistics for a model."""
        model_key = f"{provider}:{model}"
        self._ensure_model_entry(model_key)
        self._reset_daily_if_needed(model_key)
        
        current_time = time.time()
        minute_timestamps = self.usage_data[model_key]['minute_timestamps']
        recent_requests = [ts for ts in minute_timestamps if current_time - ts < 60]
        
        return {
            'model': model_key,
            'requests_last_minute': len(recent_requests),
            'requests_today': self.usage_data[model_key]['daily_count'],
            'last_reset': self.usage_data[model_key]['last_reset']
        }
    
    def get_all_usage_stats(self) -> List[Dict]:
        """Get usage statistics for all tracked models."""
        stats = []
        for model_key in self.usage_data.keys():
            provider, model = model_key.split(':', 1)
            stats.append(self.get_usage_stats(provider, model))
        return stats
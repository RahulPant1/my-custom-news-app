"""Redis caching layer for improved performance."""

import json
import pickle
import hashlib
import time
import logging
from typing import Any, Optional, Dict, List, Callable
from functools import wraps
import redis
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CacheManager:
    """Redis-based caching manager with fallback to in-memory cache."""
    
    def __init__(self, redis_url: str = None, default_ttl: int = 300):
        self.default_ttl = default_ttl
        self.redis_client = None
        self.fallback_cache = {}  # In-memory fallback
        self.fallback_expiry = {}
        
        # Try to connect to Redis
        try:
            if redis_url:
                self.redis_client = redis.from_url(redis_url)
            else:
                self.redis_client = redis.Redis(
                    host=os.getenv('REDIS_HOST', 'localhost'),
                    port=int(os.getenv('REDIS_PORT', 6379)),
                    db=int(os.getenv('REDIS_DB', 0)),
                    decode_responses=False,  # We'll handle encoding ourselves
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True
                )
            
            # Test connection
            self.redis_client.ping()
            self.use_redis = True
            logger.info("Connected to Redis cache")
            
        except Exception as e:
            logger.warning(f"Redis not available, using in-memory cache: {e}")
            self.use_redis = False
    
    def _serialize_key(self, key: str) -> str:
        """Create a consistent cache key."""
        return f"newsdigest:{key}"
    
    def _serialize_value(self, value: Any) -> bytes:
        """Serialize value for storage."""
        return pickle.dumps(value)
    
    def _deserialize_value(self, data: bytes) -> Any:
        """Deserialize value from storage."""
        return pickle.loads(data)
    
    def _cleanup_fallback_cache(self):
        """Clean expired entries from fallback cache."""
        current_time = time.time()
        expired_keys = [
            key for key, expiry in self.fallback_expiry.items()
            if expiry < current_time
        ]
        
        for key in expired_keys:
            self.fallback_cache.pop(key, None)
            self.fallback_expiry.pop(key, None)
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        cache_key = self._serialize_key(key)
        
        if self.use_redis:
            try:
                data = self.redis_client.get(cache_key)
                if data:
                    return self._deserialize_value(data)
                return None
            except Exception as e:
                logger.warning(f"Redis get failed, falling back: {e}")
                self.use_redis = False
        
        # Fallback cache
        self._cleanup_fallback_cache()
        if cache_key in self.fallback_cache:
            if self.fallback_expiry[cache_key] > time.time():
                return self.fallback_cache[cache_key]
            else:
                # Expired
                self.fallback_cache.pop(cache_key, None)
                self.fallback_expiry.pop(cache_key, None)
        
        return None
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache with TTL."""
        cache_key = self._serialize_key(key)
        ttl = ttl or self.default_ttl
        
        if self.use_redis:
            try:
                serialized_value = self._serialize_value(value)
                self.redis_client.setex(cache_key, ttl, serialized_value)
                return True
            except Exception as e:
                logger.warning(f"Redis set failed, falling back: {e}")
                self.use_redis = False
        
        # Fallback cache
        self._cleanup_fallback_cache()
        self.fallback_cache[cache_key] = value
        self.fallback_expiry[cache_key] = time.time() + ttl
        return True
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        cache_key = self._serialize_key(key)
        
        if self.use_redis:
            try:
                self.redis_client.delete(cache_key)
                return True
            except Exception as e:
                logger.warning(f"Redis delete failed: {e}")
        
        # Fallback cache
        self.fallback_cache.pop(cache_key, None)
        self.fallback_expiry.pop(cache_key, None)
        return True
    
    def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern."""
        if self.use_redis:
            try:
                cache_pattern = self._serialize_key(pattern)
                keys = self.redis_client.keys(cache_pattern)
                if keys:
                    return self.redis_client.delete(*keys)
                return 0
            except Exception as e:
                logger.warning(f"Redis pattern clear failed: {e}")
        
        # Fallback cache - pattern matching
        count = 0
        prefix = self._serialize_key("")
        pattern_key = pattern.replace("*", "")
        
        keys_to_remove = []
        for key in self.fallback_cache:
            if key.startswith(prefix) and pattern_key in key:
                keys_to_remove.append(key)
                count += 1
        
        for key in keys_to_remove:
            self.fallback_cache.pop(key, None)
            self.fallback_expiry.pop(key, None)
        
        return count
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        stats = {
            'type': 'redis' if self.use_redis else 'memory',
            'fallback_entries': len(self.fallback_cache)
        }
        
        if self.use_redis:
            try:
                info = self.redis_client.info()
                stats.update({
                    'redis_memory_used': info.get('used_memory_human', 'Unknown'),
                    'redis_connected_clients': info.get('connected_clients', 0),
                    'redis_total_commands': info.get('total_commands_processed', 0),
                    'redis_keyspace_hits': info.get('keyspace_hits', 0),
                    'redis_keyspace_misses': info.get('keyspace_misses', 0)
                })
                
                # Calculate hit rate
                hits = stats['redis_keyspace_hits']
                misses = stats['redis_keyspace_misses']
                if hits + misses > 0:
                    stats['hit_rate'] = hits / (hits + misses)
                else:
                    stats['hit_rate'] = 0
                    
            except Exception as e:
                logger.warning(f"Failed to get Redis stats: {e}")
        
        return stats


# Global cache instance
cache = CacheManager()


def cache_result(ttl: int = 300, key_prefix: str = "", use_args: bool = True):
    """Decorator to cache function results."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if use_args:
                # Include function arguments in cache key
                arg_str = "_".join(str(arg) for arg in args)
                kwarg_str = "_".join(f"{k}:{v}" for k, v in sorted(kwargs.items()))
                key_parts = [func.__name__, arg_str, kwarg_str]
            else:
                key_parts = [func.__name__]
            
            if key_prefix:
                key_parts.insert(0, key_prefix)
            
            cache_key = hashlib.md5("_".join(key_parts).encode()).hexdigest()
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            logger.debug(f"Cached result for {func.__name__}")
            
            return result
        
        # Add cache control methods to the wrapped function
        wrapper.cache_clear = lambda: cache.clear_pattern(f"{key_prefix}_{func.__name__}_*")
        wrapper.cache_info = lambda: cache.get_stats()
        
        return wrapper
    return decorator


def cache_expensive_query(ttl: int = 600):
    """Specific decorator for expensive database queries."""
    return cache_result(ttl=ttl, key_prefix="db_query")


def cache_api_response(ttl: int = 300):
    """Specific decorator for API responses."""
    return cache_result(ttl=ttl, key_prefix="api_response")


class CachedDatabaseOperations:
    """Cached versions of common database operations."""
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    @cache_expensive_query(ttl=600)  # 10 minutes
    def get_articles_by_categories(self, categories: List[str], limit: int = 20) -> List[Dict]:
        """Cached version of get_articles_by_categories."""
        return self.db.get_articles_by_categories(categories, limit)
    
    @cache_expensive_query(ttl=300)  # 5 minutes
    def get_user_preferences(self, user_id: str) -> Optional[Dict]:
        """Cached version of get_user_preferences."""
        return self.db.get_user_preferences(user_id)
    
    @cache_expensive_query(ttl=1800)  # 30 minutes
    def get_all_users(self) -> List[Dict]:
        """Cached version of get_all_users."""
        return self.db.get_all_users()
    
    @cache_expensive_query(ttl=3600)  # 1 hour
    def get_validated_feeds(self, category: str = None, only_ok: bool = True) -> List[Dict]:
        """Cached version of get_validated_feeds."""
        return self.db.get_validated_feeds(category, only_ok)
    
    @cache_expensive_query(ttl=300)  # 5 minutes
    def get_article_count(self) -> int:
        """Cached version of get_article_count."""
        return self.db.get_article_count()
    
    def invalidate_user_cache(self, user_id: str):
        """Invalidate cache entries for a specific user."""
        cache.delete(f"db_query_get_user_preferences_{user_id}")
        cache.clear_pattern("db_query_get_all_users_*")
    
    def invalidate_articles_cache(self):
        """Invalidate article-related cache entries."""
        cache.clear_pattern("db_query_get_articles_by_categories_*")
        cache.clear_pattern("db_query_get_article_count_*")
    
    def invalidate_feeds_cache(self):
        """Invalidate feed-related cache entries."""
        cache.clear_pattern("db_query_get_validated_feeds_*")


# Response caching for Flask
def cache_response(ttl: int = 300):
    """Flask response caching decorator."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            from flask import request, jsonify
            
            # Generate cache key based on request
            request_key = f"{request.method}:{request.path}:{request.query_string.decode()}"
            cache_key = hashlib.md5(request_key.encode()).hexdigest()
            
            # Try cache first
            cached_response = cache.get(f"response_{cache_key}")
            if cached_response:
                logger.debug(f"Response cache hit for {request.path}")
                return cached_response
            
            # Execute function
            response = func(*args, **kwargs)
            
            # Cache successful responses only
            if hasattr(response, 'status_code') and response.status_code == 200:
                cache.set(f"response_{cache_key}", response, ttl)
                logger.debug(f"Cached response for {request.path}")
            
            return response
        
        return wrapper
    return decorator


def setup_caching(app):
    """Setup caching for Flask application."""
    
    # Add cache headers to static files
    @app.after_request
    def add_cache_headers(response):
        from flask import request
        if request.endpoint == 'static':
            # Cache static files for 1 hour
            response.cache_control.max_age = 3600
            response.cache_control.public = True
        elif request.path.startswith('/api/'):
            # API responses - short cache
            response.cache_control.max_age = 60
        
        return response
    
    # Cache status endpoint
    @app.route('/cache/stats')
    def cache_stats():
        """Get cache statistics."""
        return cache.get_stats()
    
    @app.route('/cache/clear', methods=['POST'])
    def clear_cache():
        """Clear cache (admin only)."""
        # This would typically require admin auth
        try:
            pattern = request.json.get('pattern', '*') if request.is_json else '*'
            cleared = cache.clear_pattern(pattern)
            return {'success': True, 'cleared_keys': cleared}
        except Exception as e:
            return {'success': False, 'error': str(e)}, 500
    
    logger.info("Caching setup completed")


# Initialize cached database operations
def get_cached_db_operations(db_manager):
    """Get cached database operations instance."""
    return CachedDatabaseOperations(db_manager)
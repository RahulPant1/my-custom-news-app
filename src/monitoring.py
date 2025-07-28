"""Comprehensive monitoring and observability for the news digest application."""

import time
import logging
import psutil
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
import os
from flask import Flask, request, g
from functools import wraps
import sqlite3

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects and stores application metrics."""
    
    def __init__(self, max_samples: int = 1000):
        self.max_samples = max_samples
        
        # Metrics storage
        self.metrics = defaultdict(lambda: deque(maxlen=max_samples))
        self.counters = defaultdict(int)
        self.gauges = defaultdict(float)
        self.histograms = defaultdict(list)
        
        # Request tracking
        self.request_times = deque(maxlen=max_samples)
        self.error_counts = defaultdict(int)
        self.endpoint_stats = defaultdict(lambda: {
            'count': 0,
            'total_time': 0.0,
            'avg_time': 0.0,
            'errors': 0
        })
        
        # System metrics tracking
        self.system_metrics = deque(maxlen=max_samples)
        
        # Lock for thread safety
        self._lock = threading.Lock()
        
        # Start background collection
        self._start_system_collection()
    
    def record_metric(self, name: str, value: float, tags: Dict = None):
        """Record a metric value with optional tags."""
        with self._lock:
            timestamp = datetime.utcnow()
            metric_data = {
                'value': value,
                'timestamp': timestamp,
                'tags': tags or {}
            }
            self.metrics[name].append(metric_data)
    
    def increment_counter(self, name: str, value: int = 1):
        """Increment a counter metric."""
        with self._lock:
            self.counters[name] += value
    
    def set_gauge(self, name: str, value: float):
        """Set a gauge metric value."""
        with self._lock:
            self.gauges[name] = value
    
    def record_histogram(self, name: str, value: float):
        """Record a value in a histogram."""
        with self._lock:
            self.histograms[name].append(value)
            # Keep only recent values
            if len(self.histograms[name]) > self.max_samples:
                self.histograms[name] = self.histograms[name][-self.max_samples:]
    
    def record_request(self, endpoint: str, method: str, status_code: int, 
                      response_time: float, error: str = None):
        """Record request metrics."""
        with self._lock:
            self.request_times.append({
                'endpoint': endpoint,
                'method': method,
                'status_code': status_code,
                'response_time': response_time,
                'timestamp': datetime.utcnow(),
                'error': error
            })
            
            # Update endpoint statistics
            key = f"{method} {endpoint}"
            stats = self.endpoint_stats[key]
            stats['count'] += 1
            stats['total_time'] += response_time
            stats['avg_time'] = stats['total_time'] / stats['count']
            
            if status_code >= 400:
                stats['errors'] += 1
                self.error_counts[status_code] += 1
    
    def get_metrics_summary(self) -> Dict:
        """Get a summary of all collected metrics."""
        with self._lock:
            # Calculate request statistics
            recent_requests = [r for r in self.request_times 
                             if r['timestamp'] > datetime.utcnow() - timedelta(minutes=5)]
            
            request_stats = {
                'total_requests': len(self.request_times),
                'recent_requests': len(recent_requests),
                'avg_response_time': sum(r['response_time'] for r in recent_requests) / max(1, len(recent_requests)),
                'error_rate': sum(1 for r in recent_requests if r['status_code'] >= 400) / max(1, len(recent_requests)),
                'requests_per_minute': len(recent_requests)
            }
            
            # Get latest system metrics
            latest_system = self.system_metrics[-1] if self.system_metrics else {}
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'request_stats': request_stats,
                'endpoint_stats': dict(self.endpoint_stats),
                'error_counts': dict(self.error_counts),
                'counters': dict(self.counters),
                'gauges': dict(self.gauges),
                'system_metrics': latest_system,
                'uptime_seconds': time.time() - self._start_time if hasattr(self, '_start_time') else 0
            }
    
    def get_historical_data(self, metric_name: str, minutes: int = 60) -> List[Dict]:
        """Get historical data for a specific metric."""
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        
        with self._lock:
            if metric_name in self.metrics:
                return [
                    {
                        'value': m['value'],
                        'timestamp': m['timestamp'].isoformat(),
                        'tags': m['tags']
                    }
                    for m in self.metrics[metric_name]
                    if m['timestamp'] > cutoff_time
                ]
            return []
    
    def _start_system_collection(self):
        """Start background thread for system metrics collection."""
        self._start_time = time.time()
        
        def collect_system_metrics():
            while True:
                try:
                    # CPU and memory metrics
                    cpu_percent = psutil.cpu_percent(interval=1)
                    memory = psutil.virtual_memory()
                    disk = psutil.disk_usage('/')
                    
                    # Process-specific metrics
                    process = psutil.Process()
                    process_memory = process.memory_info()
                    
                    system_data = {
                        'timestamp': datetime.utcnow().isoformat(),
                        'cpu_percent': cpu_percent,
                        'memory_percent': memory.percent,
                        'memory_used_mb': memory.used / 1024 / 1024,
                        'memory_available_mb': memory.available / 1024 / 1024,
                        'disk_percent': disk.percent,
                        'disk_used_gb': disk.used / 1024 / 1024 / 1024,
                        'disk_free_gb': disk.free / 1024 / 1024 / 1024,
                        'process_memory_mb': process_memory.rss / 1024 / 1024,
                        'process_memory_vms_mb': process_memory.vms / 1024 / 1024,
                        'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
                    }
                    
                    with self._lock:
                        self.system_metrics.append(system_data)
                    
                    # Also record as individual metrics
                    self.set_gauge('system.cpu_percent', cpu_percent)
                    self.set_gauge('system.memory_percent', memory.percent)
                    self.set_gauge('system.disk_percent', disk.percent)
                    self.set_gauge('process.memory_mb', process_memory.rss / 1024 / 1024)
                    
                except Exception as e:
                    logger.error(f"Error collecting system metrics: {e}")
                
                time.sleep(30)  # Collect every 30 seconds
        
        metrics_thread = threading.Thread(target=collect_system_metrics, daemon=True)
        metrics_thread.start()
        logger.info("Started system metrics collection thread")


class AlertManager:
    """Manages alerts and notifications for system health."""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self.alert_rules = []
        self.active_alerts = {}
        self.alert_history = deque(maxlen=1000)
        
        # Register default alert rules
        self._register_default_alerts()
    
    def add_alert_rule(self, name: str, condition_func: callable, 
                      threshold: float, message: str, severity: str = 'warning'):
        """Add a new alert rule."""
        rule = {
            'name': name,
            'condition': condition_func,
            'threshold': threshold,
            'message': message,
            'severity': severity,
            'enabled': True
        }
        self.alert_rules.append(rule)
        logger.info(f"Added alert rule: {name}")
    
    def check_alerts(self):
        """Check all alert conditions and trigger alerts if needed."""
        current_time = datetime.utcnow()
        
        for rule in self.alert_rules:
            if not rule['enabled']:
                continue
                
            try:
                # Evaluate condition
                triggered = rule['condition'](self.metrics, rule['threshold'])
                
                if triggered and rule['name'] not in self.active_alerts:
                    # New alert
                    alert = {
                        'name': rule['name'],
                        'message': rule['message'],
                        'severity': rule['severity'],
                        'triggered_at': current_time,
                        'threshold': rule['threshold']
                    }
                    
                    self.active_alerts[rule['name']] = alert
                    self.alert_history.append(alert.copy())
                    
                    # Log alert
                    log_level = logging.ERROR if rule['severity'] == 'critical' else logging.WARNING
                    logger.log(log_level, f"ALERT: {rule['name']} - {rule['message']}")
                    
                elif not triggered and rule['name'] in self.active_alerts:
                    # Alert resolved
                    resolved_alert = self.active_alerts.pop(rule['name'])
                    resolved_alert['resolved_at'] = current_time
                    resolved_alert['duration'] = (current_time - resolved_alert['triggered_at']).total_seconds()
                    
                    self.alert_history.append(resolved_alert)
                    logger.info(f"ALERT RESOLVED: {rule['name']}")
                    
            except Exception as e:
                logger.error(f"Error checking alert rule {rule['name']}: {e}")
    
    def get_active_alerts(self) -> List[Dict]:
        """Get all currently active alerts."""
        return list(self.active_alerts.values())
    
    def get_alert_history(self, hours: int = 24) -> List[Dict]:
        """Get alert history for the specified time period."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        return [
            alert for alert in self.alert_history
            if alert['triggered_at'] > cutoff_time
        ]
    
    def _register_default_alerts(self):
        """Register default system alerts."""
        
        # High CPU usage
        self.add_alert_rule(
            'high_cpu_usage',
            lambda m, t: m.gauges.get('system.cpu_percent', 0) > t,
            80.0,
            'CPU usage is above 80%',
            'warning'
        )
        
        # High memory usage
        self.add_alert_rule(
            'high_memory_usage',
            lambda m, t: m.gauges.get('system.memory_percent', 0) > t,
            85.0,
            'Memory usage is above 85%',
            'warning'
        )
        
        # High error rate
        def check_error_rate(metrics, threshold):
            recent_requests = [r for r in metrics.request_times 
                             if r['timestamp'] > datetime.utcnow() - timedelta(minutes=5)]
            if len(recent_requests) < 10:  # Not enough data
                return False
            error_rate = sum(1 for r in recent_requests if r['status_code'] >= 400) / len(recent_requests)
            return error_rate > threshold / 100
        
        self.add_alert_rule(
            'high_error_rate',
            check_error_rate,
            10.0,  # 10% error rate
            'Error rate is above 10% in the last 5 minutes',
            'critical'
        )
        
        # Slow response times
        def check_slow_responses(metrics, threshold):
            recent_requests = [r for r in metrics.request_times 
                             if r['timestamp'] > datetime.utcnow() - timedelta(minutes=5)]
            if len(recent_requests) < 5:
                return False
            avg_time = sum(r['response_time'] for r in recent_requests) / len(recent_requests)
            return avg_time > threshold
        
        self.add_alert_rule(
            'slow_response_times',
            check_slow_responses,
            2.0,  # 2 seconds average
            'Average response time is above 2 seconds',
            'warning'
        )


class HealthChecker:
    """Performs health checks on various system components."""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.checks = {}
        self.last_check_results = {}
        
        # Register default health checks
        self._register_default_checks()
    
    def add_health_check(self, name: str, check_func: callable, 
                        timeout: int = 30, critical: bool = False):
        """Add a new health check."""
        self.checks[name] = {
            'function': check_func,
            'timeout': timeout,
            'critical': critical
        }
    
    def run_health_checks(self) -> Dict:
        """Run all registered health checks."""
        results = {
            'timestamp': datetime.utcnow().isoformat(),
            'overall_status': 'healthy',
            'checks': {}
        }
        
        critical_failures = 0
        
        for name, check_config in self.checks.items():
            try:
                start_time = time.time()
                
                # Run check with timeout
                check_result = check_config['function']()
                
                execution_time = time.time() - start_time
                
                result = {
                    'status': 'healthy' if check_result['healthy'] else 'unhealthy',
                    'message': check_result.get('message', ''),
                    'execution_time': execution_time,
                    'critical': check_config['critical'],
                    'details': check_result.get('details', {})
                }
                
                if not check_result['healthy']:
                    if check_config['critical']:
                        critical_failures += 1
                        results['overall_status'] = 'critical'
                    elif results['overall_status'] == 'healthy':
                        results['overall_status'] = 'degraded'
                
                results['checks'][name] = result
                
            except Exception as e:
                result = {
                    'status': 'error',
                    'message': f'Health check failed: {str(e)}',
                    'execution_time': 0,
                    'critical': check_config['critical'],
                    'details': {}
                }
                
                results['checks'][name] = result
                
                if check_config['critical']:
                    critical_failures += 1
                    results['overall_status'] = 'critical'
                elif results['overall_status'] == 'healthy':
                    results['overall_status'] = 'degraded'
        
        self.last_check_results = results
        return results
    
    def _register_default_checks(self):
        """Register default health checks."""
        
        def database_check():
            """Check database connectivity and basic operations."""
            try:
                # Test basic connectivity
                article_count = self.db_manager.get_article_count()
                
                # Test write operation
                test_query = "SELECT 1"
                with sqlite3.connect(self.db_manager.db_path) as conn:
                    conn.execute(test_query)
                
                return {
                    'healthy': True,
                    'message': f'Database operational with {article_count} articles',
                    'details': {'article_count': article_count}
                }
            except Exception as e:
                return {
                    'healthy': False,
                    'message': f'Database error: {str(e)}',
                    'details': {'error': str(e)}
                }
        
        def rss_feeds_check():
            """Check RSS feed validation status."""
            try:
                validation_summary = self.db_manager.get_feed_validation_summary()
                total_feeds = validation_summary.get('total', 0)
                ok_feeds = validation_summary.get('ok', 0)
                
                if total_feeds == 0:
                    return {
                        'healthy': False,
                        'message': 'No RSS feeds configured',
                        'details': validation_summary
                    }
                
                health_ratio = ok_feeds / total_feeds if total_feeds > 0 else 0
                
                return {
                    'healthy': health_ratio >= 0.8,  # At least 80% of feeds working
                    'message': f'{ok_feeds}/{total_feeds} RSS feeds operational',
                    'details': validation_summary
                }
            except Exception as e:
                return {
                    'healthy': False,
                    'message': f'RSS feeds check failed: {str(e)}',
                    'details': {'error': str(e)}
                }
        
        def disk_space_check():
            """Check available disk space."""
            try:
                disk_usage = psutil.disk_usage('/')
                free_gb = disk_usage.free / (1024**3)
                total_gb = disk_usage.total / (1024**3)
                percent_used = (disk_usage.used / disk_usage.total) * 100
                
                return {
                    'healthy': percent_used < 90,  # Less than 90% used
                    'message': f'{free_gb:.1f}GB free ({percent_used:.1f}% used)',
                    'details': {
                        'free_gb': free_gb,
                        'total_gb': total_gb,
                        'percent_used': percent_used
                    }
                }
            except Exception as e:
                return {
                    'healthy': False,
                    'message': f'Disk space check failed: {str(e)}',
                    'details': {'error': str(e)}
                }
        
        # Register checks
        self.add_health_check('database', database_check, critical=True)
        self.add_health_check('rss_feeds', rss_feeds_check, critical=False)
        self.add_health_check('disk_space', disk_space_check, critical=False)


def setup_monitoring(app: Flask, db_manager):
    """Set up monitoring for Flask application."""
    
    # Initialize monitoring components
    metrics = MetricsCollector()
    alerts = AlertManager(metrics)
    health = HealthChecker(db_manager)
    
    # Middleware for request tracking
    @app.before_request
    def before_request():
        g.start_time = time.time()
    
    @app.after_request
    def after_request(response):
        if hasattr(g, 'start_time'):
            response_time = time.time() - g.start_time
            
            # Record request metrics
            metrics.record_request(
                endpoint=request.endpoint or 'unknown',
                method=request.method,
                status_code=response.status_code,
                response_time=response_time
            )
            
            # Add response time header
            response.headers['X-Response-Time'] = f"{response_time:.3f}s"
        
        return response
    
    # Periodic alert checking
    def alert_checker():
        while True:
            try:
                alerts.check_alerts()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Alert checker error: {e}")
                time.sleep(60)
    
    alert_thread = threading.Thread(target=alert_checker, daemon=True)
    alert_thread.start()
    
    # Health check endpoints
    @app.route('/health')
    def health_check():
        """Simple health check endpoint."""
        return {'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()}
    
    @app.route('/health/detailed')
    def detailed_health_check():
        """Detailed health check with all components."""
        return health.run_health_checks()
    
    @app.route('/metrics')
    def metrics_endpoint():
        """Metrics endpoint for monitoring systems."""
        return metrics.get_metrics_summary()
    
    @app.route('/alerts')
    def alerts_endpoint():
        """Active alerts endpoint."""
        return {
            'active_alerts': alerts.get_active_alerts(),
            'alert_history': alerts.get_alert_history(hours=24)
        }
    
    logger.info("Monitoring and observability setup completed")
    
    return {
        'metrics': metrics,
        'alerts': alerts,
        'health': health
    }
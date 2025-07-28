"""Background job processing system for async operations."""

import threading
import queue
import time
import logging
import json
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import os
import signal

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class Job:
    """Represents a background job."""
    
    def __init__(self, job_id: str, job_type: str, task_func: Callable, 
                 args: tuple = (), kwargs: dict = None, 
                 priority: JobPriority = JobPriority.NORMAL,
                 timeout: int = 300, retries: int = 3):
        self.job_id = job_id
        self.job_type = job_type
        self.task_func = task_func
        self.args = args
        self.kwargs = kwargs or {}
        self.priority = priority
        self.timeout = timeout
        self.retries = retries
        
        # Status tracking
        self.status = JobStatus.PENDING
        self.created_at = datetime.utcnow()
        self.started_at = None
        self.completed_at = None
        self.result = None
        self.error = None
        self.progress = 0
        self.logs = []
        self.attempt = 0
    
    def __lt__(self, other):
        """For priority queue sorting."""
        return self.priority.value > other.priority.value
    
    def add_log(self, message: str, level: str = "INFO"):
        """Add log message to job."""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': level,
            'message': message
        }
        self.logs.append(log_entry)
        logger.log(getattr(logging, level), f"Job {self.job_id}: {message}")
    
    def update_progress(self, progress: int, message: str = None):
        """Update job progress."""
        self.progress = max(0, min(100, progress))
        if message:
            self.add_log(f"Progress: {self.progress}% - {message}")
    
    def to_dict(self) -> Dict:
        """Convert job to dictionary for API responses."""
        return {
            'job_id': self.job_id,
            'job_type': self.job_type,
            'status': self.status.value,
            'priority': self.priority.value,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'progress': self.progress,
            'result': self.result,
            'error': self.error,
            'timeout': self.timeout,
            'retries': self.retries,
            'attempt': self.attempt,
            'logs': self.logs[-10:]  # Last 10 log entries
        }


class BackgroundJobManager:
    """Manages background job execution with worker threads."""
    
    def __init__(self, num_workers: int = 3, max_jobs: int = 1000):
        self.num_workers = num_workers
        self.max_jobs = max_jobs
        
        # Job storage
        self.jobs: Dict[str, Job] = {}
        self.job_queue = queue.PriorityQueue(maxsize=max_jobs)
        
        # Worker management
        self.workers: List[threading.Thread] = []
        self.running = False
        self.shutdown_event = threading.Event()
        
        # Statistics
        self.stats = {
            'total_jobs': 0,
            'completed_jobs': 0,
            'failed_jobs': 0,
            'cancelled_jobs': 0,
            'avg_execution_time': 0.0,
            'total_execution_time': 0.0
        }
        
        # Job type registry
        self.job_handlers: Dict[str, Callable] = {}
        
        # Register built-in job types
        self._register_builtin_handlers()
    
    def start(self):
        """Start the job manager and worker threads."""
        if self.running:
            logger.warning("Job manager is already running")
            return
        
        self.running = True
        self.shutdown_event.clear()
        
        # Start worker threads
        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"JobWorker-{i+1}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
        
        logger.info(f"Started background job manager with {self.num_workers} workers")
    
    def stop(self, timeout: int = 30):
        """Stop the job manager and wait for workers to finish."""
        if not self.running:
            return
        
        logger.info("Stopping background job manager...")
        self.running = False
        self.shutdown_event.set()
        
        # Wait for workers to finish
        for worker in self.workers:
            worker.join(timeout=timeout)
            if worker.is_alive():
                logger.warning(f"Worker {worker.name} did not shut down gracefully")
        
        # Cancel pending jobs
        pending_count = 0
        while not self.job_queue.empty():
            try:
                job = self.job_queue.get_nowait()
                job.status = JobStatus.CANCELLED
                job.completed_at = datetime.utcnow()
                pending_count += 1
            except queue.Empty:
                break
        
        if pending_count > 0:
            logger.info(f"Cancelled {pending_count} pending jobs")
        
        self.workers.clear()
        logger.info("Background job manager stopped")
    
    def register_handler(self, job_type: str, handler: Callable):
        """Register a handler for a specific job type."""
        self.job_handlers[job_type] = handler
        logger.info(f"Registered handler for job type: {job_type}")
    
    def submit_job(self, job_type: str, job_data: Dict, 
                   priority: JobPriority = JobPriority.NORMAL,
                   timeout: int = 300, retries: int = 3) -> str:
        """Submit a new job for background processing."""
        if not self.running:
            raise RuntimeError("Job manager is not running")
        
        if self.job_queue.full():
            raise RuntimeError("Job queue is full")
        
        # Generate unique job ID
        job_id = f"{job_type}_{int(time.time() * 1000)}"
        
        # Get handler function
        if job_type not in self.job_handlers:
            raise ValueError(f"No handler registered for job type: {job_type}")
        
        handler = self.job_handlers[job_type]
        
        # Create job
        job = Job(
            job_id=job_id,
            job_type=job_type,
            task_func=handler,
            args=(),
            kwargs=job_data,
            priority=priority,
            timeout=timeout,
            retries=retries
        )
        
        # Store and queue job
        self.jobs[job_id] = job
        self.job_queue.put(job)
        
        job.add_log(f"Job submitted with priority {priority.name}")
        self.stats['total_jobs'] += 1
        
        logger.info(f"Submitted job {job_id} of type {job_type}")
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get job status and details."""
        job = self.jobs.get(job_id)
        return job.to_dict() if job else None
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or running job."""
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            return False
        
        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.utcnow()
        job.add_log("Job cancelled by user")
        
        self.stats['cancelled_jobs'] += 1
        logger.info(f"Cancelled job {job_id}")
        return True
    
    def get_queue_status(self) -> Dict:
        """Get queue and worker status."""
        pending_jobs = sum(1 for job in self.jobs.values() if job.status == JobStatus.PENDING)
        running_jobs = sum(1 for job in self.jobs.values() if job.status == JobStatus.RUNNING)
        
        return {
            'running': self.running,
            'workers': len(self.workers),
            'queue_size': self.job_queue.qsize(),
            'pending_jobs': pending_jobs,
            'running_jobs': running_jobs,
            'total_jobs': len(self.jobs),
            'stats': self.stats
        }
    
    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove old completed jobs from memory."""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        jobs_to_remove = []
        
        for job_id, job in self.jobs.items():
            if (job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED] 
                and job.completed_at and job.completed_at < cutoff_time):
                jobs_to_remove.append(job_id)
        
        for job_id in jobs_to_remove:
            del self.jobs[job_id]
        
        if jobs_to_remove:
            logger.info(f"Cleaned up {len(jobs_to_remove)} old jobs")
    
    def _worker_loop(self):
        """Main worker thread loop."""
        worker_name = threading.current_thread().name
        logger.info(f"Worker {worker_name} started")
        
        while self.running:
            try:
                # Get next job with timeout
                try:
                    job = self.job_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                if not self.running:
                    # Put job back if shutting down
                    self.job_queue.put(job)
                    break
                
                # Execute job
                self._execute_job(job, worker_name)
                
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}")
                time.sleep(1)
        
        logger.info(f"Worker {worker_name} stopped")
    
    def _execute_job(self, job: Job, worker_name: str):
        """Execute a single job with thread-safe timeout handling."""
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        job.attempt += 1
        job.add_log(f"Started execution on worker {worker_name} (attempt {job.attempt})")
        
        start_time = time.time()
        
        try:
            # Thread-safe timeout handling using threading.Timer
            timeout_occurred = threading.Event()
            timer = None
            
            def timeout_handler():
                timeout_occurred.set()
                job.add_log(f"Job timeout after {job.timeout} seconds", "ERROR")
            
            # Start timeout timer
            timer = threading.Timer(job.timeout, timeout_handler)
            timer.start()
            
            try:
                # Execute the job function
                result = job.task_func(job, **job.kwargs)
                
                # Check if timeout occurred during execution
                if timeout_occurred.is_set():
                    raise TimeoutError(f"Job exceeded timeout of {job.timeout} seconds")
                
                job.result = result
                job.status = JobStatus.COMPLETED
                job.add_log("Job completed successfully")
                self.stats['completed_jobs'] += 1
                
            finally:
                # Cancel timeout timer
                if timer:
                    timer.cancel()
            
        except Exception as e:
            error_msg = f"Job failed: {str(e)}"
            job.error = error_msg
            job.add_log(error_msg, "ERROR")
            job.add_log(f"Traceback: {traceback.format_exc()}", "DEBUG")
            
            # Retry logic
            if job.attempt < job.retries:
                job.status = JobStatus.PENDING
                job.add_log(f"Retrying job (attempt {job.attempt + 1}/{job.retries})")
                self.job_queue.put(job)
                return
            else:
                job.status = JobStatus.FAILED
                job.add_log(f"Job failed after {job.retries} attempts", "ERROR")
                self.stats['failed_jobs'] += 1
        
        # Update timing statistics
        execution_time = time.time() - start_time
        job.completed_at = datetime.utcnow()
        
        self.stats['total_execution_time'] += execution_time
        completed_jobs = self.stats['completed_jobs'] + self.stats['failed_jobs']
        if completed_jobs > 0:
            self.stats['avg_execution_time'] = self.stats['total_execution_time'] / completed_jobs
        
        job.add_log(f"Execution completed in {execution_time:.2f} seconds")
    
    def _register_builtin_handlers(self):
        """Register built-in job handlers."""
        
        def rss_collection_job(job: Job, user_id: str = None, max_articles: int = 10, **kwargs):
            """RSS collection background job."""
            try:
                from .incremental_collector import IncrementalCollector
            except ImportError:
                from incremental_collector import IncrementalCollector
            
            job.update_progress(10, "Initializing RSS collector")
            
            collector = IncrementalCollector()
            job.update_progress(25, "Starting collection from RSS feeds")
            
            if user_id:
                # Get user categories for targeted collection
                try:
                    from .database import DatabaseManager
                except ImportError:
                    from database import DatabaseManager
                db = DatabaseManager()
                user_prefs = db.get_user_preferences(user_id)
                if user_prefs:
                    categories = user_prefs.get('selected_categories', [])
                    job.add_log(f"Collecting for user {user_id} categories: {categories}")
                else:
                    categories = None
            else:
                categories = None
            
            job.update_progress(50, "Fetching articles from feeds")
            
            # Run collection
            if categories:
                # Use incremental collection for specific categories
                job.update_progress(50, f"Processing {len(categories)} categories")
                stats = collector.run_incremental_collection(max_articles, categories)
                job.add_log(f"Collection stats: {stats}")
            else:
                # Collect all categories using incremental collection
                job.update_progress(50, "Processing all categories")
                stats = collector.run_incremental_collection(max_articles)
            
            job.update_progress(80, f"Collected {stats.get('new', 0)} new articles, {stats.get('updated', 0)} updated")
            
            job.update_progress(100, "Collection completed")
            return {
                'new_articles': stats.get('new', 0),
                'updated_articles': stats.get('updated', 0),
                'skipped': stats.get('skipped', 0),
                'errors': stats.get('errors', 0),
                'feeds_processed': stats.get('feeds_processed', 0),
                'categories_processed': len(categories) if categories else 'all'
            }
        
        def ai_processing_job(job: Job, article_limit: int = 50, **kwargs):
            """AI processing background job."""
            try:
                from .enhanced_ai_processor import EnhancedAIProcessor
            except ImportError:
                from enhanced_ai_processor import EnhancedAIProcessor
            processor_class = EnhancedAIProcessor
            job.add_log("Using enhanced AI processor with LLM Router")
            
            job.update_progress(10, "Initializing AI processor")
            
            processor = processor_class()
            job.update_progress(25, "Starting AI processing cycle")
            
            result = processor.run_enhanced_processing_cycle()
            
            job.update_progress(100, "AI processing completed")
            return result
        
        def email_delivery_job(job: Job, user_id: str, digest_data: Dict = None, **kwargs):
            """Email delivery background job using refactored email system."""
            import sys
            import os
            
            # Add project root and src to Python path for imports
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            src_dir = current_dir
            
            for path in [project_root, src_dir]:
                if path not in sys.path:
                    sys.path.insert(0, path)
            
            job.add_log(f"Debug: Current dir: {current_dir}")
            job.add_log(f"Debug: Project root: {project_root}")
            job.add_log(f"Debug: Python path: {sys.path[:3]}")
            
            try:
                from .email_delivery_refactored import RefactoredEmailDeliveryManager
                from .enhanced_ai_processor import EnhancedAIProcessor
                from .user_interface import DigestGenerator
                from .database import DatabaseManager
            except ImportError:
                from email_delivery_refactored import RefactoredEmailDeliveryManager
                from enhanced_ai_processor import EnhancedAIProcessor
                from user_interface import DigestGenerator
                from database import DatabaseManager
            
            job.update_progress(10, f"Preparing email delivery for user {user_id}")
            
            # Initialize managers with proper dependencies
            try:
                db_manager = DatabaseManager()
                ai_processor = EnhancedAIProcessor()
                email_manager = RefactoredEmailDeliveryManager(db_manager, ai_processor)
                
                # Check configuration
                if not email_manager.is_configured():
                    config_status = email_manager.get_configuration_status()
                    error_msg = f"Email system not configured: {', '.join(config_status.get('errors', ['Unknown error']))}"
                    job.add_log(error_msg, "ERROR")
                    raise Exception(error_msg)
                
                job.update_progress(25, "Email system initialized and configured")
                
            except Exception as e:
                job.add_log(f"Failed to initialize email system: {e}", "ERROR")
                raise Exception(f"Email system initialization failed: {e}")
            
            if not digest_data:
                # Generate digest using existing articles
                job.update_progress(40, "Generating digest from existing articles")
                try:
                    digest_generator = DigestGenerator(db_manager)
                    articles = digest_generator.get_personalized_articles(user_id)
                    
                    if not articles:
                        job.add_log("No articles found for user's categories", "WARNING")
                        # Create minimal digest with placeholder
                        user_prefs = db_manager.get_user_preferences(user_id)
                        digest_data = {
                            'categories': {
                                'No Articles': [{
                                    'id': 1,
                                    'title': 'No new articles found',
                                    'ai_summary': f"No articles were found for your selected categories: {', '.join(user_prefs['selected_categories']) if user_prefs else 'Unknown'}. Try running the collection again later.",
                                    'source_link': '#',
                                    'author': 'News Digest System',
                                    'publication_date': datetime.now().isoformat()
                                }]
                            },
                            'user_id': user_id,
                            'generated_at': datetime.now().isoformat()
                        }
                    else:
                        # Group articles by category for proper email structure
                        digest_data = {
                            'categories': {},
                            'user_id': user_id,
                            'generated_at': datetime.now().isoformat()
                        }
                        
                        # Get user preferences for category filtering
                        user_prefs = db_manager.get_user_preferences(user_id)
                        if not user_prefs:
                            raise Exception(f"User {user_id} not found")
                        
                        # Group articles by their AI categories
                        by_category = {}
                        for article in articles:
                            article_categories = article.get('ai_categories', ['Uncategorized'])
                            if isinstance(article_categories, str):
                                article_categories = [article_categories]
                            
                            for category in article_categories:
                                if category in user_prefs['selected_categories']:
                                    if category not in by_category:
                                        by_category[category] = []
                                    by_category[category].append(article)
                        
                        # Convert to email format
                        total_articles = 0
                        for category, category_articles in by_category.items():
                            digest_data['categories'][category] = []
                            for article in category_articles[:5]:  # Limit to 5 per category
                                email_article = {
                                    'id': article.get('id', 0),
                                    'title': article.get('title', 'No Title'),
                                    'ai_summary': article.get('ai_summary') or article.get('original_summary', '')[:300] + '...' if article.get('original_summary', '') else 'No summary available',
                                    'source_link': article.get('source_link', '#'),
                                    'author': article.get('author', 'Unknown'),
                                    'publication_date': article.get('publication_date', datetime.now().isoformat())
                                }
                                digest_data['categories'][category].append(email_article)
                                total_articles += 1
                        
                        job.add_log(f"Prepared {total_articles} articles across {len(by_category)} categories")
                
                except Exception as e:
                    job.add_log(f"Failed to generate digest: {e}", "ERROR")
                    raise Exception(f"Digest generation failed: {e}")
            
            job.update_progress(70, "Sending email digest")
            
            try:
                success, message = email_manager.deliver_digest_email(user_id, digest_data)
                
                if success:
                    job.update_progress(100, "Email sent successfully")
                    job.add_log(f"Email delivered: {message}", "INFO")
                    return {'success': True, 'message': message}
                else:
                    job.add_log(f"Email delivery failed: {message}", "ERROR")
                    raise Exception(f"Email delivery failed: {message}")
                    
            except Exception as e:
                job.add_log(f"Email send error: {e}", "ERROR")
                raise Exception(f"Email delivery failed: {e}")
        
        # Register handlers
        self.register_handler('rss_collection', rss_collection_job)
        self.register_handler('ai_processing', ai_processing_job)
        self.register_handler('email_delivery', email_delivery_job)


# Global job manager instance
job_manager = BackgroundJobManager()

def start_job_manager():
    """Start the global job manager."""
    job_manager.start()

def stop_job_manager():
    """Stop the global job manager."""
    job_manager.stop()

def submit_background_job(job_type: str, job_data: Dict, 
                         priority: JobPriority = JobPriority.NORMAL) -> str:
    """Submit a job to the background processor."""
    return job_manager.submit_job(job_type, job_data, priority)

def get_job_status(job_id: str) -> Optional[Dict]:
    """Get status of a background job."""
    return job_manager.get_job_status(job_id)
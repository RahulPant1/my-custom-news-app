"""Enhanced database manager with connection pooling and performance optimizations."""

import sqlite3
import threading
import contextlib
from queue import Queue, Empty, Full
from typing import Optional, Dict, List, Callable, Any
import logging
import time
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DatabaseConnectionPool:
    """Thread-safe SQLite connection pool with optimizations."""
    
    def __init__(self, db_path: str, max_connections: int = 10, timeout: int = 30):
        self.db_path = db_path
        self.max_connections = max_connections
        self.timeout = timeout
        self._pool = Queue(maxsize=max_connections)
        self._lock = threading.Lock()
        self._created_connections = 0
        
        # Performance tracking
        self.stats = {
            'total_queries': 0,
            'slow_queries': 0,
            'avg_query_time': 0.0,
            'connection_reuses': 0,
            'pool_hits': 0,
            'pool_misses': 0
        }
        
        # Initialize with some connections
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Pre-populate pool with connections."""
        initial_connections = min(3, self.max_connections)
        for _ in range(initial_connections):
            try:
                conn = self._create_connection()
                self._pool.put_nowait(conn)
            except Full:
                break
    
    def _create_connection(self) -> sqlite3.Connection:
        """Create a new optimized database connection."""
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.timeout,
            check_same_thread=False,
            isolation_level=None  # Autocommit mode for better performance
        )
        
        # Enable performance optimizations
        conn.execute('PRAGMA journal_mode=WAL')  # Write-Ahead Logging
        conn.execute('PRAGMA synchronous=NORMAL')  # Balanced safety/performance
        conn.execute('PRAGMA cache_size=10000')  # 10MB cache
        conn.execute('PRAGMA temp_store=MEMORY')  # Keep temp tables in memory
        conn.execute('PRAGMA mmap_size=268435456')  # 256MB memory map
        conn.execute('PRAGMA foreign_keys=ON')  # Enable foreign keys
        
        # Row factory for dict-like access
        conn.row_factory = sqlite3.Row
        
        with self._lock:
            self._created_connections += 1
        
        logger.debug(f"Created new database connection. Total: {self._created_connections}")
        return conn
    
    @contextlib.contextmanager
    def get_connection(self):
        """Context manager for getting database connections."""
        conn = None
        start_time = time.time()
        
        try:
            # Try to get from pool first
            try:
                conn = self._pool.get_nowait()
                self.stats['pool_hits'] += 1
                self.stats['connection_reuses'] += 1
            except Empty:
                self.stats['pool_misses'] += 1
                # Create new connection if pool is empty and under limit
                with self._lock:
                    if self._created_connections < self.max_connections:
                        conn = self._create_connection()
                    else:
                        # Wait for connection to become available
                        conn = self._pool.get(timeout=self.timeout)
                        self.stats['pool_hits'] += 1
            
            # Verify connection is still good
            if not self._is_connection_valid(conn):
                conn.close()
                conn = self._create_connection()
            
            yield conn
            
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            raise
        finally:
            # Return connection to pool
            if conn:
                try:
                    if self._is_connection_valid(conn):
                        self._pool.put_nowait(conn)
                    else:
                        conn.close()
                        with self._lock:
                            self._created_connections -= 1
                except Full:
                    # Pool is full, close the connection
                    conn.close()
                    with self._lock:
                        self._created_connections -= 1
    
    def _is_connection_valid(self, conn: sqlite3.Connection) -> bool:
        """Check if connection is still valid."""
        try:
            conn.execute('SELECT 1').fetchone()
            return True
        except:
            return False
    
    def execute_query(self, query: str, params: tuple = (), 
                     fetch_mode: str = 'all') -> Any:
        """Execute query with performance tracking."""
        start_time = time.time()
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                
                if fetch_mode == 'one':
                    result = cursor.fetchone()
                elif fetch_mode == 'all':
                    result = cursor.fetchall()
                elif fetch_mode == 'none':
                    result = cursor.rowcount
                else:
                    result = cursor
                
                # Update stats
                query_time = time.time() - start_time
                self.stats['total_queries'] += 1
                
                # Track slow queries (>100ms)
                if query_time > 0.1:
                    self.stats['slow_queries'] += 1
                    logger.warning(f"Slow query ({query_time:.3f}s): {query[:100]}")
                
                # Update average query time
                total_queries = self.stats['total_queries']
                self.stats['avg_query_time'] = (
                    (self.stats['avg_query_time'] * (total_queries - 1) + query_time) / total_queries
                )
                
                return result
                
        except Exception as e:
            logger.error(f"Query execution failed: {query[:100]} - {e}")
            raise
    
    def execute_transaction(self, operations: List[Callable]):
        """Execute multiple operations in a transaction."""
        with self.get_connection() as conn:
            try:
                conn.execute('BEGIN IMMEDIATE')
                
                for operation in operations:
                    operation(conn)
                
                conn.execute('COMMIT')
                
            except Exception as e:
                conn.execute('ROLLBACK')
                logger.error(f"Transaction failed: {e}")
                raise
    
    def get_stats(self) -> Dict:
        """Get connection pool statistics."""
        with self._lock:
            pool_size = self._pool.qsize()
            
        return {
            **self.stats,
            'active_connections': self._created_connections,
            'pooled_connections': pool_size,
            'max_connections': self.max_connections,
            'pool_efficiency': self.stats['pool_hits'] / max(1, self.stats['pool_hits'] + self.stats['pool_misses'])
        }
    
    def close_all(self):
        """Close all connections in the pool."""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except Empty:
                break
        
        with self._lock:
            self._created_connections = 0


class OptimizedDatabaseManager:
    """Enhanced database manager with performance optimizations."""
    
    def __init__(self, db_path: str = None, pool_size: int = 10):
        self.db_path = db_path or os.getenv('DATABASE_PATH', 'news_digest.db')
        self.pool = DatabaseConnectionPool(self.db_path, max_connections=pool_size)
        
        # Query cache for frequently accessed data
        self._query_cache = {}
        self._cache_ttl = {}
        self._cache_lock = threading.Lock()
        
        # Initialize database
        self.init_database()
        
        # Start background maintenance
        self._start_maintenance_thread()
    
    def init_database(self):
        """Initialize database with performance optimizations."""
        # Use the original database manager's init logic but with optimizations
        from database import DatabaseManager
        original_db = DatabaseManager(self.db_path)
        original_db.init_database()
        
        # Add additional performance indexes
        performance_indexes = [
            'CREATE INDEX IF NOT EXISTS idx_articles_user_categories ON articles(ai_categories) WHERE ai_categories IS NOT NULL',
            'CREATE INDEX IF NOT EXISTS idx_articles_trending ON articles(trending_flag, date_collected) WHERE trending_flag = 1',
            'CREATE INDEX IF NOT EXISTS idx_articles_recent ON articles(date_collected DESC)',
            'CREATE INDEX IF NOT EXISTS idx_user_email ON user_preferences(email)',
            'CREATE INDEX IF NOT EXISTS idx_delivery_user_status ON email_deliveries(user_id, delivery_status)',
            'CREATE INDEX IF NOT EXISTS idx_feedback_user_date ON feedback_history(user_id, created_at)',
            'CREATE INDEX IF NOT EXISTS idx_feed_tracking_url_date ON feed_tracking(feed_url, last_fetched)',
        ]
        
        for index_sql in performance_indexes:
            try:
                self.pool.execute_query(index_sql, fetch_mode='none')
                logger.debug(f"Created performance index: {index_sql.split('idx_')[1].split(' ')[0]}")
            except Exception as e:
                logger.warning(f"Failed to create index: {e}")
    
    def get_articles_by_categories_cached(self, categories: List[str], 
                                        limit: int = 20, cache_ttl: int = 300) -> List[Dict]:
        """Get articles with caching for better performance."""
        cache_key = f"articles:{','.join(sorted(categories))}:{limit}"
        
        # Check cache first
        with self._cache_lock:
            if cache_key in self._query_cache:
                cache_time = self._cache_ttl.get(cache_key, 0)
                if time.time() - cache_time < cache_ttl:
                    logger.debug(f"Cache hit for {cache_key}")
                    return self._query_cache[cache_key]
        
        # Query database with optimized SQL
        placeholders = ','.join(['?'] * len(categories))
        query = f'''
            SELECT id, title, author, publication_date, source_link, 
                   original_summary, ai_categories, ai_summary, trending_flag, date_collected
            FROM articles 
            WHERE ai_categories IS NOT NULL 
            AND ({' OR '.join(['ai_categories LIKE ?' for _ in categories])})
            ORDER BY trending_flag DESC, date_collected DESC 
            LIMIT ?
        '''
        
        params = [f'%"{cat}"%' for cat in categories] + [limit]
        rows = self.pool.execute_query(query, tuple(params))
        
        # Convert to dict format
        articles = []
        for row in rows:
            articles.append({
                'id': row['id'],
                'title': row['title'],
                'author': row['author'],
                'publication_date': row['publication_date'],
                'source_link': row['source_link'],
                'original_summary': row['original_summary'],
                'ai_categories': json.loads(row['ai_categories']) if row['ai_categories'] else [],
                'ai_summary': row['ai_summary'],
                'trending_flag': bool(row['trending_flag']),
                'date_collected': row['date_collected']
            })
        
        # Update cache
        with self._cache_lock:
            self._query_cache[cache_key] = articles
            self._cache_ttl[cache_key] = time.time()
        
        logger.debug(f"Cached {len(articles)} articles for {cache_key}")
        return articles
    
    def bulk_insert_articles(self, articles: List[Dict]) -> Dict[str, int]:
        """Optimized bulk insert for articles."""
        if not articles:
            return {'inserted': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
        
        stats = {'inserted': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
        
        def batch_operation(conn):
            cursor = conn.cursor()
            
            for article in articles:
                try:
                    # Check for duplicates using optimized query
                    cursor.execute('''
                        SELECT id FROM articles 
                        WHERE source_link = ? OR content_hash = ? 
                        LIMIT 1
                    ''', (article['source_link'], article.get('content_hash')))
                    
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Update existing
                        cursor.execute('''
                            UPDATE articles 
                            SET original_summary = COALESCE(?, original_summary),
                                author = COALESCE(?, author),
                                publication_date = COALESCE(?, publication_date),
                                date_updated = CURRENT_TIMESTAMP
                            WHERE id = ?
                        ''', (
                            article.get('original_summary'),
                            article.get('author'),
                            article.get('publication_date'),
                            existing['id']
                        ))
                        stats['updated'] += 1
                    else:
                        # Insert new
                        cursor.execute('''
                            INSERT INTO articles 
                            (title, author, publication_date, source_link, original_summary, 
                             rss_category, ai_categories, ai_summary, trending_flag, 
                             content_hash, title_hash, guid, etag, last_modified)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            article['title'],
                            article.get('author'),
                            article.get('publication_date'),
                            article['source_link'],
                            article.get('original_summary'),
                            article.get('rss_category'),
                            json.dumps(article.get('ai_categories', [])),
                            article.get('ai_summary'),
                            article.get('trending_flag', False),
                            article.get('content_hash'),
                            article.get('title_hash'),
                            article.get('guid'),
                            article.get('etag'),
                            article.get('last_modified')
                        ))
                        stats['inserted'] += 1
                        
                except Exception as e:
                    logger.error(f"Error processing article '{article.get('title', 'Unknown')}': {e}")
                    stats['errors'] += 1
        
        try:
            self.pool.execute_transaction([batch_operation])
            
            # Clear relevant caches
            self._clear_article_cache()
            
            logger.info(f"Bulk insert complete: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Bulk insert failed: {e}")
            stats['errors'] = len(articles)
            return stats
    
    def get_user_digest_optimized(self, user_id: str) -> Optional[Dict]:
        """Get user preferences with caching."""
        cache_key = f"user:{user_id}"
        
        # Check cache
        with self._cache_lock:
            if cache_key in self._query_cache:
                cache_time = self._cache_ttl.get(cache_key, 0)
                if time.time() - cache_time < 600:  # 10 minute cache
                    return self._query_cache[cache_key]
        
        # Query database
        query = '''
            SELECT user_id, email, selected_categories, digest_frequency,
                   articles_per_digest, preferred_output_format, feedback_history
            FROM user_preferences 
            WHERE user_id = ?
        '''
        
        row = self.pool.execute_query(query, (user_id,), fetch_mode='one')
        
        if row:
            user_data = {
                'user_id': row['user_id'],
                'email': row['email'],
                'selected_categories': json.loads(row['selected_categories']) if row['selected_categories'] else [],
                'digest_frequency': row['digest_frequency'],
                'articles_per_digest': row['articles_per_digest'],
                'preferred_output_format': row['preferred_output_format'],
                'feedback_history': json.loads(row['feedback_history']) if row['feedback_history'] else {}
            }
            
            # Cache the result
            with self._cache_lock:
                self._query_cache[cache_key] = user_data
                self._cache_ttl[cache_key] = time.time()
            
            return user_data
        
        return None
    
    def _clear_article_cache(self):
        """Clear article-related cache entries."""
        with self._cache_lock:
            keys_to_remove = [k for k in self._query_cache.keys() if k.startswith('articles:')]
            for key in keys_to_remove:
                del self._query_cache[key]
                if key in self._cache_ttl:
                    del self._cache_ttl[key]
    
    def _start_maintenance_thread(self):
        """Start background thread for cache cleanup and database maintenance."""
        def maintenance_loop():
            while True:
                try:
                    # Cache cleanup (every 5 minutes)
                    current_time = time.time()
                    with self._cache_lock:
                        expired_keys = [
                            k for k, t in self._cache_ttl.items() 
                            if current_time - t > 1800  # 30 minutes
                        ]
                        for key in expired_keys:
                            self._query_cache.pop(key, None)
                            self._cache_ttl.pop(key, None)
                    
                    if expired_keys:
                        logger.debug(f"Cleaned {len(expired_keys)} expired cache entries")
                    
                    # Database maintenance (every hour)
                    if int(current_time) % 3600 < 300:  # Within 5 minutes of the hour
                        self._run_database_maintenance()
                    
                    time.sleep(300)  # 5 minutes
                    
                except Exception as e:
                    logger.error(f"Maintenance thread error: {e}")
                    time.sleep(60)  # Wait a minute before retrying
        
        maintenance_thread = threading.Thread(target=maintenance_loop, daemon=True)
        maintenance_thread.start()
        logger.info("Started database maintenance thread")
    
    def _run_database_maintenance(self):
        """Run periodic database maintenance tasks."""
        try:
            # VACUUM to reclaim space and optimize
            self.pool.execute_query('VACUUM', fetch_mode='none')
            
            # ANALYZE to update query planner statistics
            self.pool.execute_query('ANALYZE', fetch_mode='none')
            
            # Clean up old articles (older than 30 days)
            cutoff_date = (datetime.now() - timedelta(days=30)).isoformat()
            result = self.pool.execute_query(
                'DELETE FROM articles WHERE date_collected < ?', 
                (cutoff_date,), 
                fetch_mode='none'
            )
            
            if result > 0:
                logger.info(f"Cleaned up {result} old articles during maintenance")
            
        except Exception as e:
            logger.error(f"Database maintenance failed: {e}")
    
    def get_performance_stats(self) -> Dict:
        """Get database performance statistics."""
        pool_stats = self.pool.get_stats()
        
        with self._cache_lock:
            cache_stats = {
                'cache_entries': len(self._query_cache),
                'cache_size_mb': sum(len(str(v)) for v in self._query_cache.values()) / 1024 / 1024
            }
        
        return {
            **pool_stats,
            **cache_stats,
            'db_path': self.db_path
        }
    
    def close(self):
        """Close all database connections."""
        self.pool.close_all()
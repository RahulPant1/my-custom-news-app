#!/usr/bin/env python3
"""Mobile-responsive web interface for news digest."""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import os
import json
import subprocess
import sys
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
import logging
import threading

from .database import DatabaseManager
from .user_interface import DigestGenerator
# from .email_delivery import EmailDeliveryManager  # Migrated to email_delivery_refactored
try:
    from config import AI_CATEGORIES
except ImportError:
    AI_CATEGORIES = ['Science & Discovery', 'Technology & Gadgets', 'Health & Wellness', 'Business & Finance', 'Global Affairs', 'Environment & Climate', 'Good Vibes (Positive News)', 'Pop Culture & Lifestyle', 'For Young Minds (Youth-Focused)', 'DIY, Skills & How-To']

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Flask app with proper template and static directories
template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

# Ensure templates and static directories exist
os.makedirs(template_dir, exist_ok=True)
os.makedirs(static_dir, exist_ok=True)
error_template_path = os.path.join(template_dir, 'error.html')
if not os.path.exists(error_template_path):
    with open(error_template_path, 'w') as f:
        f.write('''
<!DOCTYPE html>
<html>
<head>
    <title>Error - News Digest</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .error { color: #d32f2f; font-size: 18px; margin-bottom: 20px; }
        .home-link { color: #1976d2; text-decoration: none; padding: 10px 20px; background: #e3f2fd; border-radius: 4px; display: inline-block; }
        .home-link:hover { background: #bbdefb; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚠️ Error</h1>
        <div class="error">{{ error }}</div>
        <a href="/" class="home-link">← Back to Home</a>
    </div>
</body>
</html>
        ''')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Template function for category icons
@app.template_global()
def get_category_icon(category):
    """Get emoji icon for category."""
    icons = {
        'Science & Discovery': '🔬',
        'Technology & Gadgets': '💻',
        'Health & Wellness': '🏥',
        'Business & Finance': '💼',
        'Global Affairs': '🌍',
        'Environment & Climate': '🌱',
        'Good Vibes (Positive News)': '😊',
        'Pop Culture & Lifestyle': '🎭',
        'For Young Minds (Youth-Focused)': '🎓',
        'DIY, Skills & How-To': '🔧'
    }
    return icons.get(category, '📰')

# Initialize services
db_manager = DatabaseManager()
digest_generator = DigestGenerator()
# Initialize with enhanced AI processor
from .email_delivery_refactored import RefactoredEmailDeliveryManager
from .enhanced_ai_processor import EnhancedAIProcessor
try:
    ai_processor = EnhancedAIProcessor()
    email_manager = RefactoredEmailDeliveryManager(db_manager, ai_processor)
except Exception as e:
    logger.warning(f"Failed to initialize email manager with AI processor: {e}")
    email_manager = RefactoredEmailDeliveryManager(db_manager, None)

# Initialize security middleware
# Import security middleware with fallback for missing dependencies
try:
    from .security_middleware import SecurityManager, USER_CREATION_SCHEMA, PIPELINE_RUN_SCHEMA
    SECURITY_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Security middleware not available ({e}). Running in basic mode.")
    SECURITY_AVAILABLE = False
    SecurityManager = None
    USER_CREATION_SCHEMA = None
    PIPELINE_RUN_SCHEMA = None
# Initialize security if available
if SECURITY_AVAILABLE:
    security = SecurityManager(app)
else:
    # Create dummy security decorators when security is not available
    class DummySecurity:
        def rate_limit(self, **kwargs):
            def decorator(f):
                return f
            return decorator
        
        def require_auth(self, f):
            return f
        
        def admin_required(self, f):
            return f
        
        def validate_input(self, schema):
            def decorator(f):
                return f
            return decorator
    
    security = DummySecurity()

# Initialize background job processing with fallback
try:
    from .background_jobs import job_manager, start_job_manager, submit_background_job, get_job_status, JobPriority
    BACKGROUND_JOBS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Background jobs not available ({e}). Using synchronous processing.")
    BACKGROUND_JOBS_AVAILABLE = False
    
    # Create dummy background job functions
    from enum import Enum
    class JobPriority(Enum):
        LOW = "low"
        NORMAL = "normal"
        HIGH = "high"
    
    def submit_background_job(job_type, job_data, priority=None):
        # Return a dummy job ID
        return "sync_job_" + str(hash(str(job_data)))[:8]
    
    def get_job_status(job_id):
        # Return completed status for dummy jobs
        return {"status": "completed", "result": {"success": True, "message": "Synchronous processing completed"}}
    
    def start_job_manager():
        pass

# Start job manager if available
if BACKGROUND_JOBS_AVAILABLE:
    start_job_manager()

# Setup monitoring and observability with fallback
try:
    from .monitoring import setup_monitoring
    monitoring_components = setup_monitoring(app, db_manager)
    MONITORING_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Monitoring not available ({e}). Basic logging only.")
    monitoring_components = None
    MONITORING_AVAILABLE = False

# Setup caching with fallback
try:
    from .caching import setup_caching, get_cached_db_operations, cache_response
    setup_caching(app)
    CACHING_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Caching not available ({e}). No caching enabled.")
    CACHING_AVAILABLE = False
    def cache_response(timeout=None):
        def decorator(f):
            return f
        return decorator
    def get_cached_db_operations():
        return db_manager
if CACHING_AVAILABLE:
    cached_db = get_cached_db_operations(db_manager)
else:
    cached_db = db_manager

@app.route('/')
@cache_response(ttl=120)  # Cache for 2 minutes
def home():
    """Homepage with user selection and digest preview."""
    try:
        # Get all users for selection (cached)
        users = []
        all_users = cached_db.get_all_users()
        
        # Handle both dict and list response types
        if isinstance(all_users, list):
            for user_prefs in all_users:
                users.append({
                    'user_id': user_prefs['user_id'],
                    'email': user_prefs.get('email', ''),
                    'categories': user_prefs.get('selected_categories', []),
                    'last_digest': user_prefs.get('last_digest_date', 'Never')
                })
        elif hasattr(all_users, 'items'):
            # Handle dict-like object
            for user_id, user_prefs in all_users.items():
                users.append({
                    'user_id': user_id,
                    'email': user_prefs.get('email', ''),
                    'categories': user_prefs.get('selected_categories', []),
                    'last_digest': user_prefs.get('last_digest_date', 'Never')
                })
        else:
            logger.warning(f"Unexpected all_users type: {type(all_users)}")
            users = []
        
        return render_template('home.html', users=users)
    except Exception as e:
        logger.error(f"Error loading home page: {e}")
        return render_template('error.html', error="Failed to load users"), 500

@app.route('/digest/<user_id>')
def view_digest(user_id: str):
    """View digest for a specific user."""
    try:
        # First check if user exists
        user_prefs = db_manager.get_user_preferences(user_id)
        if not user_prefs:
            return render_template('error.html', error=f"User {user_id} not found"), 404
        
        # Check if we have any articles at all
        try:
            total_articles = db_manager.get_article_count()
            logger.info(f"Total articles in database: {total_articles}")
            
            if total_articles == 0:
                return render_template('error.html', 
                                     error="No articles found in database. Please run the collector first to fetch articles."), 404
        except Exception as count_error:
            logger.warning(f"Could not get article count: {count_error}")
        
        # Generate digest - Get articles and create web-friendly structure
        try:
            articles = digest_generator.get_personalized_articles(user_id)
            if not articles:
                return render_template('error.html', 
                                     error=f"No articles found for user {user_id} with categories: {user_prefs.get('selected_categories', [])}. Please check if articles exist in the database and match the selected categories."), 404
            
            # Create digest data structure expected by web template
            digest_data = {
                'categories': digest_generator._deduplicate_articles_by_category(
                    articles, user_prefs['selected_categories']
                ),
                'generated_at': datetime.now().isoformat(),
                'user_id': user_id,
                'total_articles': len(articles)
            }
            
            logger.info(f"Generated digest for {user_id}: {len(digest_data.get('categories', {}))} categories with {digest_data['total_articles']} total articles")
        except Exception as digest_error:
            logger.error(f"Error generating digest for {user_id}: {digest_error}")
            # Try to get raw articles to debug
            try:
                articles = digest_generator.get_personalized_articles(user_id)
                article_count = len(articles) if articles else 0
                return render_template('error.html', 
                                     error=f"Failed to generate digest: {str(digest_error)}. Found {article_count} articles for user categories: {user_prefs.get('selected_categories', [])}"), 500
            except Exception as article_error:
                return render_template('error.html', 
                                     error=f"Failed to generate digest and retrieve articles: {str(digest_error)}. Article retrieval error: {str(article_error)}"), 500
        
        return render_template('digest.html', 
                             digest=digest_data, 
                             user_id=user_id,
                             user_prefs=user_prefs)
    except Exception as e:
        logger.error(f"Error in view_digest for {user_id}: {e}")
        return render_template('error.html', error=f"Failed to load user digest: {str(e)}"), 500

@app.route('/email-preview/<user_id>')
def email_preview(user_id: str):
    """Preview email version of digest."""
    try:
        # First check if user exists
        user_prefs = db_manager.get_user_preferences(user_id)
        if not user_prefs:
            return render_template('error.html', error=f"User {user_id} not found"), 404
        
        # Check if we have any articles
        try:
            total_articles = db_manager.get_article_count()
            if total_articles == 0:
                return render_template('error.html', 
                                     error="No articles found in database. Please run the collector first to fetch articles."), 404
        except Exception as count_error:
            logger.warning(f"Could not get article count: {count_error}")
        
        # Get personalized articles
        try:
            articles = digest_generator.get_personalized_articles(user_id)
            if not articles:
                return render_template('error.html', 
                                     error=f"No articles found for user {user_id} with categories: {user_prefs.get('selected_categories', [])}"), 404
            
            logger.info(f"Found {len(articles)} articles for email preview")
        except Exception as article_error:
            logger.error(f"Error getting articles for {user_id}: {article_error}")
            return render_template('error.html', error=f"Failed to get articles: {str(article_error)}"), 500
        
        # Create digest data structure
        try:
            digest_data = {
                'categories': digest_generator._deduplicate_articles_by_category(
                    articles, user_prefs['selected_categories']
                ),
                'generated_at': datetime.now().isoformat(),
                'user_id': user_id
            }
            
            # Generate HTML email content using mobile_card template for preview
            html_content = email_manager.generate_html_email(user_id, digest_data)
            
            return html_content
        except Exception as render_error:
            logger.error(f"Error rendering email preview for {user_id}: {render_error}")
            return render_template('error.html', error=f"Failed to generate email preview: {str(render_error)}"), 500
        
    except Exception as e:
        logger.error(f"Error in email_preview for {user_id}: {e}")
        return render_template('error.html', error=f"Failed to generate email preview: {str(e)}"), 500

@app.route('/api/send-digest/<user_id>', methods=['POST'])
@security.rate_limit(max_requests=10, window_minutes=60, per_user=True)
@security.require_auth
def send_digest(user_id: str):
    """API endpoint to send digest email."""
    try:
        # Get user preferences and articles
        user_prefs = db_manager.get_user_preferences(user_id)
        if not user_prefs:
            return jsonify({'success': False, 'message': f'User {user_id} not found'}), 404
            
        # Get personalized articles
        articles = digest_generator.get_personalized_articles(user_id)
        
        # Create proper digest structure for email
        email_digest_data = {
            'categories': digest_generator._deduplicate_articles_by_category(
                articles, user_prefs['selected_categories']
            ),
            'user_id': user_id,
            'generated_at': datetime.now().isoformat()
        }
        
        # Send email
        success, message = email_manager.deliver_digest_email(user_id, email_digest_data)
        
        # Ensure message is not empty/None
        if not message:
            message = f"Email delivery {'completed' if success else 'failed'}"
        
        return jsonify({
            'success': success,
            'message': str(message)
        })
    except Exception as e:
        logger.error(f"Error sending digest to {user_id}: {e}")
        return jsonify({
            'success': False,
            'message': f"Failed to send digest: {str(e)}"
        }), 500

@app.route('/create-user', methods=['GET', 'POST'])
@security.rate_limit(max_requests=20, window_minutes=60)
def create_user():
    """Create a new user with preferences."""
    if request.method == 'POST':
        try:
            user_id = request.form.get('user_id', '').strip()
            email = request.form.get('email', '').strip()
            selected_categories = request.form.getlist('categories')
            
            # Validate input
            if not user_id:
                flash('User ID is required', 'error')
                return render_template('create_user.html', categories=AI_CATEGORIES)
            
            if not email:
                flash('Email is required', 'error')
                return render_template('create_user.html', categories=AI_CATEGORIES)
            
            if not selected_categories:
                flash('At least one category must be selected', 'error')
                return render_template('create_user.html', categories=AI_CATEGORIES)
            
            # Validate email format
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                flash('Please enter a valid email address', 'error')
                return render_template('create_user.html', categories=AI_CATEGORIES)
            
            # Validate categories
            invalid_categories = [cat for cat in selected_categories if cat not in AI_CATEGORIES]
            if invalid_categories:
                flash(f'Invalid categories: {", ".join(invalid_categories)}', 'error')
                return render_template('create_user.html', categories=AI_CATEGORIES)
            
            # Create user
            user_prefs = {
                'user_id': user_id,
                'email': email,
                'selected_categories': selected_categories,
                'digest_frequency': 'daily',
                'articles_per_digest': 5,
                'preferred_output_format': 'html'
            }
            
            # Save to database
            logger.info(f"Attempting to create user: {user_id} with categories: {selected_categories}")
            logger.info(f"User data to insert: {user_prefs}")
            
            try:
                success = db_manager.insert_or_update_user_preferences(user_prefs)
                logger.info(f"Database insert result: {success}")
                
                # Verify the user was actually created
                verification = db_manager.get_user_preferences(user_id)
                logger.info(f"User verification after insert: {verification}")
                
                if success and verification:
                    flash(f'User "{user_id}" created successfully!', 'success')
                    logger.info(f"User {user_id} created and verified successfully")
                    return redirect(url_for('home'))
                else:
                    logger.error(f"Failed to insert user {user_id} into database. Success: {success}, Verification: {verification}")
                    flash('Failed to create user. Database insert failed.', 'error')
                    return render_template('create_user.html', categories=AI_CATEGORIES)
            except Exception as db_error:
                logger.error(f"Database error while creating user {user_id}: {db_error}", exc_info=True)
                flash(f'Database error: {str(db_error)}', 'error')
                return render_template('create_user.html', categories=AI_CATEGORIES)
                
        except Exception as e:
            logger.error(f"Error creating user {user_id}: {e}", exc_info=True)
            flash(f'An error occurred while creating the user: {str(e)}', 'error')
            return render_template('create_user.html', categories=AI_CATEGORIES)
    
    # GET request - show form
    return render_template('create_user.html', categories=AI_CATEGORIES)

@app.route('/operations')
def operations():
    """Operations dashboard for running main.py commands."""
    try:
        # Get all users for operation selection
        all_users = db_manager.get_all_users()
        users = []
        
        # Handle both dict and list response types
        if isinstance(all_users, list):
            for user_prefs in all_users:
                users.append({
                    'user_id': user_prefs['user_id'],
                    'email': user_prefs.get('email', ''),
                    'categories': user_prefs.get('selected_categories', [])
                })
        elif hasattr(all_users, 'items'):
            # Handle dict-like object
            for user_id, user_prefs in all_users.items():
                users.append({
                    'user_id': user_id,
                    'email': user_prefs.get('email', ''),
                    'categories': user_prefs.get('selected_categories', [])
                })
        else:
            logger.warning(f"Unexpected all_users type: {type(all_users)}")
            users = []
        
        return render_template('operations.html', users=users, categories=AI_CATEGORIES)
    except Exception as e:
        logger.error(f"Error loading operations page: {e}")
        return render_template('error.html', error="Failed to load operations"), 500

# Store for real-time pipeline logs
pipeline_logs = {}
pipeline_execution_status = {}  # Renamed to avoid conflict with function name

def add_pipeline_log(user_id: str, message: str, status: str = None, step: str = None):
    """Add a log entry for the user's pipeline execution (both memory and file)."""
    timestamp = datetime.now().strftime('%H:%M:%S')
    log_entry = f'[{timestamp}] {message}'
    
    # Memory-based logs for immediate web access
    if user_id not in pipeline_logs:
        pipeline_logs[user_id] = []
    
    pipeline_logs[user_id].append(log_entry)
    
    # Keep only last 50 logs to prevent memory issues
    if len(pipeline_logs[user_id]) > 50:
        pipeline_logs[user_id] = pipeline_logs[user_id][-50:]
    
    # Update status if provided (preserve existing data)
    if status or step:
        existing_status = pipeline_execution_status.get(user_id, {})
        pipeline_execution_status[user_id] = {
            **existing_status,  # Preserve all existing data including job IDs
            'status': status or existing_status.get('status', 'running'),
            'step': step or existing_status.get('step', 'Processing...')
        }
    
    # File-based logs for subprocess access
    import os
    import json
    
    try:
        logs_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        
        log_file = os.path.join(logs_dir, f'pipeline_{user_id}.json')
        
        # Read existing logs
        existing_logs = []
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    existing_logs = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                existing_logs = []
        
        # Add new log entry with structured data
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'status': status or 'info',
            'step': step,
            'formatted': log_entry
        }
        existing_logs.append(log_data)
        
        # Keep only last 50 logs
        if len(existing_logs) > 50:
            existing_logs = existing_logs[-50:]
        
        # Write back to file
        with open(log_file, 'w') as f:
            json.dump(existing_logs, f, indent=2)
            
    except Exception as e:
        logger.warning(f"Failed to write pipeline log to file: {e}")
    
    logger.info(f"Pipeline log for {user_id}: {message}")

def clear_pipeline_logs(user_id: str):
    """Clear pipeline logs for a user (both memory and file)."""
    if user_id in pipeline_logs:
        del pipeline_logs[user_id]
    if user_id in pipeline_execution_status:
        del pipeline_execution_status[user_id]
    
    # Clear file-based logs too
    import os
    try:
        logs_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
        log_file = os.path.join(logs_dir, f'pipeline_{user_id}.json')
        if os.path.exists(log_file):
            os.remove(log_file)
    except Exception as e:
        logger.warning(f"Failed to clear pipeline log file: {e}")

def load_pipeline_logs_from_file(user_id: str):
    """Load pipeline logs from file and update memory cache."""
    import os
    import json
    
    try:
        logs_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
        log_file = os.path.join(logs_dir, f'pipeline_{user_id}.json')
        
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                file_logs = json.load(f)
            
            # Convert to display format and update memory cache
            formatted_logs = [log.get('formatted', log.get('message', '')) for log in file_logs]
            pipeline_logs[user_id] = formatted_logs
            return formatted_logs
            
    except Exception as e:
        logger.warning(f"Failed to load pipeline logs from file: {e}")
    
    return pipeline_logs.get(user_id, [])

@app.route('/api/run-pipeline', methods=['POST'])
@security.rate_limit(max_requests=5, window_minutes=60, per_user=True)
@security.require_auth
@security.validate_input(PIPELINE_RUN_SCHEMA)
def run_pipeline():
    """Run the full end-to-end pipeline using background jobs."""
    try:
        user_id = request.json.get('user_id')
        options = request.json.get('options', {})
        
        if not user_id:
            return jsonify({'success': False, 'message': 'User ID is required'}), 400
        
        # Verify user exists
        user_prefs = db_manager.get_user_preferences(user_id)
        if not user_prefs:
            return jsonify({'success': False, 'message': f'User {user_id} not found'}), 404
        
        # Ensure background job manager is running
        if not BACKGROUND_JOBS_AVAILABLE:
            logger.error("Background jobs not available, cannot run pipeline")
            return jsonify({
                'success': False, 
                'message': 'Background job system not available. Please contact administrator.'
            }), 500
        
        # Check if job manager is running
        job_status = job_manager.get_queue_status()
        if not job_status.get('running', False):
            logger.warning("Job manager not running, attempting to start...")
            try:
                start_job_manager()
                add_pipeline_log(user_id, "Started background job manager", "info", "System Initialization")
            except Exception as start_error:
                logger.error(f"Failed to start job manager: {start_error}")
                return jsonify({
                    'success': False, 
                    'message': f'Failed to start background job system: {str(start_error)}'
                }), 500
        
        # Clear previous logs and initialize pipeline
        clear_pipeline_logs(user_id)
        add_pipeline_log(user_id, f"🚀 Starting pipeline for user {user_id}", "running", "Initializing pipeline")
        add_pipeline_log(user_id, f"Pipeline options: {options}", "info", "Configuration")
        
        # Prepare job data
        job_data = {
            'user_id': user_id,
            'max_articles': options.get('max_articles', 10),
            'enhanced': options.get('enhanced', False),
            'skip_ai': options.get('skip_ai', False),
            'no_collect': options.get('no_collect', False),
            'categories': options.get('categories', None)
        }
        
        # Determine priority based on options
        priority = JobPriority.HIGH if options.get('enhanced') else JobPriority.NORMAL
        
        submitted_jobs = {}
        
        # Submit collection job first
        if not options.get('no_collect'):
            try:
                collection_job_id = submit_background_job(
                    'rss_collection', 
                    {'user_id': user_id, 'max_articles': job_data['max_articles']},
                    priority
                )
                submitted_jobs['collection'] = collection_job_id
                add_pipeline_log(user_id, f"✅ RSS collection job submitted: {collection_job_id}", "info", "Job Submission")
                logger.info(f"Submitted RSS collection job {collection_job_id} for user {user_id}")
            except Exception as e:
                add_pipeline_log(user_id, f"❌ Failed to submit RSS collection job: {e}", "error", "Job Submission")
                logger.error(f"Failed to submit RSS collection job: {e}")
                return jsonify({'success': False, 'message': f'Failed to submit RSS collection job: {str(e)}'}), 500
        else:
            add_pipeline_log(user_id, "⏭️ Skipping RSS collection (no_collect=True)", "info", "Job Submission")
        
        # Submit AI processing job
        if not options.get('skip_ai'):
            try:
                ai_job_id = submit_background_job(
                    'ai_processing',
                    {'article_limit': 50},
                    priority
                )
                submitted_jobs['ai_processing'] = ai_job_id
                add_pipeline_log(user_id, f"✅ AI processing job submitted: {ai_job_id}", "info", "Job Submission")
                logger.info(f"Submitted AI processing job {ai_job_id}")
            except Exception as e:
                add_pipeline_log(user_id, f"❌ Failed to submit AI processing job: {e}", "error", "Job Submission")
                logger.error(f"Failed to submit AI processing job: {e}")
                return jsonify({'success': False, 'message': f'Failed to submit AI processing job: {str(e)}'}), 500
        else:
            add_pipeline_log(user_id, "⏭️ Skipping AI processing (skip_ai=True)", "info", "Job Submission")
        
        # Submit email delivery job (skip if dry_run mode)
        if not options.get('dry_run'):
            try:
                email_job_id = submit_background_job(
                    'email_delivery',
                    {'user_id': user_id, 'dry_run': False},
                    JobPriority.NORMAL
                )
                submitted_jobs['email_delivery'] = email_job_id
                add_pipeline_log(user_id, f"✅ Email delivery job submitted: {email_job_id}", "info", "Job Submission")
                logger.info(f"Submitted email delivery job {email_job_id} for user {user_id}")
            except Exception as e:
                add_pipeline_log(user_id, f"❌ Failed to submit email delivery job: {e}", "error", "Job Submission")
                logger.error(f"Failed to submit email delivery job: {e}")
                return jsonify({'success': False, 'message': f'Failed to submit email delivery job: {str(e)}'}), 500
        else:
            add_pipeline_log(user_id, "⏭️ Skipping email delivery (dry_run=True)", "info", "Job Submission")
            logger.info(f"Skipping email delivery (dry_run mode) for user {user_id}")
        
        # Store job IDs for tracking
        pipeline_execution_status[user_id] = {
            'status': 'running',
            'step': 'Pipeline jobs submitted successfully',
            'collection_job_id': submitted_jobs.get('collection'),
            'ai_job_id': submitted_jobs.get('ai_processing'),
            'email_job_id': submitted_jobs.get('email_delivery'),
            'started_at': datetime.now().isoformat()
        }
        
        add_pipeline_log(user_id, f"🎯 All jobs submitted successfully: {len(submitted_jobs)} jobs", "info", "Pipeline Started")
        
        return jsonify({
            'success': True,
            'message': f'Pipeline jobs submitted for user {user_id}',
            'jobs': submitted_jobs
        })
        
    except Exception as e:
        logger.error(f"Error running pipeline: {e}", exc_info=True)
        if 'user_id' in locals():
            add_pipeline_log(user_id, f"💥 Pipeline failed to start: {e}", "error", "System Error")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/pipeline-status/<user_id>')
def get_pipeline_status(user_id: str):
    """Get pipeline execution status with real-time updates."""
    status_info = pipeline_execution_status.get(user_id, {'status': 'unknown', 'step': 'No recent execution found'})
    
    response = {
        'status': status_info.get('status', 'unknown'),
        'current_step': status_info.get('step', 'Unknown'),
        'success': None,
        'jobs': {}
    }
    
    # Get job statuses if available
    if 'collection_job_id' in status_info and status_info['collection_job_id']:
        job_status = get_job_status(status_info['collection_job_id'])
        if job_status:
            response['jobs']['collection'] = job_status
    
    if 'ai_job_id' in status_info and status_info['ai_job_id']:
        job_status = get_job_status(status_info['ai_job_id'])
        if job_status:
            response['jobs']['ai_processing'] = job_status
    
    if 'email_job_id' in status_info and status_info['email_job_id']:
        job_status = get_job_status(status_info['email_job_id'])
        if job_status:
            response['jobs']['email_delivery'] = job_status
    elif 'email_job_id' in status_info and status_info['email_job_id'] is None:
        # Email job was skipped (dry_run mode)
        response['jobs']['email_delivery'] = {
            'status': 'skipped',
            'result': {'success': True, 'message': 'Email delivery skipped (dry_run mode)'}
        }
    
    # Determine overall status based on job statuses
    if response['jobs']:
        all_completed = all(
            job.get('status') in ['completed', 'failed', 'skipped'] 
            for job in response['jobs'].values()
        )
        all_successful = all(
            job.get('status') in ['completed', 'skipped'] 
            for job in response['jobs'].values()
        )
        
        if all_completed:
            response['status'] = 'completed' if all_successful else 'failed'
            response['success'] = all_successful
            if all_successful:
                response['current_step'] = 'All pipeline jobs completed successfully'
                # Update the stored status to reflect completion
                if status_info.get('status') != 'completed':
                    pipeline_execution_status[user_id] = {
                        **status_info,
                        'status': 'completed',
                        'step': 'All pipeline jobs completed successfully',
                        'completed_at': datetime.now().isoformat()
                    }
                    add_pipeline_log(user_id, "🎉 Pipeline completed successfully", "info", "Pipeline Completed")
            else:
                failed_jobs = [
                    name for name, job in response['jobs'].items() 
                    if job.get('status') == 'failed'
                ]
                response['current_step'] = f'Pipeline failed - jobs failed: {", ".join(failed_jobs)}'
                # Update the stored status to reflect failure
                if status_info.get('status') != 'failed':
                    pipeline_execution_status[user_id] = {
                        **status_info,
                        'status': 'failed',
                        'step': f'Pipeline failed - jobs failed: {", ".join(failed_jobs)}',
                        'failed_at': datetime.now().isoformat()
                    }
                    add_pipeline_log(user_id, f"❌ Pipeline failed: {', '.join(failed_jobs)}", "error", "Pipeline Failed")
    
    return jsonify(response)

@app.route('/api/pipeline-logs/<user_id>')
def get_pipeline_logs(user_id: str):
    """Get real-time pipeline logs."""
    # Handle test endpoint
    if user_id == 'test':
        return jsonify({
            'logs': [
                '[' + datetime.now().strftime('%H:%M:%S') + '] 🧪 API test endpoint working',
                '[' + datetime.now().strftime('%H:%M:%S') + '] ✅ Pipeline logs API is functional',
                '[' + datetime.now().strftime('%H:%M:%S') + '] 📡 Real-time monitoring ready'
            ],
            'status': 'completed',
            'current_step': '✅ API test successful',
            'timestamp': datetime.now().isoformat()
        })
    
    # Try to get logs from memory first, then from file
    logs = pipeline_logs.get(user_id, [])
    if not logs:
        logs = load_pipeline_logs_from_file(user_id)
    
    status = pipeline_execution_status.get(user_id, {'status': 'unknown', 'step': 'No logs available'})
    
    # If no logs yet but user exists, provide initial message
    if not logs and user_id:
        user_prefs = db_manager.get_user_preferences(user_id)
        if user_prefs:
            logs = [f'[{datetime.now().strftime("%H:%M:%S")}] 👤 User {user_id} found, ready to start pipeline']
            status = {'status': 'ready', 'step': 'Ready to start pipeline'}
    
    return jsonify({
        'logs': logs,
        'status': status['status'],
        'current_step': status['step'],
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/send-email', methods=['POST'])
@security.rate_limit(max_requests=5, window_minutes=60, per_user=True)
@security.require_auth
def send_email_api():
    """Send email using background job system or direct delivery as fallback."""
    try:
        user_id = request.json.get('user_id')
        max_articles = request.json.get('max_articles', 10)
        
        if not user_id:
            return jsonify({'success': False, 'message': 'User ID is required'}), 400
        
        # Check if user exists
        user_prefs = db_manager.get_user_preferences(user_id)
        if not user_prefs:
            return jsonify({'success': False, 'message': f'User {user_id} not found'}), 404
        
        # Try background job system first
        if BACKGROUND_JOBS_AVAILABLE:
            # Ensure job manager is running
            job_status = job_manager.get_queue_status()
            if not job_status.get('running', False):
                logger.warning("Job manager not running, attempting to start...")
                try:
                    start_job_manager()
                    logger.info("Started background job manager for email delivery")
                except Exception as start_error:
                    logger.error(f"Failed to start job manager: {start_error}")
                    return jsonify({
                        'success': False, 
                        'message': f'Failed to start background job system: {str(start_error)}'
                    }), 500
            
            # Submit email delivery job using modern background job system
            try:
                email_job_id = submit_background_job(
                    'email_delivery',
                    {'user_id': user_id, 'dry_run': False},
                    JobPriority.NORMAL
                )
                
                logger.info(f"Submitted email delivery job {email_job_id} for user {user_id}")
                
                return jsonify({
                    'success': True,
                    'message': f'Email delivery job submitted for user {user_id}',
                    'job_id': email_job_id
                })
            except Exception as job_error:
                logger.error(f"Failed to submit email delivery job: {job_error}")
                return jsonify({
                    'success': False, 
                    'message': f'Failed to submit email job: {str(job_error)}'
                }), 500
        else:
            # Fallback to direct email delivery
            logger.info(f"Background jobs not available, sending email directly for user {user_id}")
            
            try:
                # Get personalized articles and create digest
                articles = digest_generator.get_personalized_articles(user_id, max_articles)
                if not articles:
                    return jsonify({
                        'success': False, 
                        'message': f'No articles found for user {user_id} with selected categories'
                    }), 404
                
                # Create digest data structure for email
                digest_data = {
                    'categories': digest_generator._deduplicate_articles_by_category(
                        articles, user_prefs['selected_categories']
                    ),
                    'user_id': user_id,
                    'generated_at': datetime.now().isoformat()
                }
                
                # Send email directly using email manager
                success, message = email_manager.deliver_digest_email(user_id, digest_data)
                
                return jsonify({
                    'success': success,
                    'message': message or f"Email delivery {'completed' if success else 'failed'}"
                })
            except Exception as direct_error:
                logger.error(f"Direct email delivery failed: {direct_error}")
                return jsonify({
                    'success': False, 
                    'message': f'Direct email delivery failed: {str(direct_error)}'
                }), 500
        
    except Exception as e:
        logger.error(f"Error in send_email_api: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'Email API error: {str(e)}'}), 500


@app.route('/api/delete-user/<user_id>', methods=['DELETE'])
@security.rate_limit(max_requests=10, window_minutes=60)
def delete_user_api(user_id: str):
    """Delete user using database manager directly with fallback to main.py command."""
    try:
        # First check if user exists
        user_prefs = db_manager.get_user_preferences(user_id)
        if not user_prefs:
            return jsonify({'success': False, 'message': f'User {user_id} not found'}), 404
        
        # Try direct database deletion first
        try:
            success = db_manager.delete_user_preferences(user_id)
            if success:
                logger.info(f"User {user_id} deleted successfully via database manager")
                return jsonify({
                    'success': True,
                    'message': f'User {user_id} deleted successfully'
                })
            else:
                logger.warning(f"Database manager failed to delete user {user_id}, trying subprocess fallback")
        except Exception as db_error:
            logger.warning(f"Database deletion failed for user {user_id}: {db_error}, trying subprocess fallback")
        
        # Fallback to subprocess call to main.py
        try:
            main_py_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'main.py')
            
            # Check if main.py exists
            if not os.path.exists(main_py_path):
                logger.error(f"main.py not found at {main_py_path}")
                return jsonify({
                    'success': False, 
                    'message': f'Cannot delete user: main.py not found and database deletion failed'
                }), 500
            
            cmd = [sys.executable, main_py_path, 'user', 'remove', user_id, '--confirm']
            logger.info(f"Running command: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, 
                                  cwd=os.path.dirname(main_py_path))
            
            success = result.returncode == 0
            message = result.stdout if success else result.stderr
            
            # Ensure message is not empty
            if not message:
                message = f"Command {'completed successfully' if success else 'failed'}"
            
            logger.info(f"Subprocess result for user {user_id} deletion: success={success}, message={message}")
            
            return jsonify({
                'success': success,
                'message': message.strip()
            })
            
        except subprocess.TimeoutExpired:
            return jsonify({
                'success': False, 
                'message': 'User deletion timed out'
            }), 500
        except Exception as subprocess_error:
            logger.error(f"Subprocess deletion failed for user {user_id}: {subprocess_error}")
            return jsonify({
                'success': False, 
                'message': f'User deletion failed: {str(subprocess_error)}'
            }), 500
        
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        return jsonify({'success': False, 'message': f'Deletion error: {str(e)}'}), 500

@app.route('/articles-dashboard')
def articles_dashboard():
    """Articles dashboard showing all articles with detailed information."""
    try:
        # Get all articles with full details
        query = '''
        SELECT id, title, author, publication_date, source_link, 
               original_summary, rss_category, ai_categories, ai_summary, 
               trending_flag, date_collected,
               image_url, image_source, image_cached_path, image_size, 
               image_width, image_height
        FROM articles 
        ORDER BY date_collected DESC
        '''
        
        # Use proper database connection method
        import sqlite3
        with sqlite3.connect(db_manager.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            columns = [description[0] for description in cursor.description]
            articles = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        # Parse ai_categories from JSON strings
        for article in articles:
            if article['ai_categories']:
                try:
                    import json
                    article['ai_categories'] = json.loads(article['ai_categories'])
                except:
                    article['ai_categories'] = []
            else:
                article['ai_categories'] = []
        
        # Group articles by category for section view
        from collections import defaultdict
        by_category = defaultdict(list)
        
        for article in articles:
            categories = article.get('ai_categories', [])
            if categories:
                # Add to first category (main category)
                by_category[categories[0]].append(article)
            else:
                by_category['Uncategorized'].append(article)
        
        return render_template('articles_dashboard.html', 
                             articles=articles, 
                             by_category=dict(by_category))
                             
    except Exception as e:
        logger.error(f"Error loading articles dashboard: {e}")
        return render_template('error.html', error=f"Failed to load articles: {str(e)}"), 500

@app.route('/user-management')
def user_management():
    """User management dashboard."""
    try:
        # Get all users
        all_users = db_manager.get_all_users()
        users = []
        
        # Handle both dict and list response types
        if isinstance(all_users, list):
            for user_prefs in all_users:
                users.append({
                    'user_id': user_prefs['user_id'],
                    'email': user_prefs.get('email', ''),
                    'categories': user_prefs.get('selected_categories', []),
                    'last_digest': user_prefs.get('last_digest_date', 'Never')
                })
        elif hasattr(all_users, 'items'):
            # Handle dict-like object
            for user_id, user_prefs in all_users.items():
                users.append({
                    'user_id': user_id,
                    'email': user_prefs.get('email', ''),
                    'categories': user_prefs.get('selected_categories', []),
                    'last_digest': user_prefs.get('last_digest_date', 'Never')
                })
        else:
            logger.warning(f"Unexpected all_users type: {type(all_users)}")
            users = []
        
        return render_template('user_management.html', users=users, categories=AI_CATEGORIES)
    except Exception as e:
        logger.error(f"Error loading user management: {e}")
        return render_template('error.html', error="Failed to load user management"), 500

@app.route('/edit-user/<user_id>', methods=['GET', 'POST'])
@security.rate_limit(max_requests=20, window_minutes=60)
def edit_user(user_id: str):
    """Edit user preferences."""
    if request.method == 'POST':
        try:
            # Get form data
            email = request.form.get('email', '').strip()
            selected_categories = request.form.getlist('categories')
            articles_per_digest = request.form.get('articles_per_digest', '10')
            digest_frequency = request.form.get('digest_frequency', 'daily')
            
            # Validate input
            if not email:
                flash('Email is required', 'error')
                return redirect(url_for('edit_user', user_id=user_id))
            
            if not selected_categories:
                flash('At least one category must be selected', 'error')
                return redirect(url_for('edit_user', user_id=user_id))
            
            # Validate articles per digest
            try:
                articles_count = int(articles_per_digest)
                if articles_count < 5 or articles_count > 50:
                    flash('Articles per digest must be between 5 and 50', 'error')
                    return redirect(url_for('edit_user', user_id=user_id))
            except ValueError:
                flash('Articles per digest must be a valid number', 'error')
                return redirect(url_for('edit_user', user_id=user_id))
            
            # Validate email format
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                flash('Please enter a valid email address', 'error')
                return redirect(url_for('edit_user', user_id=user_id))
            
            # Validate categories
            invalid_categories = [cat for cat in selected_categories if cat not in AI_CATEGORIES]
            if invalid_categories:
                flash(f'Invalid categories: {", ".join(invalid_categories)}', 'error')
                return redirect(url_for('edit_user', user_id=user_id))
            
            # Get existing user preferences
            existing_prefs = db_manager.get_user_preferences(user_id)
            if not existing_prefs:
                flash(f'User {user_id} not found', 'error')
                return redirect(url_for('user_management'))
            
            # Update user preferences
            updated_prefs = {
                'user_id': user_id,
                'email': email,
                'selected_categories': selected_categories,
                'digest_frequency': digest_frequency,
                'articles_per_digest': articles_count,
                'preferred_output_format': existing_prefs.get('preferred_output_format', 'html'),
                'feedback_history': existing_prefs.get('feedback_history', {})
            }
            
            # Save to database
            logger.info(f"Updating user: {user_id} with data: {updated_prefs}")
            
            try:
                success = db_manager.insert_or_update_user_preferences(updated_prefs)
                logger.info(f"Database update result: {success}")
                
                # Verify the update
                verification = db_manager.get_user_preferences(user_id)
                logger.info(f"User verification after update: {verification}")
                
                if success and verification:
                    flash(f'User "{user_id}" updated successfully!', 'success')
                    logger.info(f"User {user_id} updated successfully")
                    return redirect(url_for('user_management'))
                else:
                    logger.error(f"Failed to update user {user_id}. Success: {success}, Verification: {verification}")
                    flash('Failed to update user. Database update failed.', 'error')
                    return redirect(url_for('edit_user', user_id=user_id))
            except Exception as db_error:
                logger.error(f"Database error while updating user {user_id}: {db_error}", exc_info=True)
                flash(f'Database error: {str(db_error)}', 'error')
                return redirect(url_for('edit_user', user_id=user_id))
                
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}", exc_info=True)
            flash(f'An error occurred while updating the user: {str(e)}', 'error')
            return redirect(url_for('edit_user', user_id=user_id))
    
    # GET request - show form
    try:
        user_prefs = db_manager.get_user_preferences(user_id)
        if not user_prefs:
            flash(f'User {user_id} not found', 'error')
            return redirect(url_for('user_management'))
        
        # Convert categories to dict format expected by template
        categories_dict = {}
        for category in AI_CATEGORIES:
            categories_dict[category] = {
                'icon': get_category_icon(category)
            }
        
        return render_template('edit_user.html', user=user_prefs, categories=categories_dict, user_id=user_id)
    except Exception as e:
        logger.error(f"Error loading edit user page for {user_id}: {e}")
        flash(f'Error loading user data: {str(e)}', 'error')
        return redirect(url_for('user_management'))

@app.route('/api/debug-pipeline/<user_id>')
@security.admin_required
def debug_pipeline(user_id: str):
    """Debug endpoint to test pipeline command manually."""
    try:
        main_py_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'main.py')
        cmd = [sys.executable, main_py_path, 'run', '--user', user_id, '--dry-run']
        
        logger.info(f"Debug: Testing command: {' '.join(cmd)}")
        logger.info(f"Debug: Working directory: {os.path.dirname(main_py_path)}")
        logger.info(f"Debug: main.py exists: {os.path.exists(main_py_path)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=os.path.dirname(main_py_path))
        
        return jsonify({
            'command': ' '.join(cmd),
            'working_dir': os.path.dirname(main_py_path),
            'main_py_exists': os.path.exists(main_py_path),
            'return_code': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr
        })
        
    except Exception as e:
        logger.error(f"Debug pipeline error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/test-logs')
@security.admin_required
def test_logs():
    """Test page for real-time logging functionality."""
    # Disable in production
    if os.getenv('FLASK_ENV') == 'production':
        return jsonify({'error': 'Debug endpoints disabled in production'}), 404
    
    test_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'test_logs_only.html')
    try:
        with open(test_file_path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return "Test file not found", 404

@app.route('/test-user-functions')
@security.admin_required
def test_user_functions():
    """Test page for user management functions."""
    # Disable in production
    if os.getenv('FLASK_ENV') == 'production':
        return jsonify({'error': 'Debug endpoints disabled in production'}), 404
    
    test_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'test_user_functions.html')
    try:
        with open(test_file_path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return "Test file not found", 404

@app.route('/debug-user-management')
@security.admin_required
def debug_user_management():
    """Debug page for user management functionality."""
    # Disable in production
    if os.getenv('FLASK_ENV') == 'production':
        return jsonify({'error': 'Debug endpoints disabled in production'}), 404
    
    try:
        return render_template('debug_user_management.html')
    except Exception as e:
        logger.error(f"Error loading debug user management: {e}")
        return render_template('error.html', error="Failed to load debug page"), 500

@app.route('/api/stats')
def api_stats():
    """API endpoint for application statistics."""
    try:
        # Get article statistics using count method to avoid loading all articles
        total_articles = db_manager.get_article_count()
        
        # Get user statistics
        all_users = db_manager.get_all_users()
        total_users = len(all_users)
        
        # Get recent activity
        recent_deliveries = db_manager.get_recent_email_deliveries(limit=10)
        
        # Get job queue statistics
        queue_status = job_manager.get_queue_status()
        
        return jsonify({
            'total_articles': total_articles,
            'total_users': total_users,
            'recent_deliveries': len(recent_deliveries),
            'job_queue': queue_status,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/jobs/<job_id>')
@security.require_auth
def get_job_details(job_id: str):
    """Get detailed job information."""
    job_status = get_job_status(job_id)
    if not job_status:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify(job_status)

@app.route('/api/test-job-status/<job_id>')
def test_job_status(job_id: str):
    """Test endpoint for job status without authentication (for debugging only)."""
    # Disable in production
    if os.getenv('FLASK_ENV') == 'production':
        return jsonify({'error': 'Test endpoints disabled in production'}), 404
    
    job_status = get_job_status(job_id)
    if not job_status:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify(job_status)

@app.route('/api/jobs/<job_id>/cancel', methods=['POST'])
@security.require_auth
def cancel_job(job_id: str):
    """Cancel a running or pending job."""
    success = job_manager.cancel_job(job_id)
    if success:
        return jsonify({'success': True, 'message': f'Job {job_id} cancelled'})
    else:
        return jsonify({'success': False, 'message': 'Job could not be cancelled'}), 400

@app.route('/api/jobs/queue')
@security.admin_required
def get_job_queue():
    """Get job queue status (admin only)."""
    return jsonify(job_manager.get_queue_status())

# AI Reprocessing API
@app.route('/api/reprocess-articles', methods=['POST'])
def reprocess_articles():
    """Reprocess selected articles with AI."""
    try:
        data = request.get_json()
        article_ids = data.get('article_ids', [])
        reprocess_categories = data.get('reprocess_categories', True)
        reprocess_summaries = data.get('reprocess_summaries', True)
        reprocess_trending = data.get('reprocess_trending', False)
        
        if not article_ids:
            return jsonify({'success': False, 'message': 'No articles selected'}), 400
        
        if not any([reprocess_categories, reprocess_summaries, reprocess_trending]):
            return jsonify({'success': False, 'message': 'No reprocessing options selected'}), 400
        
        logger.info(f"Starting AI reprocessing for {len(article_ids)} articles")
        
        # Import and initialize AI processor
        ai_processor = None
        import_error_msg = None
        
        try:
            # Try relative imports first
            from .enhanced_ai_processor import EnhancedAIProcessor
            ai_processor = EnhancedAIProcessor()
            logger.info("Successfully imported EnhancedAIProcessor (relative)")
        except ImportError as e:
            import_error_msg = f"Relative enhanced: {e}"
            try:
                # Try absolute imports as fallback
                import sys
                import os
                sys.path.insert(0, os.path.dirname(__file__))
                from enhanced_ai_processor import EnhancedAIProcessor
                ai_processor = EnhancedAIProcessor()
                logger.info("Successfully imported EnhancedAIProcessor (absolute)")
            except ImportError as e2:
                import_error_msg += f", Enhanced absolute: {e2}"
                logger.error(f"All AI processor imports failed: {import_error_msg}")
                ai_processor = None
        except Exception as e:
            # Catch initialization errors
            logger.error(f"AI processor initialization failed: {e}")
            import_error_msg = f"Initialization error: {e}"
        
        if ai_processor is None:
            return jsonify({
                'success': False, 
                'message': f'AI processor not available. Import errors: {import_error_msg}'
            }), 500
        
        # Get database manager
        db = DatabaseManager()
        
        # Fetch articles to reprocess
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()
            
            # Build query to get selected articles
            placeholders = ','.join(['?' for _ in article_ids])
            cursor.execute(f'''
                SELECT id, title, original_summary, ai_categories, ai_summary, trending_flag
                FROM articles 
                WHERE id IN ({placeholders})
            ''', article_ids)
            
            articles = []
            for row in cursor.fetchall():
                article = {
                    'id': row[0],
                    'title': row[1],
                    'original_summary': row[2],
                    'ai_categories': row[3],
                    'ai_summary': row[4],
                    'trending_flag': row[5]
                }
                articles.append(article)
        
        if not articles:
            return jsonify({'success': False, 'message': 'No articles found'}), 404
        
        # Process articles in batches
        processed_count = 0
        batch_size = 10  # Process in smaller batches to avoid timeouts
        
        for i in range(0, len(articles), batch_size):
            batch = articles[i:i + batch_size]
            
            for article in batch:
                try:
                    updates = {}
                    
                    # Reprocess categories if requested
                    if reprocess_categories:
                        try:
                            # Try enhanced method first
                            if hasattr(ai_processor, 'classify_article_enhanced'):
                                categories = ai_processor.classify_article_enhanced(
                                    article['title'], 
                                    article['original_summary'] or ''
                                )
                            elif hasattr(ai_processor, 'classify_article'):
                                categories = ai_processor.classify_article(
                                    article['title'], 
                                    article['original_summary'] or ''
                                )
                            else:
                                logger.error("No classify method available on AI processor")
                                categories = None
                            
                            # Always update categories field when reprocessing is requested
                            # This ensures old categories are cleared even if AI fails
                            if categories:
                                updates['ai_categories'] = json.dumps(categories)
                                logger.info(f"Updated categories for article {article['id']}: {categories}")
                            else:
                                # Clear old categories if AI processing failed or returned empty
                                updates['ai_categories'] = json.dumps([])
                                logger.warning(f"Cleared categories for article {article['id']} - AI processing failed or returned empty")
                                
                        except Exception as e:
                            logger.error(f"Error processing categories for article {article['id']}: {e}")
                            # Clear old categories on error
                            updates['ai_categories'] = json.dumps([])
                    
                    # Reprocess summaries if requested
                    if reprocess_summaries:
                        try:
                            logger.info(f"DEBUG: Starting summary processing for article {article['id']}")
                            logger.info(f"DEBUG: Article title: {article['title'][:100]}...")
                            logger.info(f"DEBUG: Original summary length: {len(article['original_summary'] or '')}")
                            
                            summary = None
                            # Try enhanced method first
                            if hasattr(ai_processor, 'generate_summary_enhanced'):
                                logger.info(f"DEBUG: Using generate_summary_enhanced method")
                                summary = ai_processor.generate_summary_enhanced(
                                    article['title'],
                                    article['original_summary'] or ''
                                )
                                logger.info(f"DEBUG: Enhanced method returned: {type(summary)}, value: {summary}")
                            elif hasattr(ai_processor, 'generate_summary'):
                                logger.info(f"DEBUG: Using generate_summary method")
                                summary = ai_processor.generate_summary(
                                    article['title'],
                                    article['original_summary'] or ''
                                )
                                logger.info(f"DEBUG: Basic method returned: {type(summary)}, value: {summary}")
                            else:
                                logger.error("No summary method available on AI processor")
                                summary = None
                            
                            # Always update summary field when reprocessing is requested
                            # This ensures old summaries are cleared even if AI fails
                            if summary and summary.strip():
                                updates['ai_summary'] = summary.strip()
                                logger.info(f"Updated AI summary for article {article['id']}: {len(summary)} chars - '{summary[:50]}...'")
                            else:
                                # Clear old summary if AI processing failed or returned empty
                                updates['ai_summary'] = ''
                                logger.warning(f"Cleared AI summary for article {article['id']} - AI processing failed or returned empty (summary was: {repr(summary)})")
                                
                        except Exception as e:
                            logger.error(f"Error processing summary for article {article['id']}: {e}", exc_info=True)
                            # Clear old summary on error
                            updates['ai_summary'] = ''
                    
                    # Reprocess trending status if requested
                    if reprocess_trending:
                        try:
                            # For trending detection, both processors work differently
                            # and neither has a simple per-article trending method
                            # For now, we'll set trending based on simple keywords
                            title_lower = article['title'].lower()
                            summary_lower = (article['original_summary'] or '').lower()
                            
                            # Simple trending detection based on keywords
                            trending_keywords = ['breaking', 'urgent', 'major', 'significant', 'unprecedented', 
                                               'record', 'first', 'new', 'latest', 'developing', 'exclusive']
                            
                            is_trending = any(keyword in title_lower or keyword in summary_lower 
                                            for keyword in trending_keywords)
                            
                            updates['trending_flag'] = is_trending
                            logger.info(f"Set trending to {is_trending} for article {article['id']} based on keywords")
                            
                        except Exception as e:
                            logger.error(f"Error processing trending for article {article['id']}: {e}")
                            updates['trending_flag'] = False
                    
                    # Update database if there are changes
                    if updates:
                        logger.info(f"DEBUG: Updating article {article['id']} with: {updates}")
                        
                        with sqlite3.connect(db.db_path) as conn:
                            cursor = conn.cursor()
                            
                            # Build update query
                            set_clauses = []
                            values = []
                            for field, value in updates.items():
                                set_clauses.append(f"{field} = ?")
                                values.append(value)
                            
                            if set_clauses:
                                values.append(article['id'])
                                query = f'''
                                    UPDATE articles 
                                    SET {', '.join(set_clauses)}, date_updated = CURRENT_TIMESTAMP
                                    WHERE id = ?
                                '''
                                logger.info(f"DEBUG: Executing SQL: {query}")
                                logger.info(f"DEBUG: With values: {values}")
                                
                                cursor.execute(query, values)
                                rows_affected = cursor.rowcount
                                logger.info(f"DEBUG: Database update affected {rows_affected} rows")
                                
                                if rows_affected > 0:
                                    processed_count += 1
                                    logger.info(f"DEBUG: Successfully updated article {article['id']}")
                                else:
                                    logger.warning(f"DEBUG: No rows affected for article {article['id']}")
                    else:
                        logger.info(f"DEBUG: No updates needed for article {article['id']}")
                
                except Exception as e:
                    logger.error(f"Error reprocessing article {article['id']}: {e}")
                    continue
        
        message = f"Successfully reprocessed {processed_count} of {len(articles)} articles"
        if processed_count > 0:
            logger.info(message)
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'message': 'No articles were successfully reprocessed'}), 500
        
    except Exception as e:
        logger.error(f"Error in AI reprocessing: {e}")
        return jsonify({'success': False, 'message': f'Reprocessing failed: {str(e)}'}), 500


@app.route('/api/test-ai-processor', methods=['GET'])
def test_ai_processor():
    """Test endpoint to check AI processor availability."""
    try:
        # Test AI processor import and initialization
        ai_processor = None
        processor_info = {}
        
        try:
            from .enhanced_ai_processor import EnhancedAIProcessor
            ai_processor = EnhancedAIProcessor()
            processor_info['type'] = 'EnhancedAIProcessor'
            processor_info['methods'] = [method for method in dir(ai_processor) if not method.startswith('_')]
        except ImportError as e:
            processor_info['enhanced_relative_error'] = str(e)
            try:
                from enhanced_ai_processor import EnhancedAIProcessor
                ai_processor = EnhancedAIProcessor()
                processor_info['type'] = 'EnhancedAIProcessor'
                processor_info['methods'] = [method for method in dir(ai_processor) if not method.startswith('_')]
            except ImportError as e2:
                processor_info['enhanced_absolute_error'] = str(e2)
                ai_processor = None
        except Exception as e:
            processor_info['init_error'] = str(e)
        
        if ai_processor:
            # Test a simple method call
            try:
                if hasattr(ai_processor, 'classify_article_enhanced'):
                    test_result = ai_processor.classify_article_enhanced("Test Title", "Test summary")
                    processor_info['test_classify'] = 'success'
                elif hasattr(ai_processor, 'classify_article'):
                    test_result = ai_processor.classify_article("Test Title", "Test summary")
                    processor_info['test_classify'] = 'success'
                else:
                    processor_info['test_classify'] = 'no_classify_method'
            except Exception as e:
                processor_info['test_classify'] = f'error: {e}'
            
            return jsonify({
                'success': True, 
                'message': 'AI processor is available', 
                'processor_info': processor_info
            })
        else:
            return jsonify({
                'success': False, 
                'message': 'AI processor not available', 
                'processor_info': processor_info
            }), 500
            
    except Exception as e:
        logger.error(f"Error testing AI processor: {e}")
        return jsonify({'success': False, 'message': f'Test failed: {str(e)}'}), 500


@app.route('/api/debug-logs', methods=['GET'])
def debug_logs():
    """Get recent log entries for debugging."""
    try:
        lines = int(request.args.get('lines', 50))
        search = request.args.get('search', '')
        
        log_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'web_interface.log')
        
        if not os.path.exists(log_file):
            return jsonify({'success': False, 'message': 'Log file not found'})
        
        with open(log_file, 'r') as f:
            all_lines = f.readlines()
        
        # Get last N lines
        recent_lines = all_lines[-lines:]
        
        # Filter by search term if provided
        if search:
            recent_lines = [line for line in recent_lines if search.lower() in line.lower()]
        
        return jsonify({
            'success': True,
            'log_file': log_file,
            'total_lines': len(all_lines),
            'returned_lines': len(recent_lines),
            'lines': [line.strip() for line in recent_lines]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error reading logs: {str(e)}'}), 500


@app.route('/api/test-pipeline', methods=['POST'])
def test_pipeline():
    """Test endpoint for pipeline without authentication (for debugging only)."""
    # Disable in production
    if os.getenv('FLASK_ENV') == 'production':
        return jsonify({'error': 'Test endpoints disabled in production'}), 404
    
    try:
        user_id = request.json.get('user_id', 'TestCLI')
        mode = request.json.get('mode', 'send')
        
        # Check if user exists
        user_prefs = db_manager.get_user_preferences(user_id)
        if not user_prefs:
            return jsonify({'success': False, 'message': f'User {user_id} not found'}), 404
        
        logger.info(f"Testing pipeline mode '{mode}' for user {user_id}")
        
        if mode == 'send':
            # Test email-only pipeline
            try:
                # Ensure job manager is running
                if not job_manager.get_queue_status().get('running', False):
                    start_job_manager()
                
                email_job_id = submit_background_job(
                    'email_delivery',
                    {'user_id': user_id, 'dry_run': False},
                    JobPriority.NORMAL
                )
                
                return jsonify({
                    'success': True,
                    'message': f'Test email job submitted: {email_job_id}',
                    'job_id': email_job_id
                })
            except Exception as e:
                return jsonify({'success': False, 'message': f'Email test failed: {str(e)}'}), 500
                
        elif mode == 'full':
            # Test full pipeline
            try:
                # Ensure job manager is running
                if not job_manager.get_queue_status().get('running', False):
                    start_job_manager()
                
                # Submit collection job
                collection_job_id = submit_background_job(
                    'rss_collection',
                    {'user_id': user_id, 'max_articles': 5},
                    JobPriority.NORMAL
                )
                
                # Submit email job
                email_job_id = submit_background_job(
                    'email_delivery',
                    {'user_id': user_id, 'dry_run': False},
                    JobPriority.NORMAL
                )
                
                return jsonify({
                    'success': True,
                    'message': f'Test full pipeline submitted',
                    'jobs': {
                        'collection': collection_job_id,
                        'email': email_job_id
                    }
                })
            except Exception as e:
                return jsonify({'success': False, 'message': f'Full pipeline test failed: {str(e)}'}), 500
        
        else:
            return jsonify({'success': False, 'message': f'Unknown test mode: {mode}'}), 400
        
    except Exception as e:
        logger.error(f"Test pipeline error: {e}")
        return jsonify({'success': False, 'message': f'Test failed: {str(e)}'}), 500

@app.route('/api/debug-llm-router', methods=['GET'])
def debug_llm_router():
    """Debug LLM Router status and configuration."""
    try:
        # Test LLM Router import and initialization
        debug_info = {}
        
        try:
            from .enhanced_ai_processor import EnhancedAIProcessor
            processor = EnhancedAIProcessor()
            debug_info['processor_type'] = 'EnhancedAIProcessor'
            debug_info['using_llm_router'] = getattr(processor, 'using_llm_router', 'Unknown')
            
            # Get AI manager type
            if hasattr(processor, 'ai_manager'):
                debug_info['ai_manager_type'] = type(processor.ai_manager).__name__
                
                # If using LLM Router, get more details
                if hasattr(processor.ai_manager, 'providers'):
                    debug_info['providers'] = [p.name for p in processor.ai_manager.providers] if hasattr(processor.ai_manager.providers[0], 'name') else len(processor.ai_manager.providers)
                    debug_info['current_provider'] = getattr(processor.ai_manager, 'current_provider', 'Unknown')
                
                # Test a simple query
                try:
                    test_result = processor._query_ai('What is 2+2?', 'test')
                    debug_info['test_query'] = f'Success: {test_result[:50]}...'
                except Exception as e:
                    debug_info['test_query'] = f'Failed: {str(e)}'
            
        except Exception as e:
            debug_info['processor_error'] = str(e)
        
        # Test direct LLM Router
        try:
            from .llm_router import LLMRouter
            router = LLMRouter('ai_config.yaml')
            debug_info['direct_llm_router'] = 'Success'
            test_result = router.query('What is 2+2?')
            debug_info['direct_test'] = f'Success: {test_result[:50]}...'
        except Exception as e:
            debug_info['direct_llm_router'] = f'Failed: {str(e)}'
        
        return jsonify({
            'success': True,
            'debug_info': debug_info
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Debug failed: {str(e)}'}), 500


# RSS Feed Management Routes
@app.route('/rss-management')
def rss_management():
    """RSS feed management page."""
    try:
        db = DatabaseManager()
        
        # Get all feeds grouped by category
        all_feeds = db.get_all_feeds()
        
        # Group feeds by category
        feeds_by_category = {}
        for feed in all_feeds:
            category = feed['category']
            if category not in feeds_by_category:
                feeds_by_category[category] = []
            feeds_by_category[category].append(feed)
        
        # Ensure all categories are represented
        for category in AI_CATEGORIES:
            if category not in feeds_by_category:
                feeds_by_category[category] = []
        
        # Category icons mapping
        category_icons = {
            'Science & Discovery': '🔬',
            'Technology & Gadgets': '💻',
            'Health & Wellness': '🏥',
            'Business & Finance': '💼',
            'Global Affairs': '🌍',
            'Environment & Climate': '🌱',
            'Good Vibes (Positive News)': '😊',
            'Pop Culture & Lifestyle': '🎭',
            'For Young Minds (Youth-Focused)': '🎓',
            'DIY, Skills & How-To': '🔧'
        }
        
        return render_template('rss_management.html', 
                             feeds_by_category=feeds_by_category,
                             category_icons=category_icons)
    except Exception as e:
        logger.error(f"Error loading RSS management page: {e}")
        return render_template('error.html', error="Failed to load RSS management page"), 500

@app.route('/add-rss-feed', methods=['POST'])
def add_rss_feed():
    """Add a new RSS feed."""
    try:
        category = request.form.get('category')
        feed_url = request.form.get('feed_url')
        feed_title = request.form.get('feed_title')
        
        if not category or not feed_url:
            flash('Category and Feed URL are required', 'error')
            return redirect(url_for('rss_management'))
        
        db = DatabaseManager()
        success = db.add_rss_feed(category, feed_url, feed_title)
        
        if success:
            flash(f'RSS feed added successfully to {category}', 'success')
        else:
            flash('Failed to add RSS feed', 'error')
            
    except Exception as e:
        logger.error(f"Error adding RSS feed: {e}")
        flash('Error adding RSS feed', 'error')
    
    return redirect(url_for('rss_management'))

@app.route('/update-rss-feed', methods=['POST'])
def update_rss_feed():
    """Update an existing RSS feed."""
    try:
        feed_id = request.form.get('feed_id')
        category = request.form.get('category')
        feed_url = request.form.get('feed_url')
        feed_title = request.form.get('feed_title')
        is_active = bool(request.form.get('is_active'))
        
        if not feed_id or not category or not feed_url:
            flash('Feed ID, Category, and Feed URL are required', 'error')
            return redirect(url_for('rss_management'))
        
        db = DatabaseManager()
        
        # Update feed in database
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE rss_feeds 
                SET category = ?, feed_url = ?, feed_title = ?, is_active = ?, date_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (category, feed_url, feed_title, is_active, feed_id))
            
            if cursor.rowcount > 0:
                flash('RSS feed updated successfully', 'success')
            else:
                flash('RSS feed not found', 'error')
                
    except Exception as e:
        logger.error(f"Error updating RSS feed: {e}")
        flash('Error updating RSS feed', 'error')
    
    return redirect(url_for('rss_management'))

@app.route('/delete-rss-feed', methods=['POST'])
def delete_rss_feed():
    """Delete an RSS feed."""
    try:
        data = request.get_json()
        feed_url = data.get('feed_url')
        
        if not feed_url:
            return jsonify({'success': False, 'message': 'Feed URL is required'}), 400
        
        db = DatabaseManager()
        success = db.remove_rss_feed(feed_url)
        
        if success:
            return jsonify({'success': True, 'message': 'RSS feed deleted successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to delete RSS feed'}), 400
            
    except Exception as e:
        logger.error(f"Error deleting RSS feed: {e}")
        return jsonify({'success': False, 'message': 'Error deleting RSS feed'}), 500

@app.route('/validate-rss-feed', methods=['POST'])
def validate_rss_feed():
    """Validate an RSS feed."""
    try:
        data = request.get_json()
        feed_url = data.get('feed_url')
        
        if not feed_url:
            return jsonify({'success': False, 'message': 'Feed URL is required'}), 400
        
        # Import RSS validator
        try:
            from .rss_validator import validate_rss_feed as validate_feed
            
            # Validate the feed
            is_valid, message = validate_feed(feed_url)
            
            # Update database with validation results
            db = DatabaseManager()
            status = 'ok' if is_valid else 'error'
            db.update_feed_validation_status(feed_url, status, message)
            
            return jsonify({
                'success': is_valid, 
                'message': message,
                'status': status
            })
            
        except ImportError:
            # Fallback: simple URL check
            import requests
            try:
                response = requests.get(feed_url, timeout=10)
                if response.status_code == 200:
                    db = DatabaseManager()
                    db.update_feed_validation_status(feed_url, 'ok', 'URL accessible')
                    return jsonify({'success': True, 'message': 'URL accessible', 'status': 'ok'})
                else:
                    db = DatabaseManager()
                    db.update_feed_validation_status(feed_url, 'error', f'HTTP {response.status_code}')
                    return jsonify({'success': False, 'message': f'HTTP {response.status_code}', 'status': 'error'})
            except Exception as e:
                db = DatabaseManager()
                db.update_feed_validation_status(feed_url, 'error', str(e))
                return jsonify({'success': False, 'message': str(e), 'status': 'error'})
            
    except Exception as e:
        logger.error(f"Error validating RSS feed: {e}")
        return jsonify({'success': False, 'message': 'Error validating RSS feed'}), 500

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return render_template('error.html', error="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return render_template('error.html', error="Internal server error"), 500

# Create templates directory if it doesn't exist when module is imported
templates_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')
os.makedirs(templates_dir, exist_ok=True)
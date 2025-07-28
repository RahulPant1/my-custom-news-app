#!/usr/bin/env python3
"""
Simple feedback capture web service for email digest buttons.
Handles like/dislike clicks from email and stores them in the database.
"""

from flask import Flask, request, redirect, jsonify, render_template_string
import logging
import sqlite3
from datetime import datetime
import os
from urllib.parse import unquote

# Add src to path for imports
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from database import DatabaseManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize database manager
db_manager = DatabaseManager()

# Success page template
SUCCESS_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Thank You!</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0;
            padding: 0;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .container {
            background: white;
            padding: 40px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 8px 30px rgba(0,0,0,0.2);
            max-width: 400px;
            margin: 20px;
        }
        .icon {
            font-size: 48px;
            margin-bottom: 20px;
        }
        h1 {
            color: #333;
            margin-bottom: 15px;
            font-size: 24px;
        }
        p {
            color: #666;
            line-height: 1.6;
            margin-bottom: 20px;
        }
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 6px;
            text-decoration: none;
            display: inline-block;
            font-weight: 500;
            transition: transform 0.2s;
        }
        .btn:hover {
            transform: translateY(-2px);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">{{ icon }}</div>
        <h1>{{ title }}</h1>
        <p>{{ message }}</p>
        <p style="font-size: 14px; color: #999; margin-top: 30px;">
            This will help us personalize your future news digests.
        </p>
    </div>
</body>
</html>
"""

@app.route('/track/feedback')
def handle_feedback():
    """Handle feedback clicks from email digest."""
    try:
        # Get parameters
        user_id = request.args.get('user_id')
        article_id = request.args.get('article_id')
        feedback_type = request.args.get('feedback')
        
        if not all([user_id, article_id, feedback_type]):
            return jsonify({'error': 'Missing required parameters'}), 400
        
        # Validate feedback type
        valid_feedback_types = ['like', 'dislike', 'more_like_this']
        if feedback_type not in valid_feedback_types:
            return jsonify({'error': 'Invalid feedback type'}), 400
        
        # Store feedback in database
        success = store_feedback(user_id, article_id, feedback_type)
        
        if success:
            logger.info(f"Feedback recorded: user={user_id}, article={article_id}, feedback={feedback_type}")
            
            # Generate appropriate response
            if feedback_type == 'like':
                icon = "👍"
                title = "Thanks for the Like!"
                message = "We'll show you more articles like this one in your future digests."
            elif feedback_type == 'dislike':
                icon = "👎"
                title = "Got It!"
                message = "We'll avoid showing you similar articles in the future. Your feedback helps us improve."
            elif feedback_type == 'more_like_this':
                icon = "➕"
                title = "Perfect!"
                message = "We'll prioritize this type of content in your future digests."
            
            html = render_template_string(SUCCESS_PAGE, 
                                        icon=icon, 
                                        title=title, 
                                        message=message)
            return html
        else:
            logger.error(f"Failed to store feedback: user={user_id}, article={article_id}, feedback={feedback_type}")
            return jsonify({'error': 'Failed to record feedback'}), 500
            
    except Exception as e:
        logger.error(f"Error handling feedback: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/preferences')
def manage_preferences():
    """Handle preference management link from email."""
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400
    
    # Get user preferences
    user_prefs = db_manager.get_user_preferences(user_id)
    if not user_prefs:
        return jsonify({'error': 'User not found'}), 404
    
    # Simple preferences page
    prefs_page = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Manage Preferences</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #f8f9fa;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 500px;
                margin: 0 auto;
                background: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            h1 {{
                color: #333;
                margin-bottom: 20px;
            }}
            .pref-item {{
                margin-bottom: 15px;
                padding: 10px;
                background: #f8f9fa;
                border-radius: 4px;
            }}
            .label {{
                font-weight: 500;
                color: #555;
            }}
            .value {{
                color: #333;
                margin-top: 5px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📧 Email Preferences</h1>
            <div class="pref-item">
                <div class="label">User ID:</div>
                <div class="value">{user_prefs['user_id']}</div>
            </div>
            <div class="pref-item">
                <div class="label">Email:</div>
                <div class="value">{user_prefs.get('email', 'Not set')}</div>
            </div>
            <div class="pref-item">
                <div class="label">Selected Categories:</div>
                <div class="value">{', '.join(user_prefs.get('selected_categories', []))}</div>
            </div>
            <div class="pref-item">
                <div class="label">Digest Frequency:</div>
                <div class="value">{user_prefs.get('digest_frequency', 'daily')}</div>
            </div>
            <div class="pref-item">
                <div class="label">Articles per Digest:</div>
                <div class="value">{user_prefs.get('articles_per_digest', 10)}</div>
            </div>
            <p style="margin-top: 30px; color: #666; font-size: 14px;">
                To modify these preferences, please use the CLI commands or contact support.
            </p>
        </div>
    </body>
    </html>
    """
    
    return prefs_page

@app.route('/unsubscribe')
def unsubscribe():
    """Handle unsubscribe link from email."""
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400
    
    # Simple unsubscribe page
    unsubscribe_page = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Unsubscribe</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #f8f9fa;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 400px;
                margin: 0 auto;
                background: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                text-align: center;
            }}
            h1 {{
                color: #333;
                margin-bottom: 20px;
            }}
            p {{
                color: #666;
                line-height: 1.6;
                margin-bottom: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📧 Unsubscribe</h1>
            <p>To unsubscribe from news digest emails, please use the CLI command:</p>
            <pre style="background: #f8f9fa; padding: 10px; border-radius: 4px; font-size: 12px;">
python main.py user remove {user_id}
            </pre>
            <p style="font-size: 14px; color: #999; margin-top: 30px;">
                Or contact support for assistance.
            </p>
        </div>
    </body>
    </html>
    """
    
    return unsubscribe_page

@app.route('/health')
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/')
def index():
    """Simple index page."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>News Digest Feedback Service</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
            h1 { color: #333; }
            p { color: #666; }
        </style>
    </head>
    <body>
        <h1>📰 News Digest Feedback Service</h1>
        <p>This service handles feedback from email digest buttons.</p>
        <p style="font-size: 14px; color: #999;">Service is running and ready to receive feedback.</p>
    </body>
    </html>
    """

def store_feedback(user_id: str, article_id: str, feedback_type: str) -> bool:
    """Store user feedback in the database."""
    try:
        # First, update user feedback history in user preferences
        user_prefs = db_manager.get_user_preferences(user_id)
        if not user_prefs:
            logger.error(f"User {user_id} not found for feedback")
            return False
        
        # Update feedback history
        feedback_history = user_prefs.get('feedback_history', {})
        feedback_history[str(article_id)] = {
            'feedback': feedback_type,
            'timestamp': datetime.now().isoformat(),
            'source': 'email'
        }
        
        # Update user preferences with new feedback
        user_prefs['feedback_history'] = feedback_history
        success = db_manager.insert_or_update_user_preferences(user_prefs)
        
        if success:
            logger.info(f"Updated feedback history for user {user_id}, article {article_id}")
        
        return success
        
    except Exception as e:
        logger.error(f"Error storing feedback: {e}")
        return False

if __name__ == '__main__':
    # Get port from environment or default to 5000
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    
    logger.info(f"Starting feedback service on {host}:{port}")
    app.run(host=host, port=port, debug=False)
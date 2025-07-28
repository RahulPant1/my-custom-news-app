"""Interactive web interface for category selection and user management."""

import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
import os

try:
    from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
    flask_available = True
except ImportError:
    flask_available = False

from database import DatabaseManager
from user_interface import UserPreferencesManager, DigestGenerator
from config import AI_CATEGORIES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InteractiveNewsInterface:
    """Interactive web interface for news digest management."""
    
    def __init__(self, port: int = 5000, debug: bool = False):
        if not flask_available:
            raise ImportError("Flask not installed. Run: pip install flask")
        
        self.app = Flask(__name__, 
                        template_folder='../templates',
                        static_folder='../static')
        self.app.secret_key = 'news_digest_secret_key_change_in_production'
        self.port = port
        self.debug = debug
        
        self.db_manager = DatabaseManager()
        self.prefs_manager = UserPreferencesManager(self.db_manager)
        self.digest_generator = DigestGenerator(self.db_manager)
        
        # Category descriptions and sample headlines
        self.category_info = self._load_category_info()
        
        # Setup routes
        self._setup_routes()
    
    def _load_category_info(self) -> Dict[str, Dict]:
        """Load category information with descriptions and sample data."""
        return {
            "Science & Discovery": {
                "description": "Latest scientific research, discoveries, and innovations from labs worldwide",
                "icon": "🔬",
                "sample_headlines": [
                    "Revolutionary Gene Therapy Shows Promise for Rare Diseases",
                    "Astronomers Discover Earth-like Planet in Habitable Zone",
                    "Breakthrough in Quantum Computing Achieved by Research Team"
                ],
                "color": "#2196F3"
            },
            "Technology & Gadgets": {
                "description": "Tech news, product launches, software updates, and digital innovations",
                "icon": "💻",
                "sample_headlines": [
                    "Apple Unveils Next-Generation Processor with 30% Performance Boost",
                    "AI-Powered Smart Home System Revolutionizes Energy Efficiency",
                    "New Smartphone Camera Technology Enables Professional Photography"
                ],
                "color": "#4CAF50"
            },
            "Health & Wellness": {
                "description": "Medical research, health tips, wellness trends, and healthcare innovations",
                "icon": "🏥",
                "sample_headlines": [
                    "New Study Links Mediterranean Diet to Improved Brain Health",
                    "Revolutionary Cancer Treatment Shows 90% Success Rate",
                    "Mental Health Apps Prove Effective in Clinical Trials"
                ],
                "color": "#FF9800"
            },
            "Business & Finance": {
                "description": "Market news, business developments, economic trends, and financial insights",
                "icon": "💼",
                "sample_headlines": [
                    "Tech Stocks Surge Following Positive Earnings Reports",
                    "Sustainable Energy Investments Reach Record High",
                    "Cryptocurrency Market Shows Signs of Stabilization"
                ],
                "color": "#9C27B0"
            },
            "Global Affairs": {
                "description": "International news, politics, diplomacy, and world events",
                "icon": "🌍",
                "sample_headlines": [
                    "Historic Climate Agreement Signed by 50 Nations",
                    "International Trade Relations Show Signs of Improvement",
                    "Global Health Initiative Launches in Developing Countries"
                ],
                "color": "#F44336"
            },
            "Environment & Climate": {
                "description": "Climate change, environmental issues, sustainability, and green technology",
                "icon": "🌱",
                "sample_headlines": [
                    "Renewable Energy Now Powers 40% of European Grid",
                    "Innovative Carbon Capture Technology Deployed Globally",
                    "Biodiversity Conservation Efforts Show Promising Results"
                ],
                "color": "#4CAF50"
            },
            "Good Vibes (Positive News)": {
                "description": "Uplifting stories, positive developments, and inspiring human achievements",
                "icon": "😊",
                "sample_headlines": [
                    "Community Fundraiser Raises $1M for Local Children's Hospital",
                    "Young Inventor Creates Device to Clean Ocean Plastic",
                    "Retired Teacher's Free Tutoring Program Transforms Lives"
                ],
                "color": "#FFEB3B"
            },
            "Pop Culture & Lifestyle": {
                "description": "Entertainment news, culture trends, lifestyle tips, and celebrity updates",
                "icon": "🎭",
                "sample_headlines": [
                    "Independent Film Festival Showcases Diverse Voices",
                    "Sustainable Fashion Trends Gain Mainstream Adoption",
                    "New Documentary Explores Impact of Social Media"
                ],
                "color": "#E91E63"
            },
            "For Young Minds": {
                "description": "Educational content, science for kids, learning resources, and youth-focused stories",
                "icon": "🎓",
                "sample_headlines": [
                    "Interactive Science Museum Opens Virtual Reality Lab",
                    "Student-Led Environmental Project Wins National Award",
                    "New Educational App Makes Math Fun for Elementary Students"
                ],
                "color": "#00BCD4"
            },
            "DIY, Skills & How-To": {
                "description": "Tutorials, skill development, how-to guides, and creative project ideas",
                "icon": "🔧",
                "sample_headlines": [
                    "Easy Weekend Projects That Add Value to Your Home",
                    "Master Chef Shares Simple Techniques for Gourmet Cooking",
                    "Urban Gardening: Growing Fresh Herbs in Small Spaces"
                ],
                "color": "#795548"
            }
        }
    
    def _setup_routes(self):
        """Setup Flask routes."""
        
        @self.app.route('/')
        def index():
            """Main dashboard."""
            stats = self.db_manager.get_incremental_stats()
            return render_template('index.html', 
                                 categories=self.category_info,
                                 stats=stats)
        
        @self.app.route('/categories')
        def categories():
            """Category selection interface."""
            return render_template('categories.html', 
                                 categories=self.category_info,
                                 ai_categories=AI_CATEGORIES)
        
        @self.app.route('/create-user', methods=['GET', 'POST'])
        def create_user():
            """Create new user with category preferences."""
            if request.method == 'POST':
                try:
                    user_id = request.form.get('user_id')
                    email = request.form.get('email')
                    selected_categories = request.form.getlist('categories')
                    articles_per_digest = int(request.form.get('articles_per_digest', 10))
                    output_format = request.form.get('output_format', 'text')
                    
                    if not selected_categories:
                        flash('Please select at least one category', 'error')
                        return render_template('create_user.html', 
                                             categories=self.category_info)
                    
                    created_user_id = self.prefs_manager.create_user(
                        user_id=user_id,
                        email=email,
                        categories=selected_categories,
                        articles_per_digest=articles_per_digest,
                        preferred_output_format=output_format
                    )
                    
                    flash(f'User {created_user_id} created successfully!', 'success')
                    return redirect(url_for('user_profile', user_id=created_user_id))
                    
                except Exception as e:
                    flash(f'Error creating user: {str(e)}', 'error')
                    logger.error(f"Error creating user: {e}")
            
            return render_template('create_user.html', 
                                 categories=self.category_info)
        
        @self.app.route('/user/<user_id>')
        def user_profile(user_id):
            """User profile and preferences."""
            prefs = self.prefs_manager.get_user_preferences(user_id)
            if not prefs:
                flash(f'User {user_id} not found', 'error')
                return redirect(url_for('index'))
            
            return render_template('user_profile.html', 
                                 user=prefs, 
                                 categories=self.category_info)
        
        @self.app.route('/user/<user_id>/edit', methods=['GET', 'POST'])
        def edit_user(user_id):
            """Edit user preferences."""
            prefs = self.prefs_manager.get_user_preferences(user_id)
            if not prefs:
                flash(f'User {user_id} not found', 'error')
                return redirect(url_for('index'))
            
            if request.method == 'POST':
                try:
                    updates = {
                        'email': request.form.get('email', prefs['email']),
                        'selected_categories': request.form.getlist('categories'),
                        'articles_per_digest': int(request.form.get('articles_per_digest', prefs['articles_per_digest'])),
                        'preferred_output_format': request.form.get('output_format', prefs['preferred_output_format'])
                    }
                    
                    if not updates['selected_categories']:
                        flash('Please select at least one category', 'error')
                    else:
                        self.prefs_manager.update_user_preferences(user_id, **updates)
                        flash('Preferences updated successfully!', 'success')
                        return redirect(url_for('user_profile', user_id=user_id))

                except Exception as e:
                    flash(f'Error updating preferences: {str(e)}', 'error')
                    logger.error(f"Error updating user {user_id}: {e}")

            return render_template('edit_user.html', 
                                 user=prefs, 
                                 categories=self.category_info)

        @self.app.route('/generate-digest/<user_id>')
        def generate_digest_route(user_id):
            """Generate and display a news digest."""
            try:
                digest = self.digest_generator.generate_digest(user_id)
                return render_template('digest.html', digest=digest, user_id=user_id)
            except Exception as e:
                flash(f'Error generating digest: {str(e)}', 'error')
                logger.error(f"Error generating digest for {user_id}: {e}")
                return redirect(url_for('user_profile', user_id=user_id))

        # API endpoints
        @self.app.route('/api/stats')
        def api_stats():
            return jsonify(self.db_manager.get_incremental_stats())

        @self.app.route('/api/users')
        def api_users():
            users = self.db_manager.get_all_users()
            return jsonify(users)

    def create_templates(self):
        """Create necessary HTML, CSS, and JS files."""
        template_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')
        static_dir = os.path.join(os.path.dirname(__file__), '..', 'static')
        os.makedirs(template_dir, exist_ok=True)
        os.makedirs(static_dir, exist_ok=True)

        # Base template
        base_html = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}News Digest{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('index') }}">News Digest</a>
            <div class="collapse navbar-collapse">
                <ul class="navbar-nav ms-auto">
                    <li class="nav-item"><a class="nav-link" href="{{ url_for('categories') }}">Categories</a></li>
                    <li class="nav-item"><a class="nav-link" href="{{ url_for('create_user') }}">Create User</a></li>
                </ul>
            </div>
        </div>
    </nav>
    <main class="container mt-4">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </main>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="{{ url_for('static', filename='script.js') }}"></script>
</body>
</html>
"""
        with open(os.path.join(template_dir, 'base.html'), 'w') as f:
            f.write(base_html)

        # Index page
        index_html = """
{% extends "base.html" %}
{% block title %}Dashboard{% endblock %}
{% block content %}
    <h1>Dashboard</h1>
    <div id="stats-container">
        <p>Articles in DB: {{ stats.total_articles }}</p>
        <p>Processed today: {{ stats.processed_today }}</p>
    </div>
    <h2>Categories</h2>
    <div class="row">
        {% for cat, info in categories.items() %}
        <div class="col-md-4 mb-3">
            <div class="card">
                <div class="card-body">
                    <h5 class="card-title">{{ info.icon }} {{ cat }}</h5>
                    <p class="card-text">{{ info.description }}</p>
                </div>
            </div>
        </div>
        {% endfor %}
    </div>
{% endblock %}
"""
        with open(os.path.join(template_dir, 'index.html'), 'w') as f:
            f.write(index_html)

        # Categories page
        categories_html = """
{% extends "base.html" %}
{% block title %}Categories{% endblock %}
{% block content %}
    <h1>All Categories</h1>
    <ul>
    {% for cat in ai_categories %}
        <li>{{ cat }}</li>
    {% endfor %}
    </ul>
{% endblock %}
"""
        with open(os.path.join(template_dir, 'categories.html'), 'w') as f:
            f.write(categories_html)

        # Create user page
        create_user_html = """
{% extends "base.html" %}
{% block title %}Create User{% endblock %}
{% block content %}
    <h1>Create User</h1>
    <form method="post">
        <div class="mb-3">
            <label for="user_id" class="form-label">User ID</label>
            <input type="text" class="form-control" id="user_id" name="user_id" required>
        </div>
        <div class="mb-3">
            <label for="email" class="form-label">Email</label>
            <input type="email" class="form-control" id="email" name="email">
        </div>
        <div class="mb-3">
            <label class="form-label">Select Categories</label>
            {% for category, info in categories.items() %}
            <div class="form-check">
                <input class="form-check-input" type="checkbox" value="{{ category }}" id="cat_{{ loop.index }}" name="categories">
                <label class="form-check-label" for="cat_{{ loop.index }}">
                    {{ info.icon }} {{ category }}
                </label>
            </div>
            {% endfor %}
        </div>
        <button type="submit" class="btn btn-primary">Create</button>
    </form>
{% endblock %}
"""
        with open(os.path.join(template_dir, 'create_user.html'), 'w') as f:
            f.write(create_user_html)
        
        # User profile page
        user_profile_html = """
{% extends "base.html" %}
{% block title %}User Profile{% endblock %}
{% block content %}
    <h1>User Profile: {{ user.user_id }}</h1>
    <p>Email: {{ user.email }}</p>
    <p>Categories: {{ user.selected_categories|join(', ') }}</p>
    <a href="{{ url_for('edit_user', user_id=user.user_id) }}" class="btn btn-secondary">Edit</a>
    <a href="{{ url_for('generate_digest_route', user_id=user.user_id) }}" class="btn btn-primary">Generate Digest</a>
{% endblock %}
"""
        with open(os.path.join(template_dir, 'user_profile.html'), 'w') as f:
            f.write(user_profile_html)

        # Edit user page
        edit_user_html = """
{% extends "base.html" %}
{% block title %}Edit User{% endblock %}
{% block content %}
    <h1>Edit User: {{ user.user_id }}</h1>
    <form method="post">
        <div class="mb-3">
            <label for="email" class="form-label">Email</label>
            <input type="email" class="form-control" id="email" name="email" value="{{ user.email }}">
        </div>
        <div class="mb-3">
            <label class="form-label">Select Categories</label>
            {% for category, info in categories.items() %}
            <div class="form-check">
                <input class="form-check-input" type="checkbox" value="{{ category }}" id="cat_{{ loop.index }}" name="categories" {% if category in user.selected_categories %}checked{% endif %}>
                <label class="form-check-label" for="cat_{{ loop.index }}">
                    {{ info.icon }} {{ category }}
                </label>
            </div>
            {% endfor %}
        </div>
        <button type="submit" class="btn btn-primary">Save Changes</button>
    </form>
{% endblock %}
"""
        with open(os.path.join(template_dir, 'edit_user.html'), 'w') as f:
            f.write(edit_user_html)

        # Digest page
        digest_html = """
{% extends "base.html" %}
{% block title %}News Digest{% endblock %}
{% block content %}
    <h1>Your News Digest for {{ user_id }}</h1>
    <pre>{{ digest }}</pre>
{% endblock %}
"""
        with open(os.path.join(template_dir, 'digest.html'), 'w') as f:
            f.write(digest_html)

        # CSS
        css_content = """
body { font-family: sans-serif; }
.card { margin-bottom: 1.5rem; }
"""
        with open(os.path.join(static_dir, 'style.css'), 'w') as f:
            f.write(css_content)

        # JavaScript
        js_content = """
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('stats-container')) {
        fetch('/api/stats')
            .then(response => response.json())
            .then(data => {
                const container = document.getElementById('stats-container');
                container.innerHTML = `
                    <p>Articles in DB: ${data.total_articles}</p>
                    <p>Processed today: ${data.processed_today}</p>
                `;
            });
    }
});
"""
        with open(os.path.join(static_dir, 'script.js'), 'w') as f:
            f.write(js_content)

    def run(self):
        """Run the interactive interface."""
        logger.info(f"Starting interactive interface on port {self.port}")
        
        # Create templates and static files
        self.create_templates()
        
        # Run Flask app
        self.app.run(host='0.0.0.0', port=self.port, debug=self.debug)


def main():
    """Run interactive interface."""
    try:
        interface = InteractiveNewsInterface(port=5000, debug=True)
        print("\n" + "="*60)
        print("NEWS DIGEST INTERACTIVE INTERFACE")
        print("="*60)
        print("Starting web interface...")
        print("Open your browser and go to: http://localhost:5000")
        print("\nFeatures:")
        print("- Browse and preview news categories")
        print("- Create personalized user profiles")
        print("- Generate custom news digests")
        print("- Interactive category selection")
        print("="*60)
        
        interface.run()
        
    except ImportError as e:
        print(f"Error: {e}")
        print("Please install Flask: pip install flask")
    except Exception as e:
        print(f"Error starting interface: {e}")


if __name__ == "__main__":
    main()
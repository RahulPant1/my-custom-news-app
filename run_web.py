#!/usr/bin/env python3
"""Entry point for the web interface that handles imports correctly."""

import sys
import os

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now import and run the web interface
from src.web_interface import app

if __name__ == '__main__':
    # Run the Flask app
    port = int(os.getenv('PORT', 5000))
    debug = True  # Enable debug mode for testing
    
    # Explicitly set debug mode on the app config
    app.config['DEBUG'] = True
    app.config['TESTING'] = True
    
    print(f"🌐 Starting News Digest Web Interface")
    print(f"   URL: http://localhost:{port}")
    print(f"   Debug: {debug}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
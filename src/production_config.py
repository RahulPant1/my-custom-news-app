"""Production configuration and deployment settings."""

import os
import logging.config
from typing import Dict, Any

# Production Environment Variables
PRODUCTION_ENV_VARS = {
    # Flask Configuration
    'FLASK_ENV': 'production',
    'FLASK_SECRET_KEY': 'your-super-secure-secret-key-here',
    'JWT_SECRET_KEY': 'your-jwt-secret-key-here',
    
    # Database Configuration
    'DATABASE_PATH': '/app/data/news_digest.db',
    'DATABASE_POOL_SIZE': '20',
    
    # Redis Configuration
    'REDIS_HOST': 'redis',  # Docker service name
    'REDIS_PORT': '6379',
    'REDIS_DB': '0',
    'REDIS_PASSWORD': '',  # Set if using password
    
    # AI Service Configuration
    'PRIMARY_AI_PROVIDER': 'auto',
    'AI_BATCH_SIZE': '50',
    'AI_REQUEST_TIMEOUT': '30',
    'AI_MAX_RETRIES': '3',
    
    # Email Configuration
    'SMTP_SERVER': 'smtp.gmail.com',
    'SMTP_PORT': '587',
    'SMTP_USERNAME': 'your-email@gmail.com',
    'SMTP_PASSWORD': 'your-app-password',
    'FROM_EMAIL': 'your-email@gmail.com',
    'FROM_NAME': 'News Digest',
    
    # Security Configuration
    'ALLOWED_ORIGINS': 'https://yourdomain.com',
    'ADMIN_USERS': 'admin@yourdomain.com',
    
    # Application Settings
    'BASE_URL': 'https://yourdomain.com',
    'LOG_LEVEL': 'INFO',
    'MAX_WORKERS': '4',
    
    # Monitoring
    'METRICS_ENABLED': 'true',
    'HEALTH_CHECK_ENABLED': 'true',
    
    # Rate Limiting
    'RATE_LIMIT_STORAGE_URL': 'redis://redis:6379/1',
}

# Production Logging Configuration
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s [%(pathname)s:%(lineno)d]'
        },
        'simple': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
        'json': {
            'format': '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s", "pathname": "%(pathname)s", "lineno": %(lineno)d}'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'simple',
            'stream': 'ext://sys.stdout'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'INFO',
            'formatter': 'detailed',
            'filename': '/app/logs/application.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5
        },
        'error_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'ERROR',
            'formatter': 'detailed',
            'filename': '/app/logs/errors.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5
        },
        'json_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'INFO',
            'formatter': 'json',
            'filename': '/app/logs/application.json',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5
        }
    },
    'loggers': {
        '': {  # Root logger
            'handlers': ['console', 'file', 'error_file'],
            'level': 'INFO',
            'propagate': False
        },
        'gunicorn.error': {
            'handlers': ['console', 'error_file'],
            'level': 'INFO',
            'propagate': False
        },
        'gunicorn.access': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False
        }
    }
}

# Security Headers Configuration
SECURITY_HEADERS = {
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self'",
    'Permissions-Policy': 'geolocation=(), microphone=(), camera=()'
}

# Rate Limiting Configuration
RATE_LIMIT_CONFIG = {
    'default': '100 per hour',
    'authenticated': '1000 per hour',
    'admin': '5000 per hour',
    'api_endpoints': {
        '/api/run-pipeline': '5 per hour',
        '/api/send-digest': '20 per hour',
        '/api/delete-user': '10 per hour',
        '/create-user': '20 per hour'
    }
}

# Database Configuration
DATABASE_CONFIG = {
    'pool_size': 20,
    'timeout': 30,
    'pragmas': {
        'journal_mode': 'WAL',
        'synchronous': 'NORMAL',
        'cache_size': 10000,
        'temp_store': 'MEMORY',
        'mmap_size': 268435456,  # 256MB
        'foreign_keys': 'ON'
    }
}

# Background Jobs Configuration
JOBS_CONFIG = {
    'num_workers': 4,
    'max_jobs': 1000,
    'job_timeout': 600,  # 10 minutes
    'cleanup_interval': 3600,  # 1 hour
    'max_job_age_hours': 24
}

# Monitoring Configuration
MONITORING_CONFIG = {
    'metrics_enabled': True,
    'health_checks_enabled': True,
    'alerts_enabled': True,
    'alert_thresholds': {
        'cpu_percent': 80,
        'memory_percent': 85,
        'disk_percent': 90,
        'error_rate_percent': 10,
        'response_time_seconds': 2.0
    }
}

# Cache Configuration
CACHE_CONFIG = {
    'default_ttl': 300,  # 5 minutes
    'ttl_settings': {
        'user_preferences': 300,     # 5 minutes
        'articles': 600,             # 10 minutes
        'feeds': 3600,               # 1 hour
        'stats': 60,                 # 1 minute
        'api_responses': 300         # 5 minutes
    }
}


def setup_production_environment():
    """Set up production environment variables."""
    for key, value in PRODUCTION_ENV_VARS.items():
        if key not in os.environ:
            os.environ[key] = value
            print(f"Set environment variable: {key}")


def setup_production_logging():
    """Configure production logging."""
    # Ensure log directory exists
    log_dir = '/app/logs'
    os.makedirs(log_dir, exist_ok=True)
    
    # Apply logging configuration
    logging.config.dictConfig(LOGGING_CONFIG)
    
    logger = logging.getLogger(__name__)
    logger.info("Production logging configuration applied")


def get_gunicorn_config() -> Dict[str, Any]:
    """Get Gunicorn configuration for production."""
    return {
        'bind': '0.0.0.0:8000',
        'workers': int(os.getenv('MAX_WORKERS', '4')),
        'worker_class': 'sync',
        'worker_connections': 1000,
        'max_requests': 1000,
        'max_requests_jitter': 100,
        'timeout': 30,
        'keepalive': 2,
        'preload_app': True,
        'access_logfile': '/app/logs/gunicorn_access.log',
        'error_logfile': '/app/logs/gunicorn_error.log',
        'log_level': 'info',
        'capture_output': True,
        'enable_stdio_inheritance': True
    }


def get_nginx_config() -> str:
    """Get Nginx configuration for production."""
    return """
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL Configuration
    ssl_certificate /etc/ssl/certs/your-domain.crt;
    ssl_certificate_key /etc/ssl/private/your-domain.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Gzip Compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;

    # Rate Limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=general:10m rate=30r/s;

    # Static Files
    location /static/ {
        alias /app/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # API Endpoints (with rate limiting)
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_timeout 30s;
    }

    # Health Check (no rate limiting)
    location /health {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # General Application
    location / {
        limit_req zone=general burst=50 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_timeout 30s;
    }

    # Security: Block access to sensitive files
    location ~ /\. {
        deny all;
    }

    location ~* \.(env|ini|conf)$ {
        deny all;
    }
}
"""


def get_docker_compose_config() -> str:
    """Get Docker Compose configuration for production."""
    return """
version: '3.8'

services:
  app:
    build: .
    restart: unless-stopped
    environment:
      - FLASK_ENV=production
      - REDIS_HOST=redis
      - DATABASE_PATH=/app/data/news_digest.db
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    depends_on:
      - redis
    networks:
      - app-network

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
      - ./ssl:/etc/ssl
      - ./static:/app/static:ro
    depends_on:
      - app
    networks:
      - app-network

  redis:
    image: redis:alpine
    restart: unless-stopped
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redis-data:/data
    networks:
      - app-network

  cron:
    build: .
    restart: unless-stopped
    command: python -m cron_scheduler
    environment:
      - FLASK_ENV=production
      - REDIS_HOST=redis
      - DATABASE_PATH=/app/data/news_digest.db
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    depends_on:
      - redis
      - app
    networks:
      - app-network

volumes:
  redis-data:

networks:
  app-network:
    driver: bridge
"""


def get_dockerfile() -> str:
    """Get Dockerfile for production."""
    return """
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn psutil

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/data /app/logs

# Set environment variables
ENV PYTHONPATH=/app/src
ENV FLASK_APP=src/web_interface.py

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \\
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Start command
CMD ["gunicorn", "--config", "src/gunicorn_config.py", "src.web_interface:app"]
"""


def create_production_files():
    """Create all production configuration files."""
    base_path = os.path.dirname(os.path.dirname(__file__))
    
    # Create gunicorn config
    gunicorn_config = get_gunicorn_config()
    gunicorn_config_py = f"""
# Gunicorn configuration for production
bind = "{gunicorn_config['bind']}"
workers = {gunicorn_config['workers']}
worker_class = "{gunicorn_config['worker_class']}"
worker_connections = {gunicorn_config['worker_connections']}
max_requests = {gunicorn_config['max_requests']}
max_requests_jitter = {gunicorn_config['max_requests_jitter']}
timeout = {gunicorn_config['timeout']}
keepalive = {gunicorn_config['keepalive']}
preload_app = {gunicorn_config['preload_app']}
accesslog = "{gunicorn_config['access_logfile']}"
errorlog = "{gunicorn_config['error_logfile']}"
loglevel = "{gunicorn_config['log_level']}"
capture_output = {gunicorn_config['capture_output']}
enable_stdio_inheritance = {gunicorn_config['enable_stdio_inheritance']}

def when_ready(server):
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    worker.log.info("worker received INT or QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)
"""
    
    with open(os.path.join(base_path, 'src', 'gunicorn_config.py'), 'w') as f:
        f.write(gunicorn_config_py)
    
    # Create other config files
    config_files = {
        'nginx.conf': get_nginx_config(),
        'docker-compose.yml': get_docker_compose_config(),
        'Dockerfile': get_dockerfile()
    }
    
    for filename, content in config_files.items():
        with open(os.path.join(base_path, filename), 'w') as f:
            f.write(content)
    
    print("Production configuration files created:")
    print("- src/gunicorn_config.py")
    print("- nginx.conf")
    print("- docker-compose.yml") 
    print("- Dockerfile")


if __name__ == "__main__":
    print("Setting up production configuration...")
    setup_production_environment()
    setup_production_logging()
    create_production_files()
    print("Production setup complete!")
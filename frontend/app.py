from flask import Flask, render_template, session, flash, redirect, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
import os
import logging
from logging.handlers import RotatingFileHandler

# Import blueprints
from blueprints.aws.auth import aws_auth_bp
from blueprints.aws.script_runner import aws_script_runner_bp

def create_app(test_config=None):
    """Create and configure the Flask application"""
    
    app = Flask(__name__, instance_relative_config=True)
    
    # Load default configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-key-for-development-only'),
        SESSION_TYPE='filesystem',
        SESSION_PERMANENT=False,
        SESSION_USE_SIGNER=True,
        API_BASE_URL=os.environ.get('API_BASE_URL', 'http://localhost:8000'),
        BACKEND_TIMEOUT=30,  # Timeout for backend API requests in seconds
        UPLOAD_FOLDER=os.path.join(app.instance_path, 'uploads'),
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,  # Max upload size (10MB)
    )
    
    # Load test config if passed
    if test_config:
        app.config.update(test_config)
    
    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    except OSError:
        pass
    
    # Configure logging
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/frontend.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Frontend startup')
    
    # Apply ProxyFix middleware for proper handling of X-Forwarded headers
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    
    # Register blueprints
    app.register_blueprint(aws_auth_bp, url_prefix='/aws/auth')
    app.register_blueprint(aws_script_runner_bp, url_prefix='/aws/script-runner')
    
    # Register error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500
    
    # Root route - landing page
    @app.route('/')
    def index():
        return render_template('index.html')
    
    return app

# Create the application instance
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

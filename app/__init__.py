"""Flask application factory and extensions."""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail
from flask_migrate import Migrate
from flask_cors import CORS

from config import config

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()
csrf = CSRFProtect()
mail = Mail()
migrate = Migrate()

# Configure login manager
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'
login_manager.session_protection = 'strong'


def create_app(config_name='default'):
    """Application factory function."""
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)
    CORS(app)
    
    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.projects import projects_bp
    from app.routes.collaboration import collab_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.notifications import notifications_bp
    from app.api.routes import api_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(projects_bp, url_prefix='/projects')
    app.register_blueprint(collab_bp, url_prefix='/collaboration')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(notifications_bp, url_prefix='/notifications')
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    
    # Exempt API from CSRF
    csrf.exempt(api_bp)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register CLI commands
    register_cli_commands(app)
    
    # Create upload folder
    import os
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    # Update last_seen on every authenticated request
    from datetime import datetime, timezone as tz

    @app.before_request
    def update_last_seen():
        from flask_login import current_user as _cu
        if _cu.is_authenticated:
            _cu.last_seen = datetime.now(tz.utc)
            db.session.commit()

    # Add context processor for global template variables
    @app.context_processor
    def inject_now():
        return {'now': datetime.now(tz.utc)}
    
    return app


def register_error_handlers(app):
    """Register custom error handlers."""
    from flask import render_template
    
    @app.errorhandler(400)
    def bad_request(error):
        return render_template('errors/400.html'), 400
    
    @app.errorhandler(403)
    def forbidden(error):
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500


def register_cli_commands(app):
    """Register custom CLI commands."""
    import click
    
    @app.cli.command('init-db')
    def init_db():
        """Initialize the database."""
        db.create_all()
        click.echo('Database initialized!')
    
    @app.cli.command('seed-db')
    def seed_db():
        """Seed the database with sample data."""
        from app.utils.seed import seed_database
        seed_database()
        click.echo('Database seeded!')
    
    @app.cli.command('create-admin')
    @click.argument('email')
    @click.argument('password')
    def create_admin(email, password):
        """Create an admin user."""
        from app.models import User, Role
        admin_role = Role.query.filter_by(name='admin').first()
        if not admin_role:
            admin_role = Role(name='admin', description='Administrator')
            db.session.add(admin_role)
        
        user = User(
            email=email,
            first_name='Admin',
            last_name='User',
            is_active=True,
            is_verified=True
        )
        user.set_password(password)
        user.roles.append(admin_role)
        db.session.add(user)
        db.session.commit()
        click.echo(f'Admin user {email} created!')

    @app.cli.command('send-test-email')
    @click.argument('recipient')
    @click.option('--subject', default='Test Email from ColabPlatform')
    def send_test_email(recipient, subject):
        """Send a simple test email to the given recipient."""
        from app.utils.email import send_email
        text = 'This is a test email sent from your ColabPlatform instance.'
        html = '<p>This is a <strong>test</strong> email sent from your ColabPlatform instance.</p>'
        try:
            send_email(subject, [recipient], text, html)
            click.echo(f'Test email sent to {recipient}')
        except Exception as e:
            click.echo(f'Failed to send test email: {e}')

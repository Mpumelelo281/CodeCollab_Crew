"""Security utilities."""
import re
from datetime import datetime, timezone, timedelta
from flask import current_app
from itsdangerous import URLSafeTimedSerializer


def validate_password_strength(password):
    """
    Validate password meets security requirements.
    Returns (is_valid, message).
    """
    config = current_app.config
    min_length = config.get('PASSWORD_MIN_LENGTH', 8)
    
    if len(password) < min_length:
        return False, f'Password must be at least {min_length} characters long.'
    
    if config.get('PASSWORD_REQUIRE_UPPERCASE', True):
        if not re.search(r'[A-Z]', password):
            return False, 'Password must contain at least one uppercase letter.'
    
    if config.get('PASSWORD_REQUIRE_LOWERCASE', True):
        if not re.search(r'[a-z]', password):
            return False, 'Password must contain at least one lowercase letter.'
    
    if config.get('PASSWORD_REQUIRE_DIGIT', True):
        if not re.search(r'\d', password):
            return False, 'Password must contain at least one digit.'
    
    if config.get('PASSWORD_REQUIRE_SPECIAL', True):
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, 'Password must contain at least one special character.'
    
    # Check common passwords
    common_passwords = ['password', '123456', 'qwerty', 'password123', 'admin']
    if password.lower() in common_passwords:
        return False, 'Password is too common. Please choose a stronger password.'
    
    return True, 'Password meets requirements.'


def generate_token(user_id, purpose, expiration=3600):
    """
    Generate a secure token for email verification, password reset, etc.
    """
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps({'user_id': user_id, 'purpose': purpose})


def verify_token(token, purpose, max_age=3600):
    """
    Verify a token and return the user_id if valid.
    Returns None if invalid or expired.
    """
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        data = serializer.loads(token, max_age=max_age)
        if data.get('purpose') != purpose:
            return None
        return data.get('user_id')
    except Exception:
        return None


def sanitize_input(text):
    """
    Sanitize user input to prevent XSS attacks.
    """
    if not text:
        return text
    
    # Remove potentially dangerous HTML tags
    dangerous_tags = ['script', 'iframe', 'object', 'embed', 'form']
    pattern = re.compile(r'<\/?(' + '|'.join(dangerous_tags) + r')[^>]*>', re.IGNORECASE)
    text = pattern.sub('', text)
    
    # Escape HTML entities
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&#x27;')
    
    return text


def validate_file_extension(filename, allowed_extensions=None):
    """
    Validate file has an allowed extension.
    """
    if not allowed_extensions:
        allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', set())
    
    if '.' not in filename:
        return False
    
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in allowed_extensions


def generate_secure_filename(original_filename):
    """
    Generate a secure filename for uploads.
    """
    import uuid
    from werkzeug.utils import secure_filename
    
    safe_name = secure_filename(original_filename)
    unique_id = uuid.uuid4().hex[:8]
    
    if '.' in safe_name:
        name, ext = safe_name.rsplit('.', 1)
        return f"{name}_{unique_id}.{ext}"
    
    return f"{safe_name}_{unique_id}"


def check_rate_limit(key, limit, period):
    """
    Simple in-memory rate limiting check.
    In production, use Redis or similar.
    """
    # This is a placeholder - in production use flask-limiter with Redis
    return True


class CSRFProtect:
    """Additional CSRF protection utilities."""
    
    @staticmethod
    def generate_csrf_token():
        """Generate a CSRF token."""
        from flask_wtf.csrf import generate_csrf
        return generate_csrf()
    
    @staticmethod
    def validate_csrf_token(token):
        """Validate a CSRF token."""
        from flask_wtf.csrf import validate_csrf
        try:
            validate_csrf(token)
            return True
        except Exception:
            return False

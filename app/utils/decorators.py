"""Custom route decorators."""
from functools import wraps
from flask import flash, redirect, url_for, abort
from flask_login import current_user
from app.models import Project, ProjectMember


def role_required(*roles):
    """
    Decorator to require specific roles.
    Usage: @role_required('admin', 'lecturer')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login'))
            
            user_roles = [r.name for r in current_user.roles]
            if not any(role in user_roles for role in roles):
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('dashboard.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def lecturer_required(f):
    """
    Decorator to require lecturer role.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        
        if not current_user.is_lecturer and not current_user.is_admin:
            flash('This page is only accessible to faculty members.', 'danger')
            return redirect(url_for('dashboard.index'))
        
        return f(*args, **kwargs)
    return decorated_function


def student_required(f):
    """
    Decorator to require student role.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        
        if not current_user.is_student:
            flash('This page is only accessible to students.', 'danger')
            return redirect(url_for('dashboard.index'))
        
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    Decorator to require admin role.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        
        if not current_user.is_admin:
            flash('This page is only accessible to administrators.', 'danger')
            return redirect(url_for('dashboard.index'))
        
        return f(*args, **kwargs)
    return decorated_function


def project_owner_required(f):
    """
    Decorator to require user to be the project owner.
    Expects 'project_id' in URL parameters.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        
        project_id = kwargs.get('project_id')
        if not project_id:
            abort(400)
        
        project = Project.query.get_or_404(project_id)
        
        if project.owner_id != current_user.id and not current_user.is_admin:
            flash('You do not have permission to manage this project.', 'danger')
            return redirect(url_for('projects.view_project', project_id=project_id))
        
        return f(*args, **kwargs)
    return decorated_function


def project_member_required(f):
    """
    Decorator to require user to be a project member or owner.
    Expects 'project_id' in URL parameters.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        
        project_id = kwargs.get('project_id')
        if not project_id:
            abort(400)
        
        project = Project.query.get_or_404(project_id)
        
        # Check if owner
        if project.owner_id == current_user.id:
            return f(*args, **kwargs)
        
        # Check if admin
        if current_user.is_admin:
            return f(*args, **kwargs)
        
        # Check if active member
        membership = ProjectMember.query.filter_by(
            project_id=project_id,
            user_id=current_user.id,
            status='active'
        ).first()
        
        if not membership:
            flash('You are not a member of this project.', 'danger')
            return redirect(url_for('projects.view_project', project_id=project_id))
        
        return f(*args, **kwargs)
    return decorated_function


def verified_email_required(f):
    """
    Decorator to require verified email.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        
        if not current_user.is_verified:
            flash('Please verify your email address to access this feature.', 'warning')
            return redirect(url_for('auth.resend_verification'))
        
        return f(*args, **kwargs)
    return decorated_function


def ajax_required(f):
    """
    Decorator to require AJAX request.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import request, jsonify
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if request.is_json:
                return f(*args, **kwargs)
            return jsonify({'error': 'AJAX request required'}), 400
        return f(*args, **kwargs)
    return decorated_function

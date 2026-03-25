"""RESTful API routes."""
from datetime import datetime, timezone
from functools import wraps
from flask import Blueprint, request, jsonify, current_app
from flask_login import current_user, login_required
from app import db
from app.models import (User, Project, Milestone, Contribution, ProjectApplication,
                       ProjectMember, Notification, Skill, Department, Course)
import jwt

api_bp = Blueprint('api', __name__)


def token_required(f):
    """Decorator for JWT token authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Check for token in header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            data = jwt.decode(
                token, 
                current_app.config['JWT_SECRET_KEY'],
                algorithms=['HS256']
            )
            current_api_user = User.query.get(data['user_id'])
            if not current_api_user:
                return jsonify({'error': 'User not found'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(current_api_user, *args, **kwargs)
    return decorated


# Authentication endpoints
@api_bp.route('/auth/login', methods=['POST'])
def api_login():
    """Authenticate user and return JWT token."""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    email = data.get('email', '').lower()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    
    user = User.query.filter_by(email=email).first()
    
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Account is deactivated'}), 403
    
    if not user.is_verified:
        return jsonify({'error': 'Email not verified'}), 403
    
    # Generate JWT token
    token = jwt.encode({
        'user_id': user.id,
        'email': user.email,
        'exp': datetime.now(timezone.utc) + current_app.config['JWT_ACCESS_TOKEN_EXPIRES']
    }, current_app.config['JWT_SECRET_KEY'], algorithm='HS256')
    
    # Update last login
    user.last_login = datetime.now(timezone.utc)
    db.session.commit()
    
    return jsonify({
        'token': token,
        'user': {
            'id': user.id,
            'email': user.email,
            'name': user.full_name,
            'roles': [r.name for r in user.roles]
        }
    })


@api_bp.route('/auth/me', methods=['GET'])
@token_required
def get_current_user(current_api_user):
    """Get current user info."""
    return jsonify({
        'id': current_api_user.id,
        'email': current_api_user.email,
        'name': current_api_user.full_name,
        'first_name': current_api_user.first_name,
        'last_name': current_api_user.last_name,
        'department': current_api_user.department.name if current_api_user.department else None,
        'roles': [r.name for r in current_api_user.roles],
        'skills': [s.name for s in current_api_user.skills],
        'created_at': current_api_user.created_at.isoformat()
    })


# Project endpoints
@api_bp.route('/projects', methods=['GET'])
def list_projects():
    """List all public projects."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 10, type=int), 100)
    
    query = Project.query.filter(
        Project.status.in_(['open', 'in_progress']),
        Project.visibility == 'public'
    )
    
    # Search
    search = request.args.get('search', '')
    if search:
        query = query.filter(
            (Project.title.ilike(f'%{search}%')) |
            (Project.description.ilike(f'%{search}%'))
        )
    
    # Filter by department
    department_id = request.args.get('department_id', type=int)
    if department_id:
        query = query.filter_by(department_id=department_id)
    
    # Filter by skills
    skill_id = request.args.get('skill_id', type=int)
    if skill_id:
        query = query.filter(Project.skills.any(Skill.id == skill_id))
    
    # Sorting
    sort = request.args.get('sort', 'newest')
    if sort == 'newest':
        query = query.order_by(Project.created_at.desc())
    elif sort == 'oldest':
        query = query.order_by(Project.created_at.asc())
    elif sort == 'title':
        query = query.order_by(Project.title)
    
    projects = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'projects': [{
            'id': p.id,
            'title': p.title,
            'description': p.description[:200] + '...' if len(p.description) > 200 else p.description,
            'status': p.status,
            'owner': p.owner.full_name,
            'department': p.get_department().name if p.get_department() else None,
            'skills': [s.name for s in p.skills],
            'tools': [t.name for t in p.tools],
            'team_count': p.team_count,
            'max_team_size': p.max_team_size,
            'progress': p.progress,
            'application_deadline': p.application_deadline.isoformat() if p.application_deadline else None,
            'created_at': p.created_at.isoformat()
        } for p in projects.items],
        'pagination': {
            'page': projects.page,
            'per_page': projects.per_page,
            'total': projects.total,
            'pages': projects.pages,
            'has_next': projects.has_next,
            'has_prev': projects.has_prev
        }
    })


@api_bp.route('/projects/<int:project_id>', methods=['GET'])
def get_project(project_id):
    """Get project details."""
    project = Project.query.get_or_404(project_id)
    
    if project.visibility == 'private':
        return jsonify({'error': 'Project not found'}), 404
    
    return jsonify({
        'id': project.id,
        'title': project.title,
        'description': project.description,
        'goals': project.goals,
        'expected_outcomes': project.expected_outcomes,
        'status': project.status,
        'visibility': project.visibility,
        'owner': {
            'id': project.owner.id,
            'name': project.owner.full_name
        },
        'department': project.get_department().name if project.get_department() else None,
        'course': project.course.name if project.course else None,
        'skills': [s.name for s in project.skills],
        'tools': [t.name for t in project.tools],
        'team_count': project.team_count,
        'max_team_size': project.max_team_size,
        'min_team_size': project.min_team_size,
        'progress': project.progress,
        'milestones': [{
            'id': m.id,
            'title': m.title,
            'status': m.status,
            'due_date': m.due_date.isoformat()
        } for m in project.milestones],
        'start_date': project.start_date.isoformat() if project.start_date else None,
        'end_date': project.end_date.isoformat() if project.end_date else None,
        'application_deadline': project.application_deadline.isoformat() if project.application_deadline else None,
        'is_accepting_applications': project.is_accepting_applications,
        'created_at': project.created_at.isoformat(),
        'updated_at': project.updated_at.isoformat()
    })


@api_bp.route('/projects', methods=['POST'])
@token_required
def create_project(current_api_user):
    """Create a new project."""
    if not current_api_user.is_lecturer:
        return jsonify({'error': 'Only lecturers can create projects'}), 403
    
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    required_fields = ['title', 'description']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400
    
    project = Project(
        title=data['title'],
        description=data['description'],
        goals=data.get('goals'),
        expected_outcomes=data.get('expected_outcomes'),
        status=data.get('status', 'draft'),
        visibility=data.get('visibility', 'public'),
        max_team_size=data.get('max_team_size', 5),
        min_team_size=data.get('min_team_size', 1),
        owner_id=current_api_user.id,
        department_id=data.get('department_id') or current_api_user.department_id
    )
    
    # Add skills
    if 'skills' in data:
        for skill_name in data['skills']:
            skill = Skill.query.filter_by(name=skill_name).first()
            if not skill:
                skill = Skill(name=skill_name)
                db.session.add(skill)
            project.skills.append(skill)
    
    db.session.add(project)
    db.session.commit()
    
    return jsonify({
        'id': project.id,
        'message': 'Project created successfully'
    }), 201


@api_bp.route('/projects/<int:project_id>/apply', methods=['POST'])
@token_required
def apply_to_project(current_api_user, project_id):
    """Apply to join a project."""
    project = Project.query.get_or_404(project_id)
    
    if not project.is_accepting_applications:
        return jsonify({'error': 'Project is not accepting applications'}), 400
    
    # Check existing application
    existing = ProjectApplication.query.filter_by(
        project_id=project_id,
        user_id=current_api_user.id
    ).filter(ProjectApplication.status.in_(['pending', 'approved'])).first()
    
    if existing:
        return jsonify({'error': 'You have already applied to this project'}), 400
    
    data = request.get_json() or {}
    
    application = ProjectApplication(
        project_id=project_id,
        user_id=current_api_user.id,
        message=data.get('message', '')
    )
    db.session.add(application)
    db.session.commit()
    
    return jsonify({
        'id': application.id,
        'message': 'Application submitted successfully'
    }), 201


# Milestone endpoints
@api_bp.route('/projects/<int:project_id>/milestones', methods=['GET'])
@token_required
def get_milestones(current_api_user, project_id):
    """Get project milestones."""
    project = Project.query.get_or_404(project_id)
    
    # Check access
    is_member = ProjectMember.query.filter_by(
        project_id=project_id,
        user_id=current_api_user.id,
        status='active'
    ).first() is not None
    
    is_owner = project.owner_id == current_api_user.id
    
    if not is_member and not is_owner:
        return jsonify({'error': 'Access denied'}), 403
    
    milestones = project.milestones.order_by(Milestone.due_date).all()
    
    return jsonify({
        'milestones': [{
            'id': m.id,
            'title': m.title,
            'description': m.description,
            'status': m.status,
            'priority': m.priority,
            'due_date': m.due_date.isoformat(),
            'completed_at': m.completed_at.isoformat() if m.completed_at else None,
            'assigned_to': m.assigned_to.full_name if m.assigned_to else None,
            'is_overdue': m.is_overdue
        } for m in milestones],
        'progress': project.progress
    })


@api_bp.route('/projects/<int:project_id>/milestones/<int:milestone_id>/status', methods=['PUT'])
@token_required
def update_milestone_status(current_api_user, project_id, milestone_id):
    """Update milestone status."""
    project = Project.query.get_or_404(project_id)
    milestone = Milestone.query.get_or_404(milestone_id)
    
    if milestone.project_id != project_id:
        return jsonify({'error': 'Invalid milestone'}), 400
    
    # Check access
    is_member = ProjectMember.query.filter_by(
        project_id=project_id,
        user_id=current_api_user.id,
        status='active'
    ).first() is not None
    
    is_owner = project.owner_id == current_api_user.id
    
    if not is_member and not is_owner:
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json()
    if not data or 'status' not in data:
        return jsonify({'error': 'Status is required'}), 400
    
    new_status = data['status']
    if new_status not in ['pending', 'in_progress', 'completed']:
        return jsonify({'error': 'Invalid status'}), 400
    
    milestone.status = new_status
    if new_status == 'completed':
        milestone.completed_at = datetime.now(timezone.utc)
    
    db.session.commit()
    
    return jsonify({
        'message': 'Milestone status updated',
        'status': milestone.status
    })


# Contribution endpoints
@api_bp.route('/projects/<int:project_id>/contributions', methods=['GET'])
@token_required
def get_contributions(current_api_user, project_id):
    """Get project contributions."""
    project = Project.query.get_or_404(project_id)
    
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    contributions = Contribution.query.filter_by(project_id=project_id)\
        .order_by(Contribution.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'contributions': [{
            'id': c.id,
            'user': c.contributor.full_name,
            'description': c.description,
            'type': c.contribution_type,
            'hours': c.hours_spent,
            'date': c.date.isoformat(),
            'milestone': c.milestone.title if c.milestone else None,
            'created_at': c.created_at.isoformat()
        } for c in contributions.items],
        'pagination': {
            'page': contributions.page,
            'total': contributions.total,
            'pages': contributions.pages
        }
    })


@api_bp.route('/projects/<int:project_id>/contributions', methods=['POST'])
@token_required
def add_contribution(current_api_user, project_id):
    """Add a contribution."""
    project = Project.query.get_or_404(project_id)
    
    # Check membership
    is_member = ProjectMember.query.filter_by(
        project_id=project_id,
        user_id=current_api_user.id,
        status='active'
    ).first() is not None
    
    if not is_member:
        return jsonify({'error': 'You are not a member of this project'}), 403
    
    data = request.get_json()
    if not data or 'description' not in data:
        return jsonify({'error': 'Description is required'}), 400
    
    contribution = Contribution(
        project_id=project_id,
        user_id=current_api_user.id,
        description=data['description'],
        contribution_type=data.get('type'),
        hours_spent=data.get('hours'),
        milestone_id=data.get('milestone_id')
    )
    db.session.add(contribution)
    db.session.commit()
    
    return jsonify({
        'id': contribution.id,
        'message': 'Contribution logged successfully'
    }), 201


# Reference data endpoints
@api_bp.route('/departments', methods=['GET'])
def list_departments():
    """List all departments."""
    departments = Department.query.order_by(Department.name).all()
    return jsonify({
        'departments': [{
            'id': d.id,
            'name': d.name,
            'code': d.code
        } for d in departments]
    })


@api_bp.route('/courses', methods=['GET'])
def list_courses():
    """List all courses."""
    department_id = request.args.get('department_id', type=int)
    
    query = Course.query
    if department_id:
        query = query.filter_by(department_id=department_id)
    
    courses = query.order_by(Course.code).all()
    return jsonify({
        'courses': [{
            'id': c.id,
            'name': c.name,
            'code': c.code,
            'department': c.department.name if c.department else None
        } for c in courses]
    })


@api_bp.route('/skills', methods=['GET'])
def list_skills():
    """List all skills."""
    skills = Skill.query.order_by(Skill.name).all()
    return jsonify({
        'skills': [{
            'id': s.id,
            'name': s.name,
            'category': s.category
        } for s in skills]
    })


# Notification endpoints
@api_bp.route('/notifications', methods=['GET'])
@token_required
def get_notifications(current_api_user):
    """Get user notifications."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    
    query = Notification.query.filter_by(user_id=current_api_user.id)
    
    if unread_only:
        query = query.filter_by(is_read=False)
    
    notifications = query.order_by(Notification.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    unread_count = Notification.query.filter_by(
        user_id=current_api_user.id,
        is_read=False
    ).count()
    
    return jsonify({
        'notifications': [{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'type': n.notification_type,
            'is_read': n.is_read,
            'action_url': n.action_url,
            'created_at': n.created_at.isoformat()
        } for n in notifications.items],
        'unread_count': unread_count,
        'pagination': {
            'page': notifications.page,
            'total': notifications.total,
            'pages': notifications.pages
        }
    })


@api_bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@token_required
def mark_notification_read(current_api_user, notification_id):
    """Mark notification as read."""
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.user_id != current_api_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    notification.mark_as_read()
    
    return jsonify({'message': 'Notification marked as read'})

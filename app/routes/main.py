"""Main routes for public pages."""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user
from app.models import Project, Department

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Landing page."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    # Get featured projects for landing page
    featured_projects = Project.query.filter_by(
        status='open',
        visibility='public'
    ).order_by(Project.created_at.desc()).limit(6).all()
    
    # Get department stats
    departments = Department.query.all()
    
    return render_template('main/index.html', 
                         featured_projects=featured_projects,
                         departments=departments)


@main_bp.route('/about')
def about():
    """About page."""
    return render_template('main/about.html')


@main_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    """Contact page."""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')
        
        # Here you could send an email or save to database
        # For now, just show a success message
        flash(f'Thank you {name}! Your message has been received. We will get back to you soon.', 'success')
        return redirect(url_for('main.contact'))
    
    return render_template('main/contact.html')


@main_bp.route('/faq')
def faq():
    """FAQ page."""
    return render_template('main/faq.html')


@main_bp.route('/terms')
def terms():
    """Terms of service."""
    return render_template('main/terms.html')


@main_bp.route('/privacy')
def privacy():
    """Privacy policy."""
    return render_template('main/privacy.html')

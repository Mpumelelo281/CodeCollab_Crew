"""Authentication routes."""
from datetime import datetime, timezone
import re
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app import db, bcrypt
from app.models import User, Role, Department, AuditLog
from app.forms import LoginForm, RegistrationForm, ForgotPasswordForm, ResetPasswordForm, ChangePasswordForm
from app.utils.email import send_password_reset_email, send_verification_email
from app.utils.security import validate_password_strength
import secrets

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact an administrator.', 'danger')
                return render_template('auth/login.html', form=form)
            
            if not user.is_verified:
                flash('Please verify your email address before logging in.', 'warning')
                return render_template('auth/login.html', form=form)
            
            # Update last login
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()
            
            # Log the user in
            login_user(user, remember=form.remember_me.data)
            
            # Audit log
            AuditLog.log('login', user_id=user.id, request=request)
            
            # Redirect to next page or dashboard
            next_page = request.args.get('next')
            if next_page and not next_page.startswith('/'):
                next_page = None
            
            flash(f'Welcome back, {user.first_name}!', 'success')
            return redirect(next_page or url_for('dashboard.index'))
        else:
            flash('Invalid email or password.', 'danger')
            AuditLog.log('failed_login', details=f'Email: {form.email.data}', request=request)
    
    return render_template('auth/login.html', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = RegistrationForm()
    
    # Populate department choices
    departments = Department.query.order_by(Department.name).all()
    form.department.choices = [(0, 'Select Department')] + [(d.id, d.name) for d in departments]
    
    if form.validate_on_submit():
        # Validate password strength
        is_valid, message = validate_password_strength(form.password.data)
        if not is_valid:
            flash(message, 'danger')
            return render_template('auth/register.html', form=form)
        
        # Check if email domain is institutional
        email = form.email.data.lower()
        if not (email.endswith('.co.za') or email.endswith('.ac.za')):
            flash('Please use your institutional email address (ending with .co.za or .ac.za).', 'danger')
            return render_template('auth/register.html', form=form)
        
        # Check if user already exists
        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'danger')
            return render_template('auth/register.html', form=form)
        
        # Create new user
        user = User(
            email=email,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            department_id=form.department.data if form.department.data != 0 else None,
            is_verified=False
        )
        user.set_password(form.password.data)
        
        # Set student or faculty ID based on role. If the user left the ID blank
        # attempt to extract the first sequence of digits from the email local-part.
        provided_id = (form.institution_id.data or '').strip()
        if not provided_id:
            local = email.split('@')[0]
            m = re.search(r"(\d+)", local)
            provided_id = m.group(1) if m else ''

        if form.role.data == 'student':
            user.student_id = provided_id
            student_role = Role.query.filter_by(name='student').first()
            if student_role:
                user.roles.append(student_role)
        else:
            user.employee_id = provided_id
            lecturer_role = Role.query.filter_by(name='lecturer').first()
            if lecturer_role:
                user.roles.append(lecturer_role)
        
        db.session.add(user)
        db.session.commit()
        
        # Attempt to send verification email. If mail is not configured in development,
        # auto-verify the account so registration flow remains smooth.
        try:
            if not current_app.config.get('MAIL_USERNAME'):
                # Mail not configured — auto-verify in dev
                user.is_verified = True
                db.session.commit()
                flash('Registration successful! Email sending is not configured; your account has been verified automatically.', 'success')
            else:
                send_verification_email(user)
                flash('Registration successful! A verification email has been sent — please check your inbox.', 'success')
        except Exception as e:
            current_app.logger.error(f'Error sending verification email: {e}')
            flash('Registration successful, but we could not send a verification email. Please contact support.', 'warning')

        AuditLog.log('registration', user_id=user.id, request=request)
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    """Handle user logout."""
    AuditLog.log('logout', user_id=current_user.id, request=request)
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))


@auth_bp.route('/verify/<token>')
def verify_email(token):
    """Verify user email with token."""
    from app.utils.security import verify_token
    
    user_id = verify_token(token, 'email-verify')
    if not user_id:
        flash('Invalid or expired verification link.', 'danger')
        return redirect(url_for('auth.login'))
    
    user = User.query.get(user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('auth.login'))
    
    if user.is_verified:
        flash('Your email is already verified.', 'info')
        return redirect(url_for('auth.login'))
    
    user.is_verified = True
    db.session.commit()
    
    flash('Your email has been verified! You can now log in.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/resend-verification', methods=['GET', 'POST'])
def resend_verification():
    """Resend verification email."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').lower()
        user = User.query.filter_by(email=email).first()
        
        if user and not user.is_verified:
            try:
                send_verification_email(user)
                flash('Verification email sent! Please check your inbox.', 'success')
            except Exception as e:
                current_app.logger.error(f'Failed to send verification email: {e}')
                flash('Failed to send verification email. Please try again later.', 'danger')
        else:
            # Don't reveal if user exists
            flash('If an account with that email exists and is not verified, a verification email has been sent.', 'info')
        
        return redirect(url_for('auth.login'))
    
    return render_template('auth/resend_verification.html')


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Handle forgot password request."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        
        # Always show success message to prevent email enumeration
        flash('If an account with that email exists, a password reset link has been sent.', 'info')
        
        if user and user.is_verified:
            try:
                send_password_reset_email(user)
            except Exception as e:
                current_app.logger.error(f'Failed to send password reset email: {e}')
        
        return redirect(url_for('auth.login'))
    
    return render_template('auth/forgot_password.html', form=form)


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Handle password reset with token."""
    from app.utils.security import verify_token
    
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    user_id = verify_token(token, 'password-reset')
    if not user_id:
        flash('Invalid or expired reset link.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    
    user = User.query.get(user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        is_valid, message = validate_password_strength(form.password.data)
        if not is_valid:
            flash(message, 'danger')
            return render_template('auth/reset_password.html', form=form)
        
        user.set_password(form.password.data)
        db.session.commit()
        
        AuditLog.log('password_reset', user_id=user.id, request=request)
        flash('Your password has been reset! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html', form=form)


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Handle password change for logged-in user."""
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'danger')
            return render_template('auth/change_password.html', form=form)
        
        is_valid, message = validate_password_strength(form.new_password.data)
        if not is_valid:
            flash(message, 'danger')
            return render_template('auth/change_password.html', form=form)
        
        current_user.set_password(form.new_password.data)
        db.session.commit()
        
        AuditLog.log('password_change', user_id=current_user.id, request=request)
        flash('Your password has been changed successfully!', 'success')
        return redirect(url_for('dashboard.profile'))
    
    return render_template('auth/change_password.html', form=form)


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile page."""
    return redirect(url_for('dashboard.profile'))

"""Email utilities."""
from flask import current_app, render_template, url_for
from flask_mail import Message
from app import mail
from app.utils.security import generate_token
from threading import Thread


def normalize_recipient_email(email):
    """Normalize known recipient domain typos before sending."""
    normalized = (email or '').strip().lower()
    if normalized.endswith('@dut4life.co.za'):
        return normalized.replace('@dut4life.co.za', '@dut4life.ac.za')
    return normalized


def build_app_url(endpoint, **values):
    """Build an absolute URL for email links using APP_BASE_URL when configured."""
    base_url = (current_app.config.get('APP_BASE_URL') or '').strip().rstrip('/')
    path = url_for(endpoint, _external=False, **values)
    if base_url:
        return f'{base_url}{path}'
    return url_for(endpoint, _external=True, **values)


def send_async_email(app, msg):
    """Send email asynchronously."""
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            app.logger.error(f'Failed to send email: {e}')


def send_email(subject, recipients, text_body=None, html_body=None, sender=None):
    """
    Send an email.
    
    Args:
        subject: Email subject
        recipients: List of recipient email addresses
        text_body: Plain text email body
        html_body: HTML email body
        sender: Sender email (defaults to config value)
    """
    if sender is None:
        sender = current_app.config.get('MAIL_DEFAULT_SENDER')

    normalized_recipients = []
    for recipient in recipients or []:
        cleaned = normalize_recipient_email(recipient)
        if cleaned:
            normalized_recipients.append(cleaned)

    # Remove duplicates while preserving order.
    normalized_recipients = list(dict.fromkeys(normalized_recipients))
    if not normalized_recipients:
        raise ValueError('No valid recipients were provided for email sending.')
    
    msg = Message(subject=subject, sender=sender, recipients=normalized_recipients)
    
    if text_body:
        msg.body = text_body
    if html_body:
        msg.html = html_body
    
    # Send asynchronously in production
    if current_app.config.get('MAIL_ASYNC', True):
        Thread(
            target=send_async_email,
            args=(current_app._get_current_object(), msg)
        ).start()
    else:
        mail.send(msg)


def send_verification_email(user):
    """Send email verification link to user."""
    token = generate_token(user.id, 'email-verify', expiration=86400)  # 24 hours
    verify_url = build_app_url('auth.verify_email', token=token)
    
    subject = 'Verify Your Email - ColabPlatform'
    # Use templates so the content is editable in the project templates folder.
    text_body = render_template('emails/verification_email.txt', user=user, verify_url=verify_url)
    html_body = render_template('emails/verification_email.html', user=user, verify_url=verify_url)

    # Use configured sender to avoid mismatches rejected by SMTP providers.
    sender = current_app.config.get('MAIL_DEFAULT_SENDER')

    send_email(subject, [user.email], text_body, html_body, sender=sender)


def send_password_reset_email(user):
    """Send password reset link to user."""
    token = generate_token(user.id, 'password-reset', expiration=3600)  # 1 hour
    reset_url = build_app_url('auth.reset_password', token=token)
    
    subject = 'Reset Your Password - ColabPlatform'
    
    text_body = f"""
Hello {user.first_name},

You requested to reset your password. Click the link below to set a new password:

{reset_url}

This link will expire in 1 hour.

If you did not request a password reset, please ignore this email.

Best regards,
The ColabPlatform Team
"""
    
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .button {{ display: inline-block; padding: 12px 24px; background-color: #4f46e5; color: white; text-decoration: none; border-radius: 6px; }}
        .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Password Reset Request</h2>
        <p>Hello {user.first_name},</p>
        <p>You requested to reset your password. Click the button below to set a new password:</p>
        <p><a href="{reset_url}" class="button">Reset Password</a></p>
        <p>Or copy and paste this link into your browser:</p>
        <p><a href="{reset_url}">{reset_url}</a></p>
        <p>This link will expire in 1 hour.</p>
        <div class="footer">
            <p>If you did not request a password reset, please ignore this email.</p>
            <p>Best regards,<br>The ColabPlatform Team</p>
        </div>
    </div>
</body>
</html>
"""
    
    send_email(subject, [user.email], text_body, html_body)


def send_notification_email(user, notification):
    """Send email notification for important events."""
    subject = f'{notification.title} - ColabPlatform'
    
    action_link = notification.action_url if notification.action_url else build_app_url('dashboard.index')
    
    text_body = f"""
Hello {user.first_name},

{notification.message}

Click here to view more details: {action_link}

Best regards,
The ColabPlatform Team
"""
    
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .button {{ display: inline-block; padding: 12px 24px; background-color: #4f46e5; color: white; text-decoration: none; border-radius: 6px; }}
        .notification {{ background-color: #f8fafc; border-left: 4px solid #4f46e5; padding: 15px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>{notification.title}</h2>
        <p>Hello {user.first_name},</p>
        <div class="notification">
            <p>{notification.message}</p>
        </div>
        <p><a href="{action_link}" class="button">View Details</a></p>
        <p style="margin-top: 30px; font-size: 12px; color: #666;">
            Best regards,<br>The ColabPlatform Team
        </p>
    </div>
</body>
</html>
"""
    
    send_email(subject, [user.email], text_body, html_body)


def send_deadline_reminder(user, milestone, project):
    """Send reminder email for upcoming deadline."""
    subject = f'Deadline Reminder: {milestone.title} - ColabPlatform'
    
    project_url = build_app_url('projects.view_milestones', project_id=project.id)
    
    text_body = f"""
Hello {user.first_name},

This is a reminder that the following milestone is due soon:

Project: {project.title}
Milestone: {milestone.title}
Due Date: {milestone.due_date.strftime('%B %d, %Y at %H:%M')}

Click here to view the project: {project_url}

Best regards,
The ColabPlatform Team
"""
    
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .button {{ display: inline-block; padding: 12px 24px; background-color: #4f46e5; color: white; text-decoration: none; border-radius: 6px; }}
        .deadline-box {{ background-color: #fef3c7; border: 1px solid #f59e0b; border-radius: 6px; padding: 15px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Deadline Reminder</h2>
        <p>Hello {user.first_name},</p>
        <p>This is a reminder that the following milestone is due soon:</p>
        <div class="deadline-box">
            <p><strong>Project:</strong> {project.title}</p>
            <p><strong>Milestone:</strong> {milestone.title}</p>
            <p><strong>Due Date:</strong> {milestone.due_date.strftime('%B %d, %Y at %H:%M')}</p>
        </div>
        <p><a href="{project_url}" class="button">View Project</a></p>
        <p style="margin-top: 30px; font-size: 12px; color: #666;">
            Best regards,<br>The ColabPlatform Team
        </p>
    </div>
</body>
</html>
"""
    
    send_email(subject, [user.email], text_body, html_body)

"""Notification utilities."""
from app import db
from app.models import Notification, User


def send_notification(user_id, title, message, notification_type='system', 
                     action_url=None, project_id=None, sender_id=None,
                     send_email=False):
    """
    Create and send a notification to a user.
    
    Args:
        user_id: ID of the user to notify
        title: Notification title
        message: Notification message
        notification_type: Type of notification (application, deadline, update, feedback, system)
        action_url: URL to link to from the notification
        project_id: Related project ID (optional)
        sender_id: ID of the user who triggered the notification (optional)
        send_email: Whether to also send an email notification
    
    Returns:
        The created Notification object
    """
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        action_url=action_url,
        project_id=project_id,
        sender_id=sender_id
    )
    
    db.session.add(notification)
    db.session.commit()
    
    # Send email notification if requested
    if send_email:
        user = User.query.get(user_id)
        if user:
            from app.utils.email import send_notification_email
            try:
                send_notification_email(user, notification)
            except Exception as e:
                # Log error but don't fail the notification
                from flask import current_app
                current_app.logger.error(f'Failed to send notification email: {e}')
    
    return notification


def notify_project_members(project, title, message, notification_type='update',
                          action_url=None, exclude_user_id=None, send_email=False):
    """
    Send notification to all active project members.
    
    Args:
        project: Project object
        title: Notification title
        message: Notification message
        notification_type: Type of notification
        action_url: URL to link to
        exclude_user_id: User ID to exclude (usually the sender)
        send_email: Whether to also send email notifications
    
    Returns:
        List of created Notification objects
    """
    from app.models import ProjectMember
    
    notifications = []
    members = ProjectMember.query.filter_by(
        project_id=project.id,
        status='active'
    ).all()
    
    for member in members:
        if exclude_user_id and member.user_id == exclude_user_id:
            continue
        
        notification = send_notification(
            user_id=member.user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            action_url=action_url,
            project_id=project.id,
            sender_id=exclude_user_id,
            send_email=send_email
        )
        notifications.append(notification)
    
    return notifications


def send_deadline_notifications():
    """
    Send notifications for upcoming deadlines.
    This should be run as a scheduled task.
    """
    from datetime import datetime, timezone, timedelta
    from flask import url_for
    from app.models import Milestone, ProjectMember
    
    # Find milestones due in the next 24 hours
    now = datetime.now(timezone.utc)
    tomorrow = now + timedelta(days=1)
    
    upcoming_milestones = Milestone.query.filter(
        Milestone.status != 'completed',
        Milestone.due_date >= now,
        Milestone.due_date <= tomorrow
    ).all()
    
    for milestone in upcoming_milestones:
        # Get all project members
        members = ProjectMember.query.filter_by(
            project_id=milestone.project_id,
            status='active'
        ).all()
        
        # Create notification for each member
        for member in members:
            # Check if we already sent a reminder today
            existing = Notification.query.filter(
                Notification.user_id == member.user_id,
                Notification.notification_type == 'deadline',
                Notification.message.contains(milestone.title),
                Notification.created_at >= now.replace(hour=0, minute=0, second=0)
            ).first()
            
            if existing:
                continue
            
            hours_until = (milestone.due_date - now).total_seconds() / 3600
            
            send_notification(
                user_id=member.user_id,
                title='Deadline Reminder',
                message=f'Milestone "{milestone.title}" is due in {int(hours_until)} hours.',
                notification_type='deadline',
                action_url=url_for('projects.view_milestones', 
                                  project_id=milestone.project_id),
                project_id=milestone.project_id,
                send_email=True
            )


def send_overdue_notifications():
    """
    Send notifications for overdue milestones.
    This should be run as a scheduled task.
    """
    from datetime import datetime, timezone
    from flask import url_for
    from app.models import Milestone, ProjectMember, Project
    
    now = datetime.now(timezone.utc)
    
    # Find overdue milestones
    overdue_milestones = Milestone.query.filter(
        Milestone.status != 'completed',
        Milestone.due_date < now
    ).all()
    
    for milestone in overdue_milestones:
        project = Project.query.get(milestone.project_id)
        
        # Notify project owner
        send_notification(
            user_id=project.owner_id,
            title='Overdue Milestone',
            message=f'Milestone "{milestone.title}" in project "{project.title}" is overdue.',
            notification_type='deadline',
            action_url=url_for('projects.view_milestones', 
                              project_id=milestone.project_id),
            project_id=milestone.project_id,
            send_email=True
        )
        
        # Update milestone status
        milestone.status = 'overdue'
        db.session.commit()


def mark_notifications_read(user_id, notification_ids):
    """
    Mark multiple notifications as read.
    
    Args:
        user_id: ID of the user
        notification_ids: List of notification IDs to mark as read
    
    Returns:
        Number of notifications marked as read
    """
    from datetime import datetime, timezone
    
    result = Notification.query.filter(
        Notification.user_id == user_id,
        Notification.id.in_(notification_ids),
        Notification.is_read == False
    ).update({
        'is_read': True,
        'read_at': datetime.now(timezone.utc)
    }, synchronize_session=False)
    
    db.session.commit()
    return result


def delete_old_notifications(days=90):
    """
    Delete notifications older than specified days.
    This should be run as a scheduled task.
    
    Args:
        days: Number of days after which to delete read notifications
    
    Returns:
        Number of notifications deleted
    """
    from datetime import datetime, timezone, timedelta
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    result = Notification.query.filter(
        Notification.is_read == True,
        Notification.created_at < cutoff
    ).delete(synchronize_session=False)
    
    db.session.commit()
    return result

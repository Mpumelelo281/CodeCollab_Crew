"""Notification routes."""
from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Notification

notifications_bp = Blueprint('notifications', __name__)


@notifications_bp.route('/')
@login_required
def view_all():
    """View all notifications."""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Filter options
    filter_type = request.args.get('type')
    filter_read = request.args.get('read')
    
    query = Notification.query.filter_by(user_id=current_user.id)
    
    if filter_type:
        query = query.filter_by(notification_type=filter_type)
    
    if filter_read == 'unread':
        query = query.filter_by(is_read=False)
    elif filter_read == 'read':
        query = query.filter_by(is_read=True)
    
    notifications = query.order_by(Notification.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    # Get notification type counts
    type_counts = db.session.query(
        Notification.notification_type,
        db.func.count(Notification.id)
    ).filter_by(user_id=current_user.id).group_by(Notification.notification_type).all()
    
    unread_count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    
    return render_template('notifications/list.html',
                         notifications=notifications,
                         type_counts=dict(type_counts),
                         unread_count=unread_count,
                         filter_type=filter_type,
                         filter_read=filter_read)


@notifications_bp.route('/<int:notification_id>')
@login_required
def view_notification(notification_id):
    """View a single notification and mark as read."""
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.user_id != current_user.id:
        flash('You do not have permission to view this notification.', 'danger')
        return redirect(url_for('notifications.view_all'))
    
    # Mark as read
    notification.mark_as_read()
    
    # Redirect to action URL if available
    if notification.action_url:
        return redirect(notification.action_url)
    
    return render_template('notifications/view.html', notification=notification)


@notifications_bp.route('/<int:notification_id>/mark-read', methods=['POST'])
@login_required
def mark_read(notification_id):
    """Mark a notification as read."""
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.user_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403
    
    notification.mark_as_read()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    
    flash('Notification marked as read.', 'info')
    return redirect(url_for('notifications.view_all'))


@notifications_bp.route('/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    """Mark all notifications as read."""
    Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).update({
        'is_read': True,
        'read_at': datetime.now(timezone.utc)
    })
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('notifications.view_all'))


@notifications_bp.route('/<int:notification_id>/delete', methods=['POST'])
@login_required
def delete_notification(notification_id):
    """Delete a notification."""
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.user_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403
    
    db.session.delete(notification)
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    
    flash('Notification deleted.', 'info')
    return redirect(url_for('notifications.view_all'))


@notifications_bp.route('/delete-all', methods=['POST'])
@login_required
def delete_all():
    """Delete all notifications."""
    Notification.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    
    flash('All notifications deleted.', 'success')
    return redirect(url_for('notifications.view_all'))


# API endpoints for real-time notification updates
@notifications_bp.route('/api/unread-count')
@login_required
def unread_count():
    """Get unread notification count."""
    count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    
    return jsonify({'count': count})


@notifications_bp.route('/api/recent')
@login_required
def recent_notifications():
    """Get recent notifications for dropdown."""
    notifications = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc()).limit(5).all()
    
    return jsonify({
        'notifications': [{
            'id': n.id,
            'title': n.title,
            'message': n.message[:100] + '...' if len(n.message) > 100 else n.message,
            'type': n.notification_type,
            'is_read': n.is_read,
            'action_url': n.action_url,
            'created_at': n.created_at.isoformat()
        } for n in notifications],
        'unread_count': current_user.get_unread_notifications_count()
    })


@notifications_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Notification settings."""
    # In a full implementation, this would manage email preferences,
    # notification types to receive, etc.
    
    if request.method == 'POST':
        # Save notification preferences
        flash('Notification settings updated.', 'success')
        return redirect(url_for('notifications.settings'))
    
    return render_template('notifications/settings.html')

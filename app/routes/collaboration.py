"""Collaboration routes for project teamwork."""
from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import (Project, ProjectMember, Contribution, ProjectUpdate, 
                       Milestone, MilestoneSubmission, Feedback, SubmissionFile)
from app.forms import ContributionForm, ProjectUpdateForm, SubmissionForm, FeedbackForm
from app.utils.decorators import project_member_required, project_owner_required
from app.utils.notifications import send_notification
from werkzeug.utils import secure_filename
import os
import uuid
from flask import current_app

collab_bp = Blueprint('collaboration', __name__)


@collab_bp.route('/project/<int:project_id>')
@login_required
@project_member_required
def project_workspace(project_id):
    """Main collaboration workspace for a project."""
    project = Project.query.get_or_404(project_id)
    
    # Get recent activity
    recent_contributions = Contribution.query.filter_by(project_id=project_id)\
        .order_by(Contribution.created_at.desc()).limit(10).all()
    recent_updates = project.updates.limit(5).all()
    
    # Get upcoming milestones
    upcoming_milestones = Milestone.query.filter_by(project_id=project_id)\
        .filter(Milestone.status != 'completed')\
        .order_by(Milestone.due_date).limit(5).all()
    
    # Get team members with their contribution stats
    members = ProjectMember.query.filter_by(project_id=project_id, status='active').all()
    member_stats = []
    for member in members:
        contribution_count = Contribution.query.filter_by(
            project_id=project_id,
            user_id=member.user_id
        ).count()
        total_hours = db.session.query(db.func.sum(Contribution.hours_spent))\
            .filter_by(project_id=project_id, user_id=member.user_id).scalar() or 0
        member_stats.append({
            'member': member,
            'contributions': contribution_count,
            'hours': total_hours
        })
    
    return render_template('collaboration/workspace.html',
                         project=project,
                         recent_contributions=recent_contributions,
                         recent_updates=recent_updates,
                         upcoming_milestones=upcoming_milestones,
                         member_stats=member_stats)


@collab_bp.route('/project/<int:project_id>/contributions')
@login_required
@project_member_required
def contributions(project_id):
    """View all project contributions."""
    project = Project.query.get_or_404(project_id)
    
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('ITEMS_PER_PAGE', 10)
    
    # Filter by user
    user_id = request.args.get('user_id', type=int)
    query = Contribution.query.filter_by(project_id=project_id)
    
    if user_id:
        query = query.filter_by(user_id=user_id)
    
    # Filter by type
    contribution_type = request.args.get('type')
    if contribution_type:
        query = query.filter_by(contribution_type=contribution_type)
    
    contributions = query.order_by(Contribution.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    # Get contribution statistics
    stats = db.session.query(
        Contribution.contribution_type,
        db.func.count(Contribution.id).label('count'),
        db.func.sum(Contribution.hours_spent).label('hours')
    ).filter_by(project_id=project_id).group_by(Contribution.contribution_type).all()
    
    # Get team members for filter
    members = ProjectMember.query.filter_by(project_id=project_id, status='active').all()
    
    return render_template('collaboration/contributions.html',
                         project=project,
                         contributions=contributions,
                         stats=stats,
                         members=members,
                         current_filters={
                             'user_id': user_id,
                             'type': contribution_type
                         })


@collab_bp.route('/project/<int:project_id>/contributions/add', methods=['GET', 'POST'])
@login_required
@project_member_required
def add_contribution(project_id):
    """Add a new contribution."""
    project = Project.query.get_or_404(project_id)
    form = ContributionForm()
    
    # Get milestones for linking (include all milestones)
    form.milestone.choices = [(0, 'No specific milestone')] + [
        (m.id, m.title) for m in project.milestones.all()
    ]
    
    if form.validate_on_submit():
        contribution = Contribution(
            project_id=project_id,
            user_id=current_user.id,
            description=form.description.data,
            contribution_type=form.contribution_type.data,
            hours_spent=form.hours_spent.data,
            date=form.date.data,
            milestone_id=form.milestone.data if form.milestone.data != 0 else None
        )
        db.session.add(contribution)
        db.session.commit()
        
        flash('Contribution logged successfully!', 'success')
        return redirect(url_for('collaboration.contributions', project_id=project_id))
    
    return render_template('collaboration/contribution_form.html',
                         form=form,
                         project=project)


@collab_bp.route('/project/<int:project_id>/updates')
@login_required
@project_member_required
def updates(project_id):
    """View project updates and announcements."""
    project = Project.query.get_or_404(project_id)
    
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('ITEMS_PER_PAGE', 10)
    
    updates = project.updates.paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('collaboration/updates.html',
                         project=project,
                         updates=updates)


@collab_bp.route('/project/<int:project_id>/updates/add', methods=['GET', 'POST'])
@login_required
@project_member_required
def add_update(project_id):
    """Add a project update."""
    project = Project.query.get_or_404(project_id)
    form = ProjectUpdateForm()
    
    if form.validate_on_submit():
        update = ProjectUpdate(
            project_id=project_id,
            author_id=current_user.id,
            title=form.title.data,
            content=form.content.data,
            update_type=form.update_type.data
        )
        db.session.add(update)
        db.session.commit()
        
        # Notify team members
        for member in project.members.filter_by(status='active'):
            if member.user_id != current_user.id:
                send_notification(
                    user_id=member.user_id,
                    title='New Project Update',
                    message=f'{current_user.full_name} posted an update in "{project.title}": {update.title}',
                    notification_type='update',
                    action_url=url_for('collaboration.updates', project_id=project_id),
                    project_id=project_id,
                    sender_id=current_user.id
                )
        
        flash('Update posted successfully!', 'success')
        return redirect(url_for('collaboration.updates', project_id=project_id))
    
    return render_template('collaboration/update_form.html',
                         form=form,
                         project=project)


@collab_bp.route('/project/<int:project_id>/milestones/<int:milestone_id>/submit', methods=['GET', 'POST'])
@login_required
@project_member_required
def submit_milestone(project_id, milestone_id):
    """Submit work for a milestone."""
    project = Project.query.get_or_404(project_id)
    milestone = Milestone.query.get_or_404(milestone_id)
    
    if milestone.project_id != project_id:
        flash('Invalid milestone.', 'danger')
        return redirect(url_for('projects.view_milestones', project_id=project_id))
    
    if milestone.status == 'completed':
        flash('This milestone is already completed.', 'info')
        return redirect(url_for('projects.view_milestones', project_id=project_id))
    
    form = SubmissionForm()
    
    if form.validate_on_submit():
        submission = MilestoneSubmission(
            milestone_id=milestone_id,
            submitted_by_id=current_user.id,
            content=form.content.data
        )
        db.session.add(submission)
        db.session.flush()  # Get submission ID
        
        # Handle file uploads
        if 'files' in request.files:
            files = request.files.getlist('files')
            for file in files:
                if file and file.filename:
                    original_filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
                    
                    upload_folder = os.path.join(
                        current_app.config['UPLOAD_FOLDER'],
                        str(project_id),
                        'submissions'
                    )
                    if not os.path.exists(upload_folder):
                        os.makedirs(upload_folder)
                    
                    file_path = os.path.join(upload_folder, unique_filename)
                    file.save(file_path)
                    file_size = os.path.getsize(file_path)
                    ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
                    
                    submission_file = SubmissionFile(
                        submission_id=submission.id,
                        filename=unique_filename,
                        original_filename=original_filename,
                        file_type=ext,
                        file_size=file_size
                    )
                    db.session.add(submission_file)
        
        db.session.commit()
        
        # Notify project owner
        send_notification(
            user_id=project.owner_id,
            title='Milestone Submission',
            message=f'{current_user.full_name} submitted work for milestone "{milestone.title}".',
            notification_type='milestone',
            action_url=url_for('collaboration.view_submission', 
                             project_id=project_id, 
                             submission_id=submission.id),
            project_id=project_id,
            sender_id=current_user.id
        )
        
        flash('Submission uploaded successfully!', 'success')
        return redirect(url_for('projects.view_milestones', project_id=project_id))
    
    return render_template('collaboration/submission_form.html',
                         form=form,
                         project=project,
                         milestone=milestone)


@collab_bp.route('/project/<int:project_id>/submissions/<int:submission_id>')
@login_required
@project_member_required
def view_submission(project_id, submission_id):
    """View a milestone submission."""
    project = Project.query.get_or_404(project_id)
    submission = MilestoneSubmission.query.get_or_404(submission_id)
    
    if submission.milestone.project_id != project_id:
        flash('Invalid submission.', 'danger')
        return redirect(url_for('projects.view_milestones', project_id=project_id))
    
    return render_template('collaboration/submission_view.html',
                         project=project,
                         submission=submission)


@collab_bp.route('/project/<int:project_id>/submissions/<int:submission_id>/review', methods=['POST'])
@login_required
@project_owner_required
def review_submission(project_id, submission_id):
    """Review a milestone submission."""
    project = Project.query.get_or_404(project_id)
    submission = MilestoneSubmission.query.get_or_404(submission_id)
    
    if submission.milestone.project_id != project_id:
        flash('Invalid submission.', 'danger')
        return redirect(url_for('projects.view_milestones', project_id=project_id))
    
    action = request.form.get('action')
    feedback = request.form.get('feedback', '')
    
    if action == 'approve':
        submission.status = 'approved'
        submission.milestone.status = 'completed'
        submission.milestone.completed_at = datetime.now(timezone.utc)
        
        notification_message = f'Your submission for "{submission.milestone.title}" has been approved!'
        notification_title = 'Submission Approved'
    elif action == 'reject':
        submission.status = 'rejected'
        notification_message = f'Your submission for "{submission.milestone.title}" needs revision.'
        notification_title = 'Submission Needs Revision'
    else:
        flash('Invalid action.', 'danger')
        return redirect(url_for('collaboration.view_submission', 
                               project_id=project_id, 
                               submission_id=submission_id))
    
    submission.feedback = feedback
    submission.reviewed_at = datetime.now(timezone.utc)
    submission.reviewed_by_id = current_user.id
    db.session.commit()
    
    # Notify submitter
    send_notification(
        user_id=submission.submitted_by_id,
        title=notification_title,
        message=notification_message,
        notification_type='feedback',
        action_url=url_for('collaboration.view_submission',
                          project_id=project_id,
                          submission_id=submission_id),
        project_id=project_id,
        sender_id=current_user.id
    )
    
    flash(f'Submission has been {action}d.', 'success')
    return redirect(url_for('projects.view_milestones', project_id=project_id))


@collab_bp.route('/project/<int:project_id>/feedback')
@login_required
@project_member_required
def view_feedback(project_id):
    """View all feedback for the project."""
    project = Project.query.get_or_404(project_id)
    
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('ITEMS_PER_PAGE', 10)
    
    feedback_list = Feedback.query.filter_by(project_id=project_id)\
        .order_by(Feedback.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('collaboration/feedback.html',
                         project=project,
                         feedback_list=feedback_list)


@collab_bp.route('/project/<int:project_id>/feedback/add', methods=['GET', 'POST'])
@login_required
@project_owner_required
def add_feedback(project_id):
    """Add feedback for project/team members."""
    project = Project.query.get_or_404(project_id)
    form = FeedbackForm()
    
    # Get team members and milestones
    members = project.members.filter_by(status='active').all()
    form.recipient.choices = [(0, 'Team (General)')] + [(m.user.id, m.user.full_name) for m in members]
    form.milestone.choices = [(0, 'No specific milestone')] + [(m.id, m.title) for m in project.milestones.all()]
    
    if form.validate_on_submit():
        feedback = Feedback(
            project_id=project_id,
            author_id=current_user.id,
            content=form.content.data,
            rating=form.rating.data if form.rating.data else None,
            feedback_type=form.feedback_type.data,
            recipient_id=form.recipient.data if form.recipient.data != 0 else None,
            milestone_id=form.milestone.data if form.milestone.data != 0 else None
        )
        db.session.add(feedback)
        db.session.commit()
        
        # Notify recipient(s)
        if feedback.recipient_id:
            send_notification(
                user_id=feedback.recipient_id,
                title='New Feedback',
                message=f'You received feedback on "{project.title}".',
                notification_type='feedback',
                action_url=url_for('collaboration.view_feedback', project_id=project_id),
                project_id=project_id,
                sender_id=current_user.id
            )
        else:
            # Notify all team members
            for member in members:
                send_notification(
                    user_id=member.user_id,
                    title='New Project Feedback',
                    message=f'New feedback posted for "{project.title}".',
                    notification_type='feedback',
                    action_url=url_for('collaboration.view_feedback', project_id=project_id),
                    project_id=project_id,
                    sender_id=current_user.id
                )
        
        flash('Feedback submitted successfully!', 'success')
        return redirect(url_for('collaboration.view_feedback', project_id=project_id))
    
    return render_template('collaboration/feedback_form.html',
                         form=form,
                         project=project)


# API endpoints for real-time updates
@collab_bp.route('/api/project/<int:project_id>/activity')
@login_required
@project_member_required
def get_recent_activity(project_id):
    """Get recent project activity for AJAX updates."""
    project = Project.query.get_or_404(project_id)
    
    # Get recent contributions
    contributions = Contribution.query.filter_by(project_id=project_id)\
        .order_by(Contribution.created_at.desc()).limit(5).all()
    
    contribution_data = [{
        'id': c.id,
        'user': c.contributor.full_name,
        'description': c.description,
        'type': c.contribution_type,
        'date': c.created_at.isoformat()
    } for c in contributions]
    
    # Get recent updates
    updates = ProjectUpdate.query.filter_by(project_id=project_id)\
        .order_by(ProjectUpdate.created_at.desc()).limit(5).all()
    
    update_data = [{
        'id': u.id,
        'title': u.title,
        'author': u.author.full_name,
        'type': u.update_type,
        'date': u.created_at.isoformat()
    } for u in updates]
    
    return jsonify({
        'contributions': contribution_data,
        'updates': update_data,
        'progress': project.progress
    })


@collab_bp.route('/api/project/<int:project_id>/contribution-stats')
@login_required
@project_member_required
def get_contribution_stats(project_id):
    """Get contribution statistics for charts."""
    # By type
    by_type = db.session.query(
        Contribution.contribution_type,
        db.func.count(Contribution.id).label('count')
    ).filter_by(project_id=project_id).group_by(Contribution.contribution_type).all()
    
    # By user
    by_user = db.session.query(
        Contribution.user_id,
        db.func.count(Contribution.id).label('count'),
        db.func.sum(Contribution.hours_spent).label('hours')
    ).filter_by(project_id=project_id).group_by(Contribution.user_id).all()
    
    user_data = []
    for user_id, count, hours in by_user:
        from app.models import User
        user = User.query.get(user_id)
        user_data.append({
            'user': user.full_name,
            'contributions': count,
            'hours': float(hours) if hours else 0
        })
    
    return jsonify({
        'by_type': [{'type': t, 'count': c} for t, c in by_type],
        'by_user': user_data
    })

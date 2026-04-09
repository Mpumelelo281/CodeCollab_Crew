"""Project management routes."""
from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import (Project, Milestone, ProjectApplication, ProjectMember, 
                       Skill, Tool, Course, Department, Notification, AuditLog, ProjectFile,
                       Task, ProjectInvitation, User, Contribution, ProjectUpdate,
                       Feedback, MilestoneSubmission, SubmissionFile, ProjectGrade, ProjectComment,
                       ProjectMessage)
from app.forms import ProjectForm, MilestoneForm, ApplicationForm, ProjectSearchForm
from app.utils.decorators import lecturer_required, project_owner_required, project_member_required
from app.utils.notifications import send_notification
from werkzeug.utils import secure_filename
import os
import uuid

projects_bp = Blueprint('projects', __name__)


@projects_bp.route('/')
def list_projects():
    """List all projects with search and filtering."""
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('ITEMS_PER_PAGE', 10)
    
    # Build query
    query = Project.query.filter(Project.status.in_(['open', 'in_progress']))
    
    # For non-authenticated users, show only public projects
    if not current_user.is_authenticated:
        query = query.filter_by(visibility='public')
    elif current_user.is_student:
        # Students see public projects and department projects
        query = query.filter(
            (Project.visibility == 'public') |
            ((Project.visibility == 'department') & 
             (Project.department_id == current_user.department_id))
        )
    
    # Search filters
    search = request.args.get('search', '')
    if search:
        query = query.filter(
            (Project.title.ilike(f'%{search}%')) |
            (Project.description.ilike(f'%{search}%'))
        )
    
    # Department filter
    department_id = request.args.get('department', type=int)
    if department_id:
        query = query.filter_by(department_id=department_id)
    
    # Course filter
    course_id = request.args.get('course', type=int)
    if course_id:
        query = query.filter_by(course_id=course_id)
    
    # Skills filter
    skill_ids = request.args.getlist('skills', type=int)
    if skill_ids:
        for skill_id in skill_ids:
            query = query.filter(Project.skills.any(Skill.id == skill_id))
    
    # Status filter
    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)
    
    # Sorting
    sort = request.args.get('sort', 'newest')
    if sort == 'newest':
        query = query.order_by(Project.created_at.desc())
    elif sort == 'oldest':
        query = query.order_by(Project.created_at.asc())
    elif sort == 'deadline':
        query = query.order_by(Project.application_deadline.asc())
    elif sort == 'title':
        query = query.order_by(Project.title.asc())
    
    # Paginate
    projects = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Get filter options
    departments = Department.query.order_by(Department.name).all()
    courses = Course.query.order_by(Course.name).all()
    skills = Skill.query.order_by(Skill.name).all()
    
    return render_template('projects/list.html',
                         projects=projects,
                         departments=departments,
                         courses=courses,
                         skills=skills,
                         current_filters={
                             'search': search,
                             'department': department_id,
                             'course': course_id,
                             'skills': skill_ids,
                             'status': status,
                             'sort': sort
                         })


@projects_bp.route('/<int:project_id>')
def view_project(project_id):
    """View project details."""
    project = Project.query.get_or_404(project_id)
    
    # Check visibility
    if project.visibility == 'private' and not current_user.is_authenticated:
        flash('You do not have permission to view this project.', 'danger')
        return redirect(url_for('projects.list_projects'))
    
    if project.visibility == 'department':
        if not current_user.is_authenticated:
            flash('Please log in to view this project.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        if current_user.department_id != project.department_id and not current_user.is_admin:
            flash('This project is only visible to members of the relevant department.', 'warning')
            return redirect(url_for('projects.list_projects'))
    
    # Check if user has already applied
    has_applied = False
    is_member = False
    user_application = None
    
    if current_user.is_authenticated:
        user_application = ProjectApplication.query.filter_by(
            project_id=project_id,
            user_id=current_user.id
        ).first()
        has_applied = user_application is not None
        
        is_member = ProjectMember.query.filter_by(
            project_id=project_id,
            user_id=current_user.id,
            status='active'
        ).first() is not None
    
    # Get project statistics
    member_count = project.members.filter_by(status='active').count()
    milestone_count = project.milestones.count()
    completed_milestones = project.milestones.filter_by(status='completed').count()
    
    # Check if user can edit the project (owner or admin)
    can_edit = False
    is_lecturer_viewer = False
    if current_user.is_authenticated:
        can_edit = (project.owner_id == current_user.id) or current_user.is_admin
        is_lecturer_viewer = (current_user.is_lecturer and 
                              current_user.department_id is not None and 
                              current_user.department_id == project.department_id)
    
    # Can apply check
    can_apply = False
    if current_user.is_authenticated and current_user.is_student:
        can_apply = project.is_accepting_applications and not has_applied and not is_member and project.owner_id != current_user.id
    
    # Get team members
    team_members = project.members.filter_by(status='active').all()
    
    # Get milestones
    milestones = project.milestones.all()
    
    # Get recent updates with author info
    updates = project.updates.limit(10).all()
    
    # Get recent contributions (who did what)
    recent_contributions = Contribution.query.filter_by(project_id=project_id)\
        .order_by(Contribution.created_at.desc()).limit(10).all()
    
    # Get project files
    project_files = project.files.filter_by(is_current=True)\
        .order_by(ProjectFile.uploaded_at.desc()).all()
    
    # Get unread message count for this user
    unread_message_count = 0
    if current_user.is_authenticated:
        unread_message_count = ProjectMessage.query.filter(
            ProjectMessage.project_id == project_id,
            ProjectMessage.sender_id != current_user.id,
            ProjectMessage.is_read == False
        ).count()
    
    return render_template('projects/view.html',
                         project=project,
                         has_applied=has_applied,
                         is_member=is_member,
                         can_edit=can_edit,
                         can_apply=can_apply,
                         is_lecturer_viewer=is_lecturer_viewer,
                         user_application=user_application,
                         member_count=member_count,
                         milestone_count=milestone_count,
                         completed_milestones=completed_milestones,
                         team_members=team_members,
                         milestones=milestones,
                         updates=updates,
                         recent_contributions=recent_contributions,
                         project_files=project_files,
                         team_count=member_count,
                         unread_message_count=unread_message_count)


@projects_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_project():
    """Create a new project. Only students can create projects."""
    if current_user.is_lecturer and not current_user.is_admin:
        flash('Only students can create projects. As a lecturer, you can view and monitor student projects.', 'info')
        return redirect(url_for('dashboard.index'))
    form = ProjectForm()
    
    # Populate choices
    form.department.choices = [(0, 'Select Department')] + [
        (d.id, d.name) for d in Department.query.order_by(Department.name).all()
    ]
    form.course.choices = [(0, 'Select Course (Optional)')] + [
        (c.id, f'{c.code} - {c.name}') for c in Course.query.order_by(Course.code).all()
    ]
    
    if form.validate_on_submit():
        project = Project(
            title=form.title.data,
            description=form.description.data,
            goals=form.goals.data,
            expected_outcomes=form.expected_outcomes.data,
            status=form.status.data,
            visibility=form.visibility.data,
            max_team_size=form.team_size.data or 0,  # 0 = unlimited
            min_team_size=1,  # Always 1
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            application_deadline=form.application_deadline.data,
            owner_id=current_user.id,
            department_id=form.department.data if form.department.data != 0 else current_user.department_id,
            course_id=form.course.data if form.course.data != 0 else None
        )
        
        # Generate invite code for sharing
        project.generate_invite_code()
        
        # Add skills
        skill_names = [s.strip() for s in form.skills.data.split(',') if s.strip()]
        for skill_name in skill_names:
            skill = Skill.query.filter_by(name=skill_name).first()
            if not skill:
                skill = Skill(name=skill_name)
                db.session.add(skill)
            project.skills.append(skill)
        
        # Add tools
        tool_names = [t.strip() for t in form.tools.data.split(',') if t.strip()]
        for tool_name in tool_names:
            tool = Tool.query.filter_by(name=tool_name).first()
            if not tool:
                tool = Tool(name=tool_name)
                db.session.add(tool)
            project.tools.append(tool)
        
        db.session.add(project)
        db.session.commit()
        
        AuditLog.log('project_created', user_id=current_user.id, 
                    entity_type='project', entity_id=project.id, request=request)
        
        flash('Project created successfully!', 'success')
        return redirect(url_for('projects.view_project', project_id=project.id))
    
    return render_template('projects/create.html', form=form)


@projects_bp.route('/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
@project_owner_required
def edit_project(project_id):
    """Edit an existing project."""
    project = Project.query.get_or_404(project_id)
    form = ProjectForm(obj=project)
    
    # Populate choices
    form.department.choices = [(0, 'Select Department')] + [
        (d.id, d.name) for d in Department.query.order_by(Department.name).all()
    ]
    form.course.choices = [(0, 'Select Course (Optional)')] + [
        (c.id, f'{c.code} - {c.name}') for c in Course.query.order_by(Course.code).all()
    ]
    
    if request.method == 'GET':
        # Pre-populate skills and tools
        form.skills.data = ', '.join([s.name for s in project.skills])
        form.tools.data = ', '.join([t.name for t in project.tools])
        form.team_size.data = project.max_team_size
    
    if form.validate_on_submit():
        project.title = form.title.data
        project.description = form.description.data
        project.goals = form.goals.data
        project.expected_outcomes = form.expected_outcomes.data
        project.status = form.status.data
        project.visibility = form.visibility.data
        project.max_team_size = form.team_size.data or 0  # 0 = unlimited
        project.min_team_size = 1  # Always 1
        project.start_date = form.start_date.data
        project.end_date = form.end_date.data
        project.application_deadline = form.application_deadline.data
        project.department_id = form.department.data if form.department.data != 0 else None
        project.course_id = form.course.data if form.course.data != 0 else None
        
        # Update skills
        project.skills.clear()
        skill_names = [s.strip() for s in form.skills.data.split(',') if s.strip()]
        for skill_name in skill_names:
            skill = Skill.query.filter_by(name=skill_name).first()
            if not skill:
                skill = Skill(name=skill_name)
                db.session.add(skill)
            project.skills.append(skill)
        
        # Update tools
        project.tools.clear()
        tool_names = [t.strip() for t in form.tools.data.split(',') if t.strip()]
        for tool_name in tool_names:
            tool = Tool.query.filter_by(name=tool_name).first()
            if not tool:
                tool = Tool(name=tool_name)
                db.session.add(tool)
            project.tools.append(tool)
        
        db.session.commit()
        
        # Notify team members about update
        for member in project.members.filter_by(status='active'):
            if member.user_id != current_user.id:
                send_notification(
                    user_id=member.user_id,
                    title='Project Updated',
                    message=f'The project "{project.title}" has been updated.',
                    notification_type='update',
                    action_url=url_for('projects.view_project', project_id=project.id),
                    project_id=project.id,
                    sender_id=current_user.id
                )
        
        AuditLog.log('project_updated', user_id=current_user.id,
                    entity_type='project', entity_id=project.id, request=request)
        
        flash('Project updated successfully!', 'success')
        return redirect(url_for('projects.view_project', project_id=project.id))
    
    return render_template('projects/edit.html', form=form, project=project)


@projects_bp.route('/<int:project_id>/delete', methods=['POST'])
@login_required
@project_owner_required
def delete_project(project_id):
    """Delete a project and all related data."""
    project = Project.query.get_or_404(project_id)
    project_title = project.title
    
    try:
        # Delete related data in proper order (respecting foreign key constraints)
        
        # Delete notifications related to project
        Notification.query.filter_by(project_id=project_id).delete()
        
        # Delete project comments
        ProjectComment.query.filter_by(project_id=project_id).delete()
        
        # Delete project grades
        ProjectGrade.query.filter_by(project_id=project_id).delete()
        
        # Delete feedback
        Feedback.query.filter_by(project_id=project_id).delete()
        
        # Delete invitations
        ProjectInvitation.query.filter_by(project_id=project_id).delete()
        
        # Delete applications
        ProjectApplication.query.filter_by(project_id=project_id).delete()
        
        # Delete members
        ProjectMember.query.filter_by(project_id=project_id).delete()
        
        # Delete project updates
        ProjectUpdate.query.filter_by(project_id=project_id).delete()
        
        # Delete files (also remove actual files from disk)
        files = ProjectFile.query.filter_by(project_id=project_id).all()
        for file in files:
            try:
                upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
                file_path = os.path.join(upload_folder, str(project_id), file.filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass  # Continue even if file deletion fails
        ProjectFile.query.filter_by(project_id=project_id).delete()
        
        # Delete contributions
        Contribution.query.filter_by(project_id=project_id).delete()
        
        # Delete tasks
        Task.query.filter_by(project_id=project_id).delete()
        
        # Delete milestone submissions and their files first
        milestones = Milestone.query.filter_by(project_id=project_id).all()
        for milestone in milestones:
            submissions = MilestoneSubmission.query.filter_by(milestone_id=milestone.id).all()
            for submission in submissions:
                SubmissionFile.query.filter_by(submission_id=submission.id).delete()
            MilestoneSubmission.query.filter_by(milestone_id=milestone.id).delete()
        
        # Delete milestones
        Milestone.query.filter_by(project_id=project_id).delete()
        
        # Log deletion
        AuditLog.log('project_deleted', user_id=current_user.id,
                    entity_type='project', entity_id=project_id, request=request,
                    details={'title': project_title})
        
        # Delete the project
        db.session.delete(project)
        db.session.commit()
        
        flash(f'Project "{project_title}" has been deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting project: {str(e)}', 'danger')
        return redirect(url_for('projects.view_project', project_id=project_id))
    
    return redirect(url_for('projects.list_projects'))


@projects_bp.route('/<int:project_id>/apply', methods=['GET', 'POST'])
@login_required
def apply_to_project(project_id):
    """Apply to join a project."""
    project = Project.query.get_or_404(project_id)
    
    # Check if project is accepting applications
    if not project.is_accepting_applications:
        flash('This project is not currently accepting applications.', 'warning')
        return redirect(url_for('projects.view_project', project_id=project_id))
    
    # Check if user has already applied
    existing_application = ProjectApplication.query.filter_by(
        project_id=project_id,
        user_id=current_user.id
    ).filter(ProjectApplication.status.in_(['pending', 'approved'])).first()
    
    if existing_application:
        flash('You have already applied to this project.', 'info')
        return redirect(url_for('projects.view_project', project_id=project_id))
    
    # Check if user is already a member
    existing_membership = ProjectMember.query.filter_by(
        project_id=project_id,
        user_id=current_user.id,
        status='active'
    ).first()
    
    if existing_membership:
        flash('You are already a member of this project.', 'info')
        return redirect(url_for('projects.view_project', project_id=project_id))
    
    form = ApplicationForm()
    
    if form.validate_on_submit():
        application = ProjectApplication(
            project_id=project_id,
            user_id=current_user.id,
            message=form.message.data
        )
        db.session.add(application)
        db.session.commit()
        
        # Notify project owner
        send_notification(
            user_id=project.owner_id,
            title='New Application',
            message=f'{current_user.full_name} has applied to join "{project.title}".',
            notification_type='application',
            action_url=url_for('projects.manage_applications', project_id=project.id),
            project_id=project.id,
            sender_id=current_user.id
        )
        
        flash('Your application has been submitted!', 'success')
        return redirect(url_for('projects.view_project', project_id=project_id))
    
    return render_template('projects/apply.html', form=form, project=project)


@projects_bp.route('/<int:project_id>/applications')
@login_required
@project_owner_required
def manage_applications(project_id):
    """Manage project applications (for project owner)."""
    project = Project.query.get_or_404(project_id)
    
    # Get applications by status
    pending = project.applications.filter_by(status='pending').all()
    approved = project.applications.filter_by(status='approved').all()
    rejected = project.applications.filter_by(status='rejected').all()
    
    return render_template('projects/applications.html',
                         project=project,
                         pending=pending,
                         approved=approved,
                         rejected=rejected)


@projects_bp.route('/<int:project_id>/applications/<int:application_id>/<action>')
@login_required
@project_owner_required
def process_application(project_id, application_id, action):
    """Process a project application (approve/reject)."""
    project = Project.query.get_or_404(project_id)
    application = ProjectApplication.query.get_or_404(application_id)
    
    if application.project_id != project_id:
        flash('Invalid application.', 'danger')
        return redirect(url_for('projects.manage_applications', project_id=project_id))
    
    if action == 'approve':
        # Check team size limit (if set)
        if project.max_team_size and project.max_team_size > 0 and project.team_count >= project.max_team_size:
            flash('Cannot approve application. Team is at maximum capacity.', 'warning')
            return redirect(url_for('projects.manage_applications', project_id=project_id))
        
        application.status = 'approved'
        application.reviewed_at = datetime.now(timezone.utc)
        application.reviewed_by_id = current_user.id
        
        # Create project membership
        member = ProjectMember(
            project_id=project_id,
            user_id=application.user_id,
            role='member'
        )
        db.session.add(member)
        
        # Notify applicant
        send_notification(
            user_id=application.user_id,
            title='Application Approved!',
            message=f'Your application to join "{project.title}" has been approved!',
            notification_type='application',
            action_url=url_for('projects.view_project', project_id=project_id),
            project_id=project_id,
            sender_id=current_user.id
        )
        
        flash(f'{application.applicant.full_name} has been added to the project!', 'success')
        
    elif action == 'reject':
        application.status = 'rejected'
        application.reviewed_at = datetime.now(timezone.utc)
        application.reviewed_by_id = current_user.id
        
        # Notify applicant
        send_notification(
            user_id=application.user_id,
            title='Application Status Update',
            message=f'Your application to join "{project.title}" was not accepted.',
            notification_type='application',
            action_url=url_for('projects.list_projects'),
            project_id=project_id,
            sender_id=current_user.id
        )
        
        flash('Application has been rejected.', 'info')
    else:
        flash('Invalid action.', 'danger')
    
    db.session.commit()
    return redirect(url_for('projects.manage_applications', project_id=project_id))


@projects_bp.route('/<int:project_id>/members')
@login_required
@project_member_required
def view_members(project_id):
    """View project team members."""
    project = Project.query.get_or_404(project_id)
    members = project.members.filter_by(status='active').all()
    
    return render_template('projects/members.html',
                         project=project,
                         members=members)


@projects_bp.route('/<int:project_id>/members/<int:member_id>/remove')
@login_required
@project_owner_required
def remove_member(project_id, member_id):
    """Remove a member from the project."""
    project = Project.query.get_or_404(project_id)
    member = ProjectMember.query.get_or_404(member_id)
    
    if member.project_id != project_id:
        flash('Invalid member.', 'danger')
        return redirect(url_for('projects.view_members', project_id=project_id))
    
    member.status = 'removed'
    member.left_at = datetime.now(timezone.utc)
    db.session.commit()
    
    # Notify removed member
    send_notification(
        user_id=member.user_id,
        title='Removed from Project',
        message=f'You have been removed from the project "{project.title}".',
        notification_type='update',
        project_id=project_id,
        sender_id=current_user.id
    )
    
    flash('Member has been removed from the project.', 'info')
    return redirect(url_for('projects.view_members', project_id=project_id))


# Milestone routes
@projects_bp.route('/<int:project_id>/milestones')
@login_required
@project_member_required
def view_milestones(project_id):
    """View project milestones."""
    project = Project.query.get_or_404(project_id)
    milestones = project.milestones.order_by(Milestone.due_date).all()
    
    return render_template('projects/milestones.html',
                         project=project,
                         milestones=milestones)


# Alias for manage_milestones
@projects_bp.route('/<int:project_id>/milestones/manage')
@login_required
def manage_milestones(project_id):
    """Alias for view_milestones - manage project milestones."""
    return redirect(url_for('projects.view_milestones', project_id=project_id))


@projects_bp.route('/<int:project_id>/milestones/create', methods=['GET', 'POST'])
@login_required
@project_owner_required
def create_milestone(project_id):
    """Create a new milestone."""
    project = Project.query.get_or_404(project_id)
    form = MilestoneForm()
    
    # Get project members for assignment
    members = project.members.filter_by(status='active').all()
    form.assigned_to.choices = [(0, 'Unassigned')] + [(m.user.id, m.user.full_name) for m in members]
    
    if form.validate_on_submit():
        milestone = Milestone(
            project_id=project_id,
            title=form.title.data,
            description=form.description.data,
            due_date=form.due_date.data,
            priority=form.priority.data,
            assigned_to_id=form.assigned_to.data if form.assigned_to.data != 0 else None
        )
        db.session.add(milestone)
        db.session.commit()
        
        # Notify team members
        for member in members:
            send_notification(
                user_id=member.user_id,
                title='New Milestone',
                message=f'New milestone "{milestone.title}" added to "{project.title}".',
                notification_type='milestone',
                action_url=url_for('projects.view_milestones', project_id=project_id),
                project_id=project_id,
                sender_id=current_user.id
            )
        
        flash('Milestone created successfully!', 'success')
        return redirect(url_for('projects.view_milestones', project_id=project_id))
    
    return render_template('projects/milestone_form.html', form=form, project=project)


@projects_bp.route('/<int:project_id>/milestones/<int:milestone_id>/update', methods=['POST'])
@login_required
@project_member_required
def update_milestone_status(project_id, milestone_id):
    """Update milestone status."""
    project = Project.query.get_or_404(project_id)
    milestone = Milestone.query.get_or_404(milestone_id)
    
    if milestone.project_id != project_id:
        return jsonify({'error': 'Invalid milestone'}), 400
    
    new_status = request.form.get('status')
    if new_status not in ['pending', 'in_progress', 'completed']:
        return jsonify({'error': 'Invalid status'}), 400
    
    milestone.status = new_status
    if new_status == 'completed':
        milestone.completed_at = datetime.now(timezone.utc)
    
    db.session.commit()
    
    # Notify project owner
    if current_user.id != project.owner_id:
        send_notification(
            user_id=project.owner_id,
            title='Milestone Updated',
            message=f'Milestone "{milestone.title}" status changed to {new_status}.',
            notification_type='milestone',
            action_url=url_for('projects.view_milestones', project_id=project_id),
            project_id=project_id,
            sender_id=current_user.id
        )
    
    flash(f'Milestone status updated to {new_status}!', 'success')
    return redirect(url_for('projects.view_milestones', project_id=project_id))


# File management
@projects_bp.route('/<int:project_id>/files')
@login_required
@project_member_required
def view_files(project_id):
    """View project files."""
    project = Project.query.get_or_404(project_id)
    files = project.files.filter_by(is_current=True).order_by(ProjectFile.uploaded_at.desc()).all()
    
    return render_template('projects/files.html',
                         project=project,
                         files=files)


# Alias for manage_files
@projects_bp.route('/<int:project_id>/files/manage')
@login_required
def manage_files(project_id):
    """Alias for view_files - manage project files."""
    return redirect(url_for('projects.view_files', project_id=project_id))


@projects_bp.route('/<int:project_id>/files/upload', methods=['GET', 'POST'])
@login_required
@project_member_required
def upload_file(project_id):
    """Upload a file to the project."""
    project = Project.query.get_or_404(project_id)
    
    if request.method == 'GET':
        return render_template('projects/upload_file.html', project=project)
    
    if 'file' not in request.files:
        flash('No file selected.', 'danger')
        return redirect(url_for('projects.view_files', project_id=project_id))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('projects.view_files', project_id=project_id))
    
    # Validate file extension
    allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', set())
    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    if ext not in allowed_extensions:
        flash(f'File type .{ext} is not allowed.', 'danger')
        return redirect(url_for('projects.view_files', project_id=project_id))
    
    # Generate secure filename
    original_filename = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
    
    # Create project upload folder
    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], str(project_id))
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    
    # Save file
    file_path = os.path.join(upload_folder, unique_filename)
    file.save(file_path)
    file_size = os.path.getsize(file_path)
    
    # Check for existing file with same name (for versioning)
    existing_file = ProjectFile.query.filter_by(
        project_id=project_id,
        original_filename=original_filename,
        is_current=True
    ).first()
    
    new_version = 1
    parent_id = None
    if existing_file:
        existing_file.is_current = False
        new_version = existing_file.version + 1
        parent_id = existing_file.id
    
    # Create file record
    project_file = ProjectFile(
        project_id=project_id,
        filename=unique_filename,
        original_filename=original_filename,
        file_type=ext,
        file_size=file_size,
        version=new_version,
        description=request.form.get('description', ''),
        uploaded_by_id=current_user.id,
        parent_id=parent_id
    )
    db.session.add(project_file)
    db.session.commit()
    
    flash(f'File "{original_filename}" uploaded successfully!', 'success')
    return redirect(url_for('projects.view_files', project_id=project_id))


@projects_bp.route('/<int:project_id>/files/<int:file_id>/versions')
@login_required
@project_member_required
def view_file_versions(project_id, file_id):
    """View file version history."""
    project = Project.query.get_or_404(project_id)
    current_file = ProjectFile.query.get_or_404(file_id)
    
    if current_file.project_id != project_id:
        flash('Invalid file.', 'danger')
        return redirect(url_for('projects.view_files', project_id=project_id))
    
    # Get all versions of this file
    versions = ProjectFile.query.filter_by(
        project_id=project_id,
        original_filename=current_file.original_filename
    ).order_by(ProjectFile.version.desc()).all()
    
    return render_template('projects/file_versions.html',
                         project=project,
                         current_file=current_file,
                         versions=versions)


@projects_bp.route('/<int:project_id>/files/<int:file_id>/download')
@login_required
@project_member_required
def download_file(project_id, file_id):
    """Download a project file."""
    from flask import send_from_directory
    
    project = Project.query.get_or_404(project_id)
    project_file = ProjectFile.query.get_or_404(file_id)
    
    if project_file.project_id != project_id:
        flash('Invalid file.', 'danger')
        return redirect(url_for('projects.view_files', project_id=project_id))
    
    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], str(project_id))
    
    return send_from_directory(
        upload_folder,
        project_file.filename,
        as_attachment=True,
        download_name=project_file.original_filename
    )


@projects_bp.route('/<int:project_id>/files/<int:file_id>/delete', methods=['POST'])
@login_required
@project_member_required
def delete_file(project_id, file_id):
    """Delete a project file."""
    project = Project.query.get_or_404(project_id)
    project_file = ProjectFile.query.get_or_404(file_id)
    
    if project_file.project_id != project_id:
        flash('Invalid file.', 'danger')
        return redirect(url_for('projects.view_files', project_id=project_id))
    
    # Only the uploader or project owner can delete
    if current_user.id != project_file.uploaded_by_id and current_user.id != project.owner_id:
        flash('You do not have permission to delete this file.', 'danger')
        return redirect(url_for('projects.view_files', project_id=project_id))
    
    # Delete the physical file
    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], str(project_id))
    file_path = os.path.join(upload_folder, project_file.filename)
    
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        pass  # File might not exist
    
    # Delete from database
    filename = project_file.original_filename
    db.session.delete(project_file)
    db.session.commit()
    
    flash(f'File "{filename}" deleted successfully.', 'success')
    return redirect(url_for('projects.view_files', project_id=project_id))


# My projects routes
@projects_bp.route('/my-projects')
@login_required
def my_projects():
    """View user's projects (owned or member of)."""
    # Get projects owned by the user (all users can create projects now)
    owned_projects = Project.query.filter_by(owner_id=current_user.id)\
        .order_by(Project.created_at.desc()).all()
    
    # Get projects user is a member of
    memberships = ProjectMember.query.filter_by(
        user_id=current_user.id,
        status='active'
    ).all()
    member_projects = [m.project for m in memberships]
    
    # Get pending applications
    pending_applications = ProjectApplication.query.filter_by(
        user_id=current_user.id,
        status='pending'
    ).all()
    
    # Get pending invitations
    pending_invitations = ProjectInvitation.query.filter_by(
        invited_user_id=current_user.id,
        status='pending'
    ).all()
    
    return render_template('projects/my_projects.html',
                         owned_projects=owned_projects,
                         member_projects=member_projects,
                         pending_applications=pending_applications,
                         pending_invitations=pending_invitations)


# ============== INVITATION ROUTES ==============

@projects_bp.route('/join/<invite_code>')
@login_required
def join_via_link(invite_code):
    """Join a project via invite link."""
    project = Project.query.filter_by(invite_code=invite_code).first_or_404()
    
    # Check if already a member
    existing_member = ProjectMember.query.filter_by(
        project_id=project.id,
        user_id=current_user.id,
        status='active'
    ).first()
    
    if existing_member:
        flash('You are already a member of this project.', 'info')
        return redirect(url_for('projects.view_project', project_id=project.id))
    
    # Check if user is the owner
    if project.owner_id == current_user.id:
        flash('You are the owner of this project.', 'info')
        return redirect(url_for('projects.view_project', project_id=project.id))
    
    # Check team size (if limit is set)
    if project.max_team_size and project.max_team_size > 0 and project.team_count >= project.max_team_size:
        flash('This project has reached its maximum team size.', 'warning')
        return redirect(url_for('projects.view_project', project_id=project.id))
    
    # Add user as member
    member = ProjectMember(
        project_id=project.id,
        user_id=current_user.id,
        role='member',
        status='active'
    )
    db.session.add(member)
    
    # Send notification to project owner
    send_notification(
        user_id=project.owner_id,
        title='New Team Member',
        message=f'{current_user.full_name} has joined your project "{project.title}" via invite link.',
        notification_type='project',
        action_url=url_for('projects.view_project', project_id=project.id),
        sender_id=current_user.id,
        project_id=project.id
    )
    
    db.session.commit()
    flash(f'You have joined "{project.title}"!', 'success')
    return redirect(url_for('projects.view_project', project_id=project.id))


@projects_bp.route('/<int:project_id>/invite', methods=['GET', 'POST'])
@login_required
@project_owner_required
def invite_members(project_id):
    """Invite members to a project."""
    project = Project.query.get_or_404(project_id)
    
    if request.method == 'POST':
        user_ids = request.form.getlist('user_ids')
        message = request.form.get('message', '')
        
        for user_id in user_ids:
            user = User.query.get(int(user_id))
            if not user:
                continue
                
            # Check if already a member
            existing_member = ProjectMember.query.filter_by(
                project_id=project.id,
                user_id=user.id,
                status='active'
            ).first()
            if existing_member:
                continue
            
            # Check if invitation already exists
            existing_invite = ProjectInvitation.query.filter_by(
                project_id=project.id,
                invited_user_id=user.id,
                status='pending'
            ).first()
            if existing_invite:
                continue
            
            # Create invitation
            invitation = ProjectInvitation(
                project_id=project.id,
                invited_by_id=current_user.id,
                invited_user_id=user.id,
                message=message,
                expires_at=datetime.utcnow() + timedelta(days=7)
            )
            db.session.add(invitation)
            db.session.flush()  # Flush to get the invitation ID
            
            # Send notification
            send_notification(
                user_id=user.id,
                title='Project Invitation',
                message=f'{current_user.full_name} has invited you to join "{project.title}".',
                notification_type='invitation',
                action_url=url_for('projects.view_invitation', invitation_id=invitation.id),
                sender_id=current_user.id,
                project_id=project.id
            )
        
        db.session.commit()
        flash('Invitations sent successfully!', 'success')
        return redirect(url_for('projects.view_project', project_id=project.id))
    
    # Get available users (students not in project)
    existing_member_ids = [m.user_id for m in project.members.filter_by(status='active').all()]
    existing_member_ids.append(project.owner_id)
    
    available_users = User.query.filter(
        User.id.notin_(existing_member_ids),
        User.is_active == True
    ).order_by(User.first_name).all()
    
    return render_template('projects/invite_members.html',
                         project=project,
                         available_users=available_users)


@projects_bp.route('/invitation/<int:invitation_id>')
@login_required
def view_invitation(invitation_id):
    """View an invitation."""
    invitation = ProjectInvitation.query.get_or_404(invitation_id)
    
    if invitation.invited_user_id != current_user.id:
        flash('You do not have permission to view this invitation.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    return render_template('projects/view_invitation.html', invitation=invitation)


@projects_bp.route('/invitation/<int:invitation_id>/accept', methods=['POST'])
@login_required
def accept_invitation(invitation_id):
    """Accept a project invitation."""
    invitation = ProjectInvitation.query.get_or_404(invitation_id)
    
    if invitation.invited_user_id != current_user.id:
        flash('You do not have permission to accept this invitation.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    if invitation.status != 'pending':
        flash('This invitation is no longer valid.', 'warning')
        return redirect(url_for('projects.my_projects'))
    
    if invitation.is_expired:
        invitation.status = 'expired'
        db.session.commit()
        flash('This invitation has expired.', 'warning')
        return redirect(url_for('projects.my_projects'))
    
    # Check team size (if limit is set)
    project = invitation.project
    if project.max_team_size and project.max_team_size > 0 and project.team_count >= project.max_team_size:
        flash('This project has reached its maximum team size.', 'warning')
        return redirect(url_for('projects.my_projects'))
    
    # Accept invitation
    invitation.accept()
    
    # Add as member
    member = ProjectMember(
        project_id=project.id,
        user_id=current_user.id,
        role='member',
        status='active'
    )
    db.session.add(member)
    
    # Notify project owner
    send_notification(
        user_id=project.owner_id,
        title='Invitation Accepted',
        message=f'{current_user.full_name} has accepted your invitation to join "{project.title}".',
        notification_type='project',
        action_url=url_for('projects.view_project', project_id=project.id),
        sender_id=current_user.id,
        project_id=project.id
    )
    
    db.session.commit()
    flash(f'You have joined "{project.title}"!', 'success')
    return redirect(url_for('projects.view_project', project_id=project.id))


@projects_bp.route('/invitation/<int:invitation_id>/decline', methods=['POST'])
@login_required
def decline_invitation(invitation_id):
    """Decline a project invitation."""
    invitation = ProjectInvitation.query.get_or_404(invitation_id)
    
    if invitation.invited_user_id != current_user.id:
        flash('You do not have permission to decline this invitation.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    invitation.decline()
    db.session.commit()
    
    flash('Invitation declined.', 'info')
    return redirect(url_for('projects.my_projects'))


@projects_bp.route('/<int:project_id>/regenerate-invite', methods=['POST'])
@login_required
@project_owner_required
def regenerate_invite_code(project_id):
    """Regenerate the project invite code."""
    project = Project.query.get_or_404(project_id)
    project.regenerate_invite_code()
    db.session.commit()
    flash('Invite link regenerated successfully!', 'success')
    return redirect(url_for('projects.view_project', project_id=project.id))


# ============== TASK ROUTES ==============

@projects_bp.route('/<int:project_id>/tasks')
@login_required
@project_member_required
def view_tasks(project_id):
    """View project tasks."""
    project = Project.query.get_or_404(project_id)
    
    # Filter tasks by status
    status_filter = request.args.get('status', 'all')
    
    if status_filter == 'all':
        tasks = project.tasks.all()
    else:
        tasks = project.tasks.filter_by(status=status_filter).all()
    
    # Get team members for assignment
    members = project.members.filter_by(status='active').all()
    
    return render_template('projects/tasks.html',
                         project=project,
                         tasks=tasks,
                         members=members,
                         status_filter=status_filter)


@projects_bp.route('/<int:project_id>/tasks/create', methods=['GET', 'POST'])
@login_required
@project_member_required
def create_task(project_id):
    """Create a new task."""
    project = Project.query.get_or_404(project_id)
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        priority = request.form.get('priority', 'medium')
        due_date_str = request.form.get('due_date')
        assigned_to_id = request.form.get('assigned_to_id')
        milestone_id = request.form.get('milestone_id')
        
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.fromisoformat(due_date_str)
            except:
                pass
        
        task = Task(
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
            project_id=project.id,
            created_by_id=current_user.id,
            assigned_to_id=int(assigned_to_id) if assigned_to_id else None,
            milestone_id=int(milestone_id) if milestone_id else None
        )
        db.session.add(task)
        
        # Notify assigned user
        if assigned_to_id and int(assigned_to_id) != current_user.id:
            send_notification(
                user_id=int(assigned_to_id),
                title='New Task Assigned',
                message=f'{current_user.full_name} assigned you a task: "{title}" in project "{project.title}".',
                notification_type='task',
                action_url=url_for('projects.view_tasks', project_id=project.id),
                sender_id=current_user.id,
                project_id=project.id
            )
        
        db.session.commit()
        flash('Task created successfully!', 'success')
        return redirect(url_for('projects.view_tasks', project_id=project.id))
    
    members = project.members.filter_by(status='active').all()
    milestones = project.milestones.all()
    
    return render_template('projects/create_task.html',
                         project=project,
                         members=members,
                         milestones=milestones)


@projects_bp.route('/<int:project_id>/tasks/<int:task_id>/update', methods=['POST'])
@login_required
@project_member_required
def update_task_status(project_id, task_id):
    """Update task status."""
    task = Task.query.get_or_404(task_id)
    
    if task.project_id != project_id:
        flash('Invalid task.', 'danger')
        return redirect(url_for('projects.view_tasks', project_id=project_id))
    
    new_status = request.form.get('status')
    if new_status in ['todo', 'in_progress', 'review', 'completed']:
        task.status = new_status
        if new_status == 'completed':
            task.completed_at = datetime.now(timezone.utc)
        db.session.commit()
        flash('Task updated!', 'success')
    
    return redirect(url_for('projects.view_tasks', project_id=project_id))


@projects_bp.route('/<int:project_id>/tasks/<int:task_id>/assign', methods=['POST'])
@login_required
@project_member_required
def assign_task(project_id, task_id):
    """Assign a task to a team member."""
    task = Task.query.get_or_404(task_id)
    
    if task.project_id != project_id:
        flash('Invalid task.', 'danger')
        return redirect(url_for('projects.view_tasks', project_id=project_id))
    
    assigned_to_id = request.form.get('assigned_to_id')
    
    if assigned_to_id:
        task.assigned_to_id = int(assigned_to_id)
        
        # Notify the assigned user
        if int(assigned_to_id) != current_user.id:
            send_notification(
                user_id=int(assigned_to_id),
                title='Task Assigned',
                message=f'{current_user.full_name} assigned you the task: "{task.title}".',
                notification_type='task',
                action_url=url_for('projects.view_tasks', project_id=project_id),
                sender_id=current_user.id,
                project_id=project_id
            )
        
        db.session.commit()
        flash('Task assigned successfully!', 'success')
    
    return redirect(url_for('projects.view_tasks', project_id=project_id))


# ============== TEAM MEMBER ROUTES ==============

@projects_bp.route('/<int:project_id>/team')
@login_required
@project_member_required
def view_team(project_id):
    """View project team members."""
    project = Project.query.get_or_404(project_id)
    
    members = project.members.filter_by(status='active').all()
    pending_invitations = project.invitations.filter_by(status='pending').all()
    
    # Get available users for inviting (if owner)
    available_users = []
    if project.owner_id == current_user.id:
        existing_member_ids = [m.user_id for m in members]
        existing_member_ids.append(project.owner_id)
        pending_invite_ids = [i.invited_user_id for i in pending_invitations if i.invited_user_id]
        excluded_ids = existing_member_ids + pending_invite_ids
        
        available_users = User.query.filter(
            User.id.notin_(excluded_ids),
            User.is_active == True
        ).order_by(User.first_name).limit(50).all()
    
    return render_template('projects/team.html',
                         project=project,
                         members=members,
                         pending_invitations=pending_invitations,
                         available_users=available_users)


# Alias for manage_team
@projects_bp.route('/<int:project_id>/team/manage')
@login_required
def manage_team(project_id):
    """Alias for view_team - manage project team."""
    return redirect(url_for('projects.view_team', project_id=project_id))

"""Dashboard and reporting routes."""
import base64
from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import (User, Project, ProjectMember, Milestone, Contribution, 
                       ProjectApplication, Notification, Department, Skill, ProjectGrade,
                       ProjectComment, ProjectUpdate, Role)
from app.forms import ProfileForm
from app.utils.decorators import lecturer_required, admin_required
from sqlalchemy import func

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    """Main dashboard view."""
    if current_user.is_lecturer:
        return redirect(url_for('dashboard.lecturer_dashboard'))
    elif current_user.is_student:
        return redirect(url_for('dashboard.student_dashboard'))
    elif current_user.is_admin:
        return redirect(url_for('dashboard.admin_dashboard'))
    else:
        return redirect(url_for('dashboard.student_dashboard'))


@dashboard_bp.route('/student')
@login_required
def student_dashboard():
    """Student dashboard with project overview."""
    # Get projects user is a member of (as memberships for display)
    memberships = ProjectMember.query.filter_by(
        user_id=current_user.id,
        status='active'
    ).all()
    
    # Get projects user owns (created)
    owned_projects = Project.query.filter_by(owner_id=current_user.id).all()
    
    # Create a combined list of all projects (for milestones, etc.)
    all_project_ids = set()
    projects = []
    for p in owned_projects:
        if p.id not in all_project_ids:
            all_project_ids.add(p.id)
            projects.append(p)
    for m in memberships:
        if m.project.id not in all_project_ids:
            all_project_ids.add(m.project.id)
            projects.append(m.project)
    
    # Active projects count (owned + member)
    active_projects_count = len(projects)
    
    # Completed milestones count
    completed_milestones_count = 0
    for project in projects:
        completed_milestones_count += project.milestones.filter_by(status='completed').count()
    
    # Get pending applications count
    pending_applications_count = ProjectApplication.query.filter_by(
        user_id=current_user.id,
        status='pending'
    ).count()
    
    # Get upcoming deadlines and overdue milestones
    upcoming_deadlines = []
    now = datetime.now(timezone.utc)
    for project in projects:
        milestones = Milestone.query.filter_by(project_id=project.id)\
            .filter(Milestone.status != 'completed')\
            .order_by(Milestone.due_date).all()
        for m in milestones:
            due = m.due_date
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            delta = due - now
            days_diff = delta.days

            if days_diff < 0:
                days_left = f'Overdue by {abs(days_diff)} day{"s" if abs(days_diff) != 1 else ""}'
                is_overdue = True
                is_soon = False
            elif days_diff == 0:
                days_left = 'Due today'
                is_overdue = False
                is_soon = True
            elif days_diff == 1:
                days_left = 'Due tomorrow'
                is_overdue = False
                is_soon = True
            else:
                days_left = f'{days_diff} days left'
                is_overdue = False
                is_soon = days_diff <= 3

            upcoming_deadlines.append({
                'title': m.title,
                'milestone': m,
                'project': project,
                'due_date': due,
                'days_left': days_left,
                'is_overdue': is_overdue,
                'is_soon': is_soon
            })
    
    # Sort: overdue first (most overdue at top), then soonest upcoming
    upcoming_deadlines.sort(key=lambda x: x['due_date'])
    
    # Get user's contribution stats
    total_contributions = Contribution.query.filter_by(user_id=current_user.id).count()
    total_hours = db.session.query(func.sum(Contribution.hours_spent))\
        .filter_by(user_id=current_user.id).scalar() or 0
    
    # Get recent contributions
    recent_contributions = Contribution.query.filter_by(user_id=current_user.id)\
        .order_by(Contribution.created_at.desc()).limit(5).all()
    
    # Get unread notifications
    unread_notifications = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    # Recommended projects (based on skills and department)
    recommended = Project.query.filter(
        Project.status == 'open',
        Project.visibility.in_(['public', 'department'])
    )
    if current_user.department_id:
        recommended = recommended.filter(
            (Project.department_id == current_user.department_id) |
            (Project.visibility == 'public')
        )
    recommended = recommended.order_by(Project.created_at.desc()).limit(5).all()
    
    return render_template('dashboard/student.html',
                         projects=projects,
                         my_projects=memberships,
                         owned_projects=owned_projects,
                         active_projects=active_projects_count,
                         completed_milestones=completed_milestones_count,
                         pending_applications=pending_applications_count,
                         upcoming_deadlines=upcoming_deadlines[:5],
                         total_contributions=total_contributions,
                         total_hours=total_hours,
                         recent_contributions=recent_contributions,
                         unread_notifications=unread_notifications,
                         recommended_projects=recommended)


@dashboard_bp.route('/lecturer')
@login_required
@lecturer_required
def lecturer_dashboard():
    """Lecturer dashboard with project management overview."""
    # Get owned projects (legacy support)
    owned_projects_query = Project.query.filter_by(owner_id=current_user.id)
    
    # Also get projects in the lecturer's department (student-created projects)
    dept_projects_query = Project.query.filter(
        Project.department_id == current_user.department_id,
        Project.owner_id != current_user.id
    ) if current_user.department_id else Project.query.filter(False)
    
    # Combine owned + department projects (no duplicates)
    owned_projects = owned_projects_query.order_by(Project.created_at.desc()).all()
    dept_projects = dept_projects_query.order_by(Project.created_at.desc()).all()
    
    # All monitored projects (owned + department)
    seen_ids = set()
    all_monitored_projects = []
    for p in owned_projects + dept_projects:
        if p.id not in seen_ids:
            seen_ids.add(p.id)
            all_monitored_projects.append(p)
    
    # Split by status
    active_projects = [p for p in all_monitored_projects if p.status in ['open', 'in_progress']]
    draft_projects = [p for p in all_monitored_projects if p.status == 'draft']
    completed_projects = [p for p in all_monitored_projects if p.status == 'completed']
    
    # Get pending applications across all projects
    pending_applications = []
    for project in active_projects:
        apps = project.applications.filter_by(status='pending').all()
        for app in apps:
            pending_applications.append({
                'application': app,
                'project': project
            })
    
    # Get projects needing attention (overdue milestones, submissions pending review)
    attention_needed = []
    for project in active_projects:
        overdue = project.milestones.filter(
            Milestone.status != 'completed',
            Milestone.due_date < datetime.now(timezone.utc)
        ).count()
        
        pending_submissions = 0
        for milestone in project.milestones:
            pending_submissions += milestone.submissions.filter_by(status='pending').count()
        
        if overdue > 0 or pending_submissions > 0:
            attention_needed.append({
                'project': project,
                'overdue_milestones': overdue,
                'pending_submissions': pending_submissions
            })
    
    # Statistics
    total_students = sum(p.team_count for p in all_monitored_projects)
    total_projects = len(all_monitored_projects)
    total_milestones = sum(p.milestones.count() for p in all_monitored_projects)
    completed_milestones = sum(
        p.milestones.filter_by(status='completed').count() 
        for p in all_monitored_projects
    )
    
    # Completion rate
    completion_rate = 0
    if total_milestones > 0:
        completion_rate = round((completed_milestones / total_milestones) * 100)
    
    # Count pending applications
    pending_applications_count = len(pending_applications)
    
    # Recent activity across all projects
    recent_contributions = Contribution.query.filter(
        Contribution.project_id.in_([p.id for p in all_monitored_projects])
    ).order_by(Contribution.created_at.desc()).limit(10).all()
    
    # Recent applications for display
    recent_applications = []
    for project in all_monitored_projects:
        apps = project.applications.filter_by(status='pending').order_by(
            ProjectApplication.applied_at.desc()
        ).limit(5).all()
        for app in apps:
            recent_applications.append(app)
    recent_applications = sorted(recent_applications, key=lambda x: x.applied_at, reverse=True)[:10]
    
    # Project stats for distribution chart
    project_stats = {
        'completed': len([p for p in all_monitored_projects if p.status == 'completed']),
        'in_progress': len([p for p in all_monitored_projects if p.status == 'in_progress']),
        'open': len([p for p in all_monitored_projects if p.status == 'open']),
        'closed': len([p for p in all_monitored_projects if p.status == 'closed']),
        'draft': len([p for p in all_monitored_projects if p.status == 'draft'])
    }
    
    # Get student progress data
    student_progress = []
    for project in all_monitored_projects:
        members = project.members.filter_by(status='active').all()
        for member in members:
            # Get contribution count for this student in this project
            contribution_count = Contribution.query.filter_by(
                user_id=member.user_id,
                project_id=project.id
            ).count()
            
            # Get last activity
            last_contribution = Contribution.query.filter_by(
                user_id=member.user_id,
                project_id=project.id
            ).order_by(Contribution.created_at.desc()).first()
            
            last_active = last_contribution.created_at if last_contribution else member.joined_at
            
            # Check if active in last 7 days
            is_active = False
            if last_active:
                # Ensure timezone-aware comparison
                if last_active.tzinfo is None:
                    last_active = last_active.replace(tzinfo=timezone.utc)
                is_active = (datetime.now(timezone.utc) - last_active).days <= 7
            
            student_progress.append({
                'student': member.user,
                'project': project,
                'contribution_count': contribution_count,
                'last_active': last_active,
                'is_active': is_active
            })
    
    return render_template('dashboard/lecturer.html',
                         my_projects=all_monitored_projects,
                         active_projects=active_projects,
                         draft_projects=draft_projects,
                         completed_projects=completed_projects,
                         pending_applications=pending_applications_count,
                         recent_applications=recent_applications,
                         attention_needed=attention_needed,
                         total_projects=total_projects,
                         total_students=total_students,
                         total_milestones=total_milestones,
                         completed_milestones=completed_milestones,
                         completion_rate=completion_rate,
                         recent_contributions=recent_contributions,
                         project_stats=project_stats,
                         student_progress=student_progress)


@dashboard_bp.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    """Admin dashboard with system overview."""
    # User statistics
    total_users = User.query.count()
    total_students = User.query.join(User.roles).filter_by(name='student').count()
    total_lecturers = User.query.join(User.roles).filter_by(name='lecturer').count()
    
    # Project statistics  
    total_projects = Project.query.count()
    active_projects = Project.query.filter(Project.status.in_(['open', 'in_progress'])).count()
    completed_projects = Project.query.filter_by(status='completed').count()
    
    # Recent registrations
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    
    # Recent projects
    recent_projects = Project.query.order_by(Project.created_at.desc()).limit(10).all()
    
    # Department distribution
    dept_stats = db.session.query(
        Department.name,
        func.count(User.id).label('user_count')
    ).outerjoin(User).group_by(Department.id).all()
    
    # Monthly activity (last 6 months)
    six_months_ago = datetime.now(timezone.utc) - timedelta(days=180)
    monthly_projects = db.session.query(
        func.strftime('%Y-%m', Project.created_at).label('month'),
        func.count(Project.id).label('count')
    ).filter(Project.created_at >= six_months_ago)\
    .group_by(func.strftime('%Y-%m', Project.created_at)).all()
    
    return render_template('dashboard/admin.html',
                         total_users=total_users,
                         total_students=total_students,
                         total_lecturers=total_lecturers,
                         total_projects=total_projects,
                         active_projects=active_projects,
                         completed_projects=completed_projects,
                         recent_users=recent_users,
                         recent_projects=recent_projects,
                         dept_stats=dept_stats,
                         monthly_projects=monthly_projects)


@dashboard_bp.route('/profile')
@login_required
def profile():
    """View user profile."""
    # Get user statistics
    if current_user.is_student:
        memberships = ProjectMember.query.filter_by(
            user_id=current_user.id,
            status='active'
        ).count()
        completed_projects = ProjectMember.query.join(Project).filter(
            ProjectMember.user_id == current_user.id,
            Project.status == 'completed'
        ).count()
        total_contributions = Contribution.query.filter_by(user_id=current_user.id).count()
        total_hours = db.session.query(func.sum(Contribution.hours_spent))\
            .filter_by(user_id=current_user.id).scalar() or 0
        
        stats = {
            'active_projects': memberships,
            'completed_projects': completed_projects,
            'total_contributions': total_contributions,
            'total_hours': round(total_hours, 1)
        }
    else:
        owned_projects = Project.query.filter_by(owner_id=current_user.id).count()
        active_projects = Project.query.filter(
            Project.owner_id == current_user.id,
            Project.status.in_(['open', 'in_progress'])
        ).count()
        completed_projects = Project.query.filter_by(
            owner_id=current_user.id,
            status='completed'
        ).count()
        total_students = db.session.query(func.count(ProjectMember.id))\
            .join(Project).filter(Project.owner_id == current_user.id).scalar() or 0
        
        stats = {
            'owned_projects': owned_projects,
            'active_projects': active_projects,
            'completed_projects': completed_projects,
            'total_students': total_students
        }
    
    return render_template('dashboard/profile.html',
                         user=current_user,
                         stats=stats)


@dashboard_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit user profile."""
    form = ProfileForm(obj=current_user)
    
    # Populate department choices
    departments = Department.query.order_by(Department.name).all()
    form.department.choices = [(0, 'Select Department')] + [(d.id, d.name) for d in departments]
    
    # Populate skills choices
    all_skills = Skill.query.order_by(Skill.name).all()
    
    if request.method == 'GET':
        form.department.data = current_user.department_id or 0
        form.skills.data = ', '.join([s.name for s in current_user.skills])
    
    if form.validate_on_submit():
        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        current_user.phone = form.phone.data
        current_user.bio = form.bio.data
        current_user.department_id = form.department.data if form.department.data != 0 else None
        
        # Handle avatar upload - store as base64 data URL
        if form.avatar.data:
            avatar_file = form.avatar.data
            if avatar_file.filename:
                # Read file and convert to base64
                file_data = avatar_file.read()
                # Check file size (max 2MB for profile pictures)
                if len(file_data) > 2 * 1024 * 1024:
                    flash('Profile picture must be less than 2MB.', 'danger')
                    return render_template('dashboard/edit_profile.html',
                                         form=form,
                                         all_skills=all_skills)
                
                # Get the file extension for MIME type
                filename = avatar_file.filename.lower()
                if filename.endswith('.png'):
                    mime_type = 'image/png'
                elif filename.endswith('.gif'):
                    mime_type = 'image/gif'
                else:
                    mime_type = 'image/jpeg'
                
                # Convert to base64 data URL
                b64_data = base64.b64encode(file_data).decode('utf-8')
                current_user.avatar = f'data:{mime_type};base64,{b64_data}'
        
        # Update skills
        current_user.skills.clear()
        skill_names = [s.strip() for s in form.skills.data.split(',') if s.strip()]
        for skill_name in skill_names:
            skill = Skill.query.filter_by(name=skill_name).first()
            if not skill:
                skill = Skill(name=skill_name)
                db.session.add(skill)
            current_user.skills.append(skill)
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('dashboard.profile'))
    
    return render_template('dashboard/edit_profile.html',
                         form=form,
                         all_skills=all_skills)


# Reporting routes
@dashboard_bp.route('/reports')
@login_required
@lecturer_required
def reports():
    """Reports overview page."""
    return render_template('dashboard/reports.html')


@dashboard_bp.route('/reports/projects')
@login_required
@lecturer_required
def project_reports():
    """Project participation and completion reports."""
    # Get lecturer's own projects AND student projects from same department
    own_projects = Project.query.filter_by(owner_id=current_user.id).all()
    
    dept_projects = []
    if current_user.department_id:
        dept_student_ids = [u.id for u in User.query.filter(
            User.department_id == current_user.department_id
        ).join(User.roles).filter(Role.name == 'student').all()]
        dept_projects = Project.query.filter(
            Project.owner_id.in_(dept_student_ids)
        ).all() if dept_student_ids else []
    
    # Combine and deduplicate
    seen_ids = set()
    projects = []
    for p in own_projects + dept_projects:
        if p.id not in seen_ids:
            seen_ids.add(p.id)
            projects.append(p)
    
    report_data = []
    for project in projects:
        members = project.members.filter_by(status='active').all()
        contributions = Contribution.query.filter_by(project_id=project.id).all()
        
        member_data = []
        for member in members:
            user_contributions = [c for c in contributions if c.user_id == member.user_id]
            member_data.append({
                'user': member.user,
                'contributions': len(user_contributions),
                'hours': sum(c.hours_spent or 0 for c in user_contributions)
            })
        
        report_data.append({
            'project': project,
            'member_count': len(members),
            'total_contributions': len(contributions),
            'progress': project.progress,
            'members': member_data
        })
    
    return render_template('dashboard/project_reports.html',
                         reports=report_data)


@dashboard_bp.route('/reports/engagement')
@login_required
@lecturer_required
def engagement_reports():
    """Student engagement reports."""
    # Get all students in lecturer's projects AND department projects
    own_project_ids = [p.id for p in Project.query.filter_by(owner_id=current_user.id).all()]
    
    dept_project_ids = []
    if current_user.department_id:
        dept_student_ids = [u.id for u in User.query.filter(
            User.department_id == current_user.department_id
        ).join(User.roles).filter(Role.name == 'student').all()]
        if dept_student_ids:
            dept_project_ids = [p.id for p in Project.query.filter(
                Project.owner_id.in_(dept_student_ids)
            ).all()]
    
    project_ids = list(set(own_project_ids + dept_project_ids))
    
    members = ProjectMember.query.filter(
        ProjectMember.project_id.in_(project_ids),
        ProjectMember.status == 'active'
    ).all()
    
    engagement_data = []
    for member in members:
        contributions = Contribution.query.filter_by(
            user_id=member.user_id,
            project_id=member.project_id
        ).all()
        
        # Calculate engagement metrics
        total_contributions = len(contributions)
        total_hours = sum(c.hours_spent or 0 for c in contributions)
        
        # Days since last contribution
        if contributions:
            last_contribution = max(c.created_at for c in contributions)
            # Ensure timezone-aware comparison
            if last_contribution.tzinfo is None:
                last_contribution = last_contribution.replace(tzinfo=timezone.utc)
            days_since = (datetime.now(timezone.utc) - last_contribution).days
        else:
            days_since = None
        
        engagement_data.append({
            'user': member.user,
            'project': member.project,
            'contributions': total_contributions,
            'hours': total_hours,
            'days_since_last': days_since,
            'joined_at': member.joined_at
        })
    
    # Sort by contributions (descending)
    engagement_data.sort(key=lambda x: x['contributions'], reverse=True)
    
    return render_template('dashboard/engagement_reports.html',
                         engagement_data=engagement_data)


# ============== GRADING ROUTES ==============

@dashboard_bp.route('/grading')
@login_required
@lecturer_required
def grading_overview():
    """Overview of projects that need grading."""
    # Get lecturer's own projects AND student projects from same department
    own_projects = Project.query.filter_by(owner_id=current_user.id).all()
    
    dept_projects = []
    if current_user.department_id:
        dept_student_ids = [u.id for u in User.query.filter(
            User.department_id == current_user.department_id
        ).join(User.roles).filter(Role.name == 'student').all()]
        dept_projects = Project.query.filter(
            Project.owner_id.in_(dept_student_ids)
        ).all() if dept_student_ids else []
    
    seen_ids = set()
    projects = []
    for p in own_projects + dept_projects:
        if p.id not in seen_ids:
            seen_ids.add(p.id)
            projects.append(p)
    
    grading_data = []
    for project in projects:
        members = project.members.filter_by(status='active').all()
        grades = {g.student_id: g for g in project.grades.all()}
        
        graded_count = len(grades)
        total_members = len(members)
        
        member_data = []
        for member in members:
            grade = grades.get(member.user_id)
            contributions = Contribution.query.filter_by(
                project_id=project.id,
                user_id=member.user_id
            ).count()
            
            member_data.append({
                'user': member.user,
                'grade': grade,
                'contributions': contributions,
                'joined_at': member.joined_at
            })
        
        grading_data.append({
            'project': project,
            'members': member_data,
            'graded_count': graded_count,
            'total_members': total_members
        })
    
    return render_template('dashboard/grading.html', grading_data=grading_data)


@dashboard_bp.route('/grading/project/<int:project_id>')
@login_required
@lecturer_required
def grade_project(project_id):
    """Grade students in a specific project."""
    project = Project.query.get_or_404(project_id)
    
    # Allow if lecturer owns the project OR is in same department as the project owner
    is_owner = project.owner_id == current_user.id
    is_dept_lecturer = (current_user.department_id and 
                        project.owner and 
                        project.owner.department_id == current_user.department_id)
    
    if not is_owner and not is_dept_lecturer:
        flash('You do not have permission to grade this project.', 'danger')
        return redirect(url_for('dashboard.grading_overview'))
    
    members = project.members.filter_by(status='active').all()
    existing_grades = {g.student_id: g for g in project.grades.all()}
    
    member_data = []
    for member in members:
        contributions = Contribution.query.filter_by(
            project_id=project.id,
            user_id=member.user_id
        ).order_by(Contribution.created_at.desc()).all()
        
        total_hours = sum(c.hours_spent or 0 for c in contributions)
        
        member_data.append({
            'user': member.user,
            'joined_at': member.joined_at,
            'contributions': contributions,
            'contribution_count': len(contributions),
            'total_hours': total_hours,
            'existing_grade': existing_grades.get(member.user_id)
        })
    
    return render_template('dashboard/grade_project.html',
                         project=project,
                         members=member_data)


@dashboard_bp.route('/grading/project/<int:project_id>/student/<int:student_id>', methods=['GET', 'POST'])
@login_required
@lecturer_required
def grade_student(project_id, student_id):
    """Grade a specific student for a project."""
    project = Project.query.get_or_404(project_id)
    student = User.query.get_or_404(student_id)
    
    # Allow if lecturer owns the project OR is in same department as the project owner
    is_owner = project.owner_id == current_user.id
    is_dept_lecturer = (current_user.department_id and 
                        project.owner and 
                        project.owner.department_id == current_user.department_id)
    
    if not is_owner and not is_dept_lecturer:
        flash('You do not have permission to grade this project.', 'danger')
        return redirect(url_for('dashboard.grading_overview'))
    
    # Check if student is a member
    membership = ProjectMember.query.filter_by(
        project_id=project_id,
        user_id=student_id,
        status='active'
    ).first()
    
    if not membership:
        flash('This student is not a member of this project.', 'danger')
        return redirect(url_for('dashboard.grade_project', project_id=project_id))
    
    # Get existing grade if any
    existing_grade = ProjectGrade.query.filter_by(
        project_id=project_id,
        student_id=student_id
    ).first()
    
    # Get contributions for this student
    contributions = Contribution.query.filter_by(
        project_id=project_id,
        user_id=student_id
    ).order_by(Contribution.created_at.desc()).all()
    
    if request.method == 'POST':
        if existing_grade and existing_grade.is_final:
            flash('This grade has been finalized and cannot be changed.', 'warning')
            return redirect(url_for('dashboard.grade_project', project_id=project_id))
        
        try:
            grade_value = float(request.form.get('grade', 0))
            contribution_score = float(request.form.get('contribution_score', 0)) if request.form.get('contribution_score') else None
            quality_score = float(request.form.get('quality_score', 0)) if request.form.get('quality_score') else None
            teamwork_score = float(request.form.get('teamwork_score', 0)) if request.form.get('teamwork_score') else None
            timeliness_score = float(request.form.get('timeliness_score', 0)) if request.form.get('timeliness_score') else None
            feedback = request.form.get('feedback', '')
            is_final = request.form.get('is_final') == 'on'
            
            if existing_grade:
                existing_grade.grade = grade_value
                existing_grade.letter_grade = ProjectGrade.calculate_letter_grade(grade_value)
                existing_grade.contribution_score = contribution_score
                existing_grade.quality_score = quality_score
                existing_grade.teamwork_score = teamwork_score
                existing_grade.timeliness_score = timeliness_score
                existing_grade.feedback = feedback
                existing_grade.is_final = is_final
            else:
                new_grade = ProjectGrade(
                    project_id=project_id,
                    student_id=student_id,
                    graded_by_id=current_user.id,
                    grade=grade_value,
                    letter_grade=ProjectGrade.calculate_letter_grade(grade_value),
                    contribution_score=contribution_score,
                    quality_score=quality_score,
                    teamwork_score=teamwork_score,
                    timeliness_score=timeliness_score,
                    feedback=feedback,
                    is_final=is_final
                )
                db.session.add(new_grade)
            
            db.session.commit()
            flash(f'Grade {"finalized" if is_final else "saved"} for {student.full_name}.', 'success')
            return redirect(url_for('dashboard.grade_project', project_id=project_id))
            
        except ValueError:
            flash('Invalid grade value. Please enter a number.', 'danger')
    
    return render_template('dashboard/grade_student.html',
                         project=project,
                         student=student,
                         membership=membership,
                         contributions=contributions,
                         existing_grade=existing_grade)


@dashboard_bp.route('/project/<int:project_id>/contributions')
@login_required
@lecturer_required
def project_contributions(project_id):
    """View all contributions (changes) made to a project."""
    project = Project.query.get_or_404(project_id)
    
    # Allow if lecturer owns the project OR is in same department as the project owner
    is_owner = project.owner_id == current_user.id
    is_dept_lecturer = (current_user.department_id and 
                        project.owner and 
                        project.owner.department_id == current_user.department_id)
    
    if not is_owner and not is_dept_lecturer:
        flash('You do not have permission to view this project.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    # Get all contributions ordered by date
    contributions = Contribution.query.filter_by(project_id=project_id)\
        .order_by(Contribution.created_at.desc()).all()
    
    # Group by user
    contributions_by_user = {}
    for contrib in contributions:
        if contrib.user_id not in contributions_by_user:
            contributions_by_user[contrib.user_id] = {
                'user': contrib.contributor,
                'contributions': [],
                'total_hours': 0,
                'count': 0
            }
        contributions_by_user[contrib.user_id]['contributions'].append(contrib)
        contributions_by_user[contrib.user_id]['total_hours'] += contrib.hours_spent or 0
        contributions_by_user[contrib.user_id]['count'] += 1
    
    # Get timeline data
    timeline = contributions[:50]  # Last 50 contributions
    
    return render_template('dashboard/project_contributions.html',
                         project=project,
                         contributions=contributions,
                         contributions_by_user=contributions_by_user,
                         timeline=timeline)


# API endpoints for dashboard charts
@dashboard_bp.route('/api/stats/contributions')
@login_required
def contribution_stats():
    """Get contribution statistics for charts."""
    if current_user.is_lecturer:
        own_project_ids = [p.id for p in Project.query.filter_by(owner_id=current_user.id).all()]
        dept_project_ids = []
        if current_user.department_id:
            dept_student_ids = [u.id for u in User.query.filter(
                User.department_id == current_user.department_id
            ).join(User.roles).filter(Role.name == 'student').all()]
            if dept_student_ids:
                dept_project_ids = [p.id for p in Project.query.filter(
                    Project.owner_id.in_(dept_student_ids)
                ).all()]
        project_ids = list(set(own_project_ids + dept_project_ids))
        contributions = Contribution.query.filter(Contribution.project_id.in_(project_ids))
    else:
        contributions = Contribution.query.filter_by(user_id=current_user.id)
    
    # By type
    by_type = db.session.query(
        Contribution.contribution_type,
        func.count(Contribution.id).label('count')
    ).filter(Contribution.id.in_([c.id for c in contributions]))\
    .group_by(Contribution.contribution_type).all()
    
    # By date (last 30 days)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    by_date = db.session.query(
        func.date(Contribution.created_at).label('date'),
        func.count(Contribution.id).label('count')
    ).filter(
        Contribution.id.in_([c.id for c in contributions]),
        Contribution.created_at >= thirty_days_ago
    ).group_by(func.date(Contribution.created_at)).all()
    
    return jsonify({
        'by_type': [{'type': t or 'Other', 'count': c} for t, c in by_type],
        'by_date': [{'date': str(d), 'count': c} for d, c in by_date]
    })


@dashboard_bp.route('/api/stats/milestones')
@login_required
def milestone_stats():
    """Get milestone statistics for charts."""
    if current_user.is_lecturer:
        own_project_ids = [p.id for p in Project.query.filter_by(owner_id=current_user.id).all()]
        dept_project_ids = []
        if current_user.department_id:
            dept_student_ids = [u.id for u in User.query.filter(
                User.department_id == current_user.department_id
            ).join(User.roles).filter(Role.name == 'student').all()]
            if dept_student_ids:
                dept_project_ids = [p.id for p in Project.query.filter(
                    Project.owner_id.in_(dept_student_ids)
                ).all()]
        project_ids = list(set(own_project_ids + dept_project_ids))
    else:
        memberships = ProjectMember.query.filter_by(user_id=current_user.id, status='active').all()
        project_ids = [m.project_id for m in memberships]
    
    milestones = Milestone.query.filter(Milestone.project_id.in_(project_ids))
    
    # By status
    by_status = db.session.query(
        Milestone.status,
        func.count(Milestone.id).label('count')
    ).filter(Milestone.project_id.in_(project_ids))\
    .group_by(Milestone.status).all()
    
    # Upcoming deadlines
    upcoming = milestones.filter(
        Milestone.status != 'completed',
        Milestone.due_date >= datetime.now(timezone.utc)
    ).order_by(Milestone.due_date).limit(10).all()
    
    return jsonify({
        'by_status': [{'status': s, 'count': c} for s, c in by_status],
        'upcoming': [{
            'id': m.id,
            'title': m.title,
            'project': m.project.title,
            'due_date': m.due_date.isoformat(),
            'priority': m.priority
        } for m in upcoming]
    })


# ============== STUDENT VIEWING ROUTES ==============

@dashboard_bp.route('/students')
@login_required
@lecturer_required
def view_all_students():
    """View all students across lecturer's department projects."""
    # Get owned projects + department projects
    owned_projects = Project.query.filter_by(owner_id=current_user.id).all()
    dept_projects = []
    if current_user.department_id:
        dept_projects = Project.query.filter(
            Project.department_id == current_user.department_id,
            Project.owner_id != current_user.id
        ).all()
    
    seen_ids = set()
    projects = []
    for p in owned_projects + dept_projects:
        if p.id not in seen_ids:
            seen_ids.add(p.id)
            projects.append(p)
    
    students_data = []
    seen_students = set()
    
    for project in projects:
        # Include project members
        members = project.members.filter_by(status='active').all()
        for member in members:
            if member.user_id not in seen_students and member.user.is_student:
                seen_students.add(member.user_id)
                
                # Get contribution count across all monitored projects
                contribution_count = Contribution.query.filter(
                    Contribution.user_id == member.user_id,
                    Contribution.project_id.in_([p.id for p in projects])
                ).count()
                
                # Get projects this student is involved in
                student_projects = []
                for p in projects:
                    if p.owner_id == member.user_id or p.members.filter_by(user_id=member.user_id, status='active').first():
                        student_projects.append(p)
                
                students_data.append({
                    'student': member.user,
                    'projects': student_projects,
                    'contribution_count': contribution_count,
                    'joined_at': member.joined_at
                })
        
        # Also include project owner if they are a student
        if project.owner and project.owner.is_student and project.owner_id not in seen_students:
            seen_students.add(project.owner_id)
            
            contribution_count = Contribution.query.filter(
                Contribution.user_id == project.owner_id,
                Contribution.project_id.in_([p.id for p in projects])
            ).count()
            
            student_projects = [p for p in projects if p.owner_id == project.owner_id or 
                              p.members.filter_by(user_id=project.owner_id, status='active').first()]
            
            students_data.append({
                'student': project.owner,
                'projects': student_projects,
                'contribution_count': contribution_count,
                'joined_at': project.created_at
            })
    
    # Sort by name
    students_data.sort(key=lambda x: x['student'].full_name)
    
    return render_template('dashboard/all_students.html',
                         students_data=students_data,
                         total_students=len(students_data))


@dashboard_bp.route('/students/<int:student_id>')
@login_required
@lecturer_required
def view_student_details(student_id):
    """View a specific student's progress and work."""
    student = User.query.get_or_404(student_id)
    
    # Get lecturer's owned projects + department projects
    lecturer_projects = Project.query.filter_by(owner_id=current_user.id).all()
    dept_projects = []
    if current_user.department_id:
        dept_projects = Project.query.filter(
            Project.department_id == current_user.department_id,
            Project.owner_id != current_user.id
        ).all()
    
    seen_ids = set()
    all_projects = []
    for p in lecturer_projects + dept_projects:
        if p.id not in seen_ids:
            seen_ids.add(p.id)
            all_projects.append(p)
    project_ids = [p.id for p in all_projects]
    
    # Check if student is in any of the lecturer's monitored projects
    memberships = ProjectMember.query.filter(
        ProjectMember.user_id == student_id,
        ProjectMember.project_id.in_(project_ids),
        ProjectMember.status == 'active'
    ).all()
    
    # Also check if student owns any of these projects
    owned_by_student = [p for p in all_projects if p.owner_id == student_id]
    
    if not memberships and not owned_by_student:
        flash('This student is not in any of your monitored projects.', 'warning')
        return redirect(url_for('dashboard.view_all_students'))
    
    # Get student's projects (memberships + owned)
    student_projects = []
    seen_project_ids = set()
    
    for membership in memberships:
        project = membership.project
        seen_project_ids.add(project.id)
        contributions = Contribution.query.filter_by(
            project_id=project.id,
            user_id=student_id
        ).order_by(Contribution.created_at.desc()).all()
        
        # Get project updates by this student
        student_updates = ProjectUpdate.query.filter_by(
            project_id=project.id,
            author_id=student_id
        ).order_by(ProjectUpdate.created_at.desc()).all()
        
        comments = ProjectComment.query.filter_by(
            project_id=project.id,
            target_student_id=student_id
        ).order_by(ProjectComment.created_at.desc()).all()
        
        student_projects.append({
            'project': project,
            'membership': membership,
            'contributions': contributions,
            'updates': student_updates,
            'comments': comments,
            'total_hours': sum(c.hours_spent or 0 for c in contributions)
        })
    
    # Add projects owned by the student
    for project in owned_by_student:
        if project.id not in seen_project_ids:
            contributions = Contribution.query.filter_by(
                project_id=project.id,
                user_id=student_id
            ).order_by(Contribution.created_at.desc()).all()
            
            student_updates = ProjectUpdate.query.filter_by(
                project_id=project.id,
                author_id=student_id
            ).order_by(ProjectUpdate.created_at.desc()).all()
            
            comments = ProjectComment.query.filter_by(
                project_id=project.id,
                target_student_id=student_id
            ).order_by(ProjectComment.created_at.desc()).all()
            
            student_projects.append({
                'project': project,
                'membership': None,
                'contributions': contributions,
                'updates': student_updates,
                'comments': comments,
                'total_hours': sum(c.hours_spent or 0 for c in contributions),
                'is_owner': True
            })
    
    return render_template('dashboard/student_details.html',
                         student=student,
                         student_projects=student_projects)


@dashboard_bp.route('/project/<int:project_id>/comment', methods=['POST'])
@login_required
@lecturer_required
def add_project_comment(project_id):
    """Add a comment to a project or student's work."""
    project = Project.query.get_or_404(project_id)
    
    if project.owner_id != current_user.id:
        flash('You do not have permission to comment on this project.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    content = request.form.get('content', '').strip()
    comment_type = request.form.get('comment_type', 'project')
    target_student_id = request.form.get('target_student_id', type=int)
    contribution_id = request.form.get('contribution_id', type=int)
    
    if not content:
        flash('Comment cannot be empty.', 'warning')
        return redirect(request.referrer or url_for('dashboard.index'))
    
    comment = ProjectComment(
        content=content,
        comment_type=comment_type,
        project_id=project_id,
        author_id=current_user.id,
        target_student_id=target_student_id if target_student_id else None,
        contribution_id=contribution_id if contribution_id else None
    )
    
    db.session.add(comment)
    db.session.commit()
    
    # Send notification to the student if comment is targeted
    if target_student_id:
        from app.utils.notifications import send_notification
        send_notification(
            user_id=target_student_id,
            title='New Comment from Lecturer',
            message=f'{current_user.full_name} commented on your work in "{project.title}".',
            notification_type='project',
            action_url=url_for('collaboration.project_workspace', project_id=project_id),
            sender_id=current_user.id,
            project_id=project_id
        )
    
    flash('Comment added successfully.', 'success')
    return redirect(request.referrer or url_for('dashboard.view_student_details', student_id=target_student_id if target_student_id else 0))


@dashboard_bp.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
@lecturer_required
def delete_comment(comment_id):
    """Delete a comment."""
    comment = ProjectComment.query.get_or_404(comment_id)
    
    if comment.author_id != current_user.id:
        flash('You can only delete your own comments.', 'danger')
        return redirect(request.referrer or url_for('dashboard.index'))
    
    db.session.delete(comment)
    db.session.commit()
    
    flash('Comment deleted.', 'success')
    return redirect(request.referrer or url_for('dashboard.index'))

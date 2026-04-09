"""Database models for the collaboration platform."""
from datetime import datetime, timezone
import secrets
from flask_login import UserMixin
from app import db, bcrypt, login_manager


# Association tables
user_roles = db.Table('user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True)
)

project_skills = db.Table('project_skills',
    db.Column('project_id', db.Integer, db.ForeignKey('projects.id'), primary_key=True),
    db.Column('skill_id', db.Integer, db.ForeignKey('skills.id'), primary_key=True)
)

user_skills = db.Table('user_skills',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('skill_id', db.Integer, db.ForeignKey('skills.id'), primary_key=True)
)

project_tools = db.Table('project_tools',
    db.Column('project_id', db.Integer, db.ForeignKey('projects.id'), primary_key=True),
    db.Column('tool_id', db.Integer, db.ForeignKey('tools.id'), primary_key=True)
)


class Role(db.Model):
    """User roles (admin, lecturer, student)."""
    __tablename__ = 'roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<Role {self.name}>'


class Department(db.Model):
    """Academic departments."""
    __tablename__ = 'departments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    code = db.Column(db.String(10), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    users = db.relationship('User', backref='department', lazy='dynamic')
    courses = db.relationship('Course', backref='department', lazy='dynamic')
    
    def __repr__(self):
        return f'<Department {self.code}>'


class Course(db.Model):
    """Academic courses."""
    __tablename__ = 'courses'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.Text)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    projects = db.relationship('Project', backref='course', lazy='dynamic')
    
    def __repr__(self):
        return f'<Course {self.code}>'


class Skill(db.Model):
    """Skills that can be associated with projects and users."""
    __tablename__ = 'skills'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    category = db.Column(db.String(50))
    
    def __repr__(self):
        return f'<Skill {self.name}>'


class Tool(db.Model):
    """Tools and technologies used in projects."""
    __tablename__ = 'tools'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    category = db.Column(db.String(50))
    description = db.Column(db.String(200))
    
    def __repr__(self):
        return f'<Tool {self.name}>'


class User(UserMixin, db.Model):
    """User model for both students and lecturers."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    student_id = db.Column(db.String(20), unique=True, index=True)  # For students
    employee_id = db.Column(db.String(20), unique=True, index=True)  # For faculty
    phone = db.Column(db.String(20))
    bio = db.Column(db.Text)
    avatar = db.Column(db.Text)  # Stores base64 data URL for profile picture
    
    # Status flags
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    availability_status = db.Column(db.String(20), default='available')  # available, busy, away, offline
    last_seen = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime)
    
    # Foreign keys
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    
    # Relationships
    roles = db.relationship('Role', secondary=user_roles, backref=db.backref('users', lazy='dynamic'))
    skills = db.relationship('Skill', secondary=user_skills, backref=db.backref('users', lazy='dynamic'))
    
    # Project relationships
    owned_projects = db.relationship('Project', backref='owner', lazy='dynamic', foreign_keys='Project.owner_id')
    applications = db.relationship('ProjectApplication', backref='applicant', lazy='dynamic', foreign_keys='ProjectApplication.user_id')
    memberships = db.relationship('ProjectMember', backref='user', lazy='dynamic')
    contributions = db.relationship('Contribution', backref='contributor', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic', foreign_keys='Notification.user_id')
    
    def set_password(self, password):
        """Hash and set the password."""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    def check_password(self, password):
        """Check if the provided password matches."""
        return bcrypt.check_password_hash(self.password_hash, password)
    
    @property
    def full_name(self):
        """Return the user's full name."""
        return f'{self.first_name} {self.last_name}'
    
    def has_role(self, role_name):
        """Check if user has a specific role."""
        return any(role.name == role_name for role in self.roles)
    
    @property
    def is_lecturer(self):
        """Check if user is a lecturer."""
        return self.has_role('lecturer')
    
    @property
    def is_student(self):
        """Check if user is a student."""
        return self.has_role('student')
    
    @property
    def is_admin(self):
        """Check if user is an admin."""
        return self.has_role('admin')
    
    @property
    def is_online(self):
        """Check if user was active in the last 5 minutes."""
        if not self.last_seen:
            return False
        last = self.last_seen
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - last).total_seconds() < 300

    def get_unread_notifications_count(self):
        """Get count of unread notifications."""
        return Notification.query.filter_by(user_id=self.id, is_read=False).count()
    
    def __repr__(self):
        return f'<User {self.email}>'


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login."""
    return User.query.get(int(user_id))


class Project(db.Model):
    """Project model for faculty-posted projects."""
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    goals = db.Column(db.Text)
    expected_outcomes = db.Column(db.Text)
    
    # Project settings
    status = db.Column(db.String(20), default='draft')  # draft, open, in_progress, completed, cancelled
    visibility = db.Column(db.String(20), default='public')  # public, department, private
    max_team_size = db.Column(db.Integer, default=5)
    min_team_size = db.Column(db.Integer, default=1)
    invite_code = db.Column(db.String(32), unique=True, index=True)  # For shareable invite links
    
    # Dates
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    application_deadline = db.Column(db.DateTime)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Foreign keys
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    
    # Relationships
    skills = db.relationship('Skill', secondary=project_skills, backref=db.backref('projects', lazy='dynamic'))
    tools = db.relationship('Tool', secondary=project_tools, backref=db.backref('projects', lazy='dynamic'))
    milestones = db.relationship('Milestone', backref='project', lazy='dynamic', order_by='Milestone.due_date')
    applications = db.relationship('ProjectApplication', backref='project', lazy='dynamic')
    members = db.relationship('ProjectMember', backref='project', lazy='dynamic')
    files = db.relationship('ProjectFile', backref='project', lazy='dynamic')
    updates = db.relationship('ProjectUpdate', backref='project', lazy='dynamic', order_by='desc(ProjectUpdate.created_at)')
    contributions = db.relationship('Contribution', backref='project', lazy='dynamic')
    feedback = db.relationship('Feedback', backref='project', lazy='dynamic')
    
    def get_department(self):
        """Get project department."""
        if self.department_id:
            return Department.query.get(self.department_id)
        return None
    
    @property
    def progress(self):
        """Calculate project progress based on milestones and tasks.
        
        Uses milestones if any exist (completed / total).
        Falls back to tasks if no milestones (completed / total).
        Falls back to contribution-based estimate if neither exist.
        """
        # Primary: milestone-based progress
        milestones = self.milestones.all()
        if milestones:
            completed = sum(1 for m in milestones if m.status == 'completed')
            return int((completed / len(milestones)) * 100)
        
        # Secondary: task-based progress
        tasks = self.tasks.all()
        if tasks:
            completed = sum(1 for t in tasks if t.status == 'completed')
            return int((completed / len(tasks)) * 100)
        
        # Tertiary: contribution-based estimate (has any work been done?)
        contribution_count = self.contributions.count()
        if contribution_count > 0:
            # Cap at 50% since without milestones/tasks we can't measure completion
            return min(int(contribution_count * 10), 50)
        
        return 0
    
    @property
    def team_count(self):
        """Get current team size."""
        return self.members.filter_by(status='active').count()
    
    @property
    def pending_applications(self):
        """Get count of pending applications."""
        return self.applications.filter_by(status='pending').count()
    
    @property
    def is_accepting_applications(self):
        """Check if project is accepting new applications."""
        if self.status != 'open':
            return False
        if self.application_deadline and datetime.now(timezone.utc) > self.application_deadline:
            return False
        if self.max_team_size and self.max_team_size > 0 and self.team_count >= self.max_team_size:
            return False
        return True
    
    def generate_invite_code(self):
        """Generate a unique invite code for the project."""
        self.invite_code = secrets.token_urlsafe(16)
        return self.invite_code
    
    def regenerate_invite_code(self):
        """Regenerate the invite code."""
        return self.generate_invite_code()
    
    def __repr__(self):
        return f'<Project {self.title}>'


class Milestone(db.Model):
    """Project milestones for tracking progress."""
    __tablename__ = 'milestones'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, in_progress, completed, overdue
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, critical
    
    # Dates
    due_date = db.Column(db.DateTime, nullable=False)
    completed_at = db.Column(db.DateTime)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Foreign keys
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    assigned_to = db.relationship('User', backref='assigned_milestones')
    submissions = db.relationship('MilestoneSubmission', backref='milestone', lazy='dynamic')
    
    @property
    def is_overdue(self):
        """Check if milestone is overdue."""
        if self.status == 'completed':
            return False
        due = self.due_date
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > due

    @property
    def days_overdue(self):
        """Return number of days overdue, or 0 if not overdue."""
        if self.status == 'completed' or not self.due_date:
            return 0
        due = self.due_date
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        delta = (datetime.now(timezone.utc) - due).days
        return max(delta, 0)

    @property
    def time_status(self):
        """Human-readable time status string."""
        if self.status == 'completed':
            return 'Completed'
        if not self.due_date:
            return 'No deadline'
        due = self.due_date
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        delta = (due - datetime.now(timezone.utc)).days
        if delta < 0:
            return f'Overdue by {abs(delta)} day{"s" if abs(delta) != 1 else ""}'
        elif delta == 0:
            return 'Due today'
        elif delta == 1:
            return 'Due tomorrow'
        else:
            return f'{delta} days left'
    
    def __repr__(self):
        return f'<Milestone {self.title}>'


class MilestoneSubmission(db.Model):
    """Submissions for milestone completion."""
    __tablename__ = 'milestone_submissions'
    
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    feedback = db.Column(db.Text)
    
    # Timestamps
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    reviewed_at = db.Column(db.DateTime)
    
    # Foreign keys
    milestone_id = db.Column(db.Integer, db.ForeignKey('milestones.id'), nullable=False)
    submitted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    submitted_by = db.relationship('User', foreign_keys=[submitted_by_id], backref='milestone_submissions')
    reviewed_by = db.relationship('User', foreign_keys=[reviewed_by_id])
    files = db.relationship('SubmissionFile', backref='submission', lazy='dynamic')


class SubmissionFile(db.Model):
    """Files attached to milestone submissions."""
    __tablename__ = 'submission_files'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50))
    file_size = db.Column(db.Integer)
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    submission_id = db.Column(db.Integer, db.ForeignKey('milestone_submissions.id'), nullable=False)


class ProjectApplication(db.Model):
    """Applications from students to join projects."""
    __tablename__ = 'project_applications'
    
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, withdrawn
    
    # Timestamps
    applied_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    reviewed_at = db.Column(db.DateTime)
    
    # Foreign keys
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    reviewed_by = db.relationship('User', foreign_keys=[reviewed_by_id])
    
    def __repr__(self):
        return f'<Application {self.user_id} -> {self.project_id}>'


class ProjectMember(db.Model):
    """Project team members."""
    __tablename__ = 'project_members'
    
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(50), default='member')  # member, lead, contributor
    status = db.Column(db.String(20), default='active')  # active, inactive, removed
    
    # Timestamps
    joined_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    left_at = db.Column(db.DateTime)
    
    # Foreign keys
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Note: 'user' relationship comes from User.memberships backref
    
    __table_args__ = (
        db.UniqueConstraint('project_id', 'user_id', name='unique_project_member'),
    )
    
    def __repr__(self):
        return f'<ProjectMember {self.user_id} in {self.project_id}>'


class ProjectFile(db.Model):
    """Files associated with projects (version controlled)."""
    __tablename__ = 'project_files'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50))
    file_size = db.Column(db.Integer)
    version = db.Column(db.Integer, default=1)
    description = db.Column(db.Text)
    is_current = db.Column(db.Boolean, default=True)
    
    # Timestamps
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Foreign keys
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('project_files.id'))  # For version tracking
    
    # Relationships
    uploaded_by = db.relationship('User', backref='uploaded_files')
    versions = db.relationship('ProjectFile', backref=db.backref('parent', remote_side=[id]))
    
    def __repr__(self):
        return f'<ProjectFile {self.original_filename} v{self.version}>'


class ProjectUpdate(db.Model):
    """Project activity updates and announcements."""
    __tablename__ = 'project_updates'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    update_type = db.Column(db.String(20), default='general')  # general, milestone, announcement, progress
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Foreign keys
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    author = db.relationship('User', backref='project_updates')
    
    def __repr__(self):
        return f'<ProjectUpdate {self.title}>'


class Contribution(db.Model):
    """Track individual contributions to projects."""
    __tablename__ = 'contributions'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    description = db.Column(db.Text, nullable=False)
    contribution_type = db.Column(db.String(50))  # code, documentation, design, research, testing
    hours_spent = db.Column(db.Float)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    date = db.Column(db.Date, default=lambda: datetime.now(timezone.utc).date())
    
    # Foreign keys
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    milestone_id = db.Column(db.Integer, db.ForeignKey('milestones.id'))
    
    # Note: 'contributor' relationship comes from User.contributions backref
    # Note: 'project' relationship comes from Project.contributions backref
    milestone = db.relationship('Milestone', backref='contributions')
    
    def __repr__(self):
        return f'<Contribution {self.id} by {self.user_id}>'


class Feedback(db.Model):
    """Faculty feedback on project progress and submissions."""
    __tablename__ = 'feedback'
    
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer)  # 1-5 rating (optional)
    feedback_type = db.Column(db.String(20), default='general')  # general, milestone, final
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Foreign keys
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    milestone_id = db.Column(db.Integer, db.ForeignKey('milestones.id'))
    
    # Relationships
    author = db.relationship('User', foreign_keys=[author_id], backref='given_feedback')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_feedback')
    milestone = db.relationship('Milestone', backref='feedback')
    
    def __repr__(self):
        return f'<Feedback {self.id}>'


class Notification(db.Model):
    """User notifications."""
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50))  # application, deadline, update, feedback, system
    is_read = db.Column(db.Boolean, default=False)
    
    # Action link (optional)
    action_url = db.Column(db.String(500))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    read_at = db.Column(db.DateTime)
    
    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    
    # Relationships
    sender = db.relationship('User', foreign_keys=[sender_id])
    project = db.relationship('Project', backref='notifications')
    
    def mark_as_read(self):
        """Mark notification as read."""
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.now(timezone.utc)
            db.session.commit()
    
    def __repr__(self):
        return f'<Notification {self.id} for {self.user_id}>'


class AuditLog(db.Model):
    """Audit log for tracking important actions."""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    user = db.relationship('User', backref='audit_logs')
    
    @classmethod
    def log(cls, action, user_id=None, entity_type=None, entity_id=None, details=None, request=None):
        """Create an audit log entry."""
        import json
        # Convert details to JSON string if it's a dict
        if isinstance(details, dict):
            details = json.dumps(details)
        
        entry = cls(
            action=action,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=request.remote_addr if request else None,
            user_agent=request.user_agent.string[:500] if request and request.user_agent else None
        )
        db.session.add(entry)
        return entry


class ProjectInvitation(db.Model):
    """Invitations to join projects."""
    __tablename__ = 'project_invitations'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120))  # Email for external invites
    status = db.Column(db.String(20), default='pending')  # pending, accepted, declined, expired
    message = db.Column(db.Text)  # Invitation message
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime)  # Expiration date
    responded_at = db.Column(db.DateTime)
    
    # Foreign keys
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    invited_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    invited_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # If inviting existing user
    
    # Relationships
    project = db.relationship('Project', backref=db.backref('invitations', lazy='dynamic'))
    invited_by = db.relationship('User', foreign_keys=[invited_by_id], backref='sent_invitations')
    invited_user = db.relationship('User', foreign_keys=[invited_user_id], backref='received_invitations')
    
    def accept(self):
        """Accept the invitation."""
        self.status = 'accepted'
        self.responded_at = datetime.now(timezone.utc)
        
    def decline(self):
        """Decline the invitation."""
        self.status = 'declined'
        self.responded_at = datetime.now(timezone.utc)
    
    @property
    def is_expired(self):
        """Check if invitation is expired."""
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False
    
    def __repr__(self):
        return f'<ProjectInvitation {self.id} for project {self.project_id}>'


class Task(db.Model):
    """Tasks within a project that can be assigned to team members."""
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='todo')  # todo, in_progress, review, completed
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, urgent
    
    # Dates
    due_date = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Foreign keys
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    milestone_id = db.Column(db.Integer, db.ForeignKey('milestones.id'))
    
    # Relationships
    project = db.relationship('Project', backref=db.backref('tasks', lazy='dynamic', order_by='Task.due_date'))
    created_by = db.relationship('User', foreign_keys=[created_by_id], backref='created_tasks')
    assigned_to = db.relationship('User', foreign_keys=[assigned_to_id], backref='assigned_tasks')
    milestone = db.relationship('Milestone', backref='tasks')
    
    @property
    def is_overdue(self):
        """Check if task is overdue."""
        if self.status == 'completed':
            return False
        if self.due_date:
            return datetime.now(timezone.utc) > self.due_date
        return False
    
    def __repr__(self):
        return f'<Task {self.title}>'


class ProjectGrade(db.Model):
    """Grades assigned to students for their project work."""
    __tablename__ = 'project_grades'
    
    id = db.Column(db.Integer, primary_key=True)
    grade = db.Column(db.Float, nullable=False)  # Numeric grade (e.g., 0-100)
    letter_grade = db.Column(db.String(5))  # A, B+, C, etc.
    feedback = db.Column(db.Text)  # Detailed feedback from lecturer
    
    # Grade components (optional breakdown)
    contribution_score = db.Column(db.Float)  # Score based on contributions
    quality_score = db.Column(db.Float)  # Code/work quality
    teamwork_score = db.Column(db.Float)  # Team collaboration
    timeliness_score = db.Column(db.Float)  # Meeting deadlines
    
    # Final grade status
    is_final = db.Column(db.Boolean, default=False)  # Locked/finalized
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Foreign keys
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # Student being graded
    graded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # Lecturer
    
    # Relationships
    project = db.relationship('Project', backref=db.backref('grades', lazy='dynamic'))
    student = db.relationship('User', foreign_keys=[student_id], backref='project_grades')
    graded_by = db.relationship('User', foreign_keys=[graded_by_id], backref='assigned_grades')
    
    __table_args__ = (
        db.UniqueConstraint('project_id', 'student_id', name='unique_project_student_grade'),
    )
    
    @staticmethod
    def calculate_letter_grade(score):
        """Convert numeric score to letter grade."""
        if score >= 90:
            return 'A+'
        elif score >= 80:
            return 'A'
        elif score >= 75:
            return 'B+'
        elif score >= 70:
            return 'B'
        elif score >= 65:
            return 'C+'
        elif score >= 60:
            return 'C'
        elif score >= 55:
            return 'D+'
        elif score >= 50:
            return 'D'
        else:
            return 'F'
    
    def __repr__(self):
        return f'<ProjectGrade {self.grade} for student {self.student_id} on project {self.project_id}>'


class ProjectComment(db.Model):
    """Lecturer comments on student projects."""
    __tablename__ = 'project_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    
    # Type of comment: 'project', 'contribution', 'general'
    comment_type = db.Column(db.String(20), default='project')
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))
    
    # Foreign keys
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # Lecturer who made the comment
    target_student_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # Optional: specific student
    contribution_id = db.Column(db.Integer, db.ForeignKey('contributions.id'))  # Optional: specific contribution
    
    # Relationships
    project = db.relationship('Project', backref=db.backref('comments', lazy='dynamic', cascade='all, delete-orphan'))
    author = db.relationship('User', foreign_keys=[author_id], backref='authored_comments')
    target_student = db.relationship('User', foreign_keys=[target_student_id], backref='received_comments')
    contribution = db.relationship('Contribution', backref=db.backref('comments', lazy='dynamic'))
    
    def __repr__(self):
        return f'<ProjectComment {self.id} by {self.author_id} on project {self.project_id}>'


class ProjectMessage(db.Model):
    """Messages between lecturers and students on projects."""
    __tablename__ = 'project_messages'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Foreign keys
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('project_messages.id'))  # For replies

    # Relationships
    project = db.relationship('Project', backref=db.backref('messages', lazy='dynamic', order_by='ProjectMessage.created_at'))
    sender = db.relationship('User', backref='sent_messages')
    replies = db.relationship('ProjectMessage', backref=db.backref('parent', remote_side=[id]), lazy='dynamic', order_by='ProjectMessage.created_at')

    def __repr__(self):
        return f'<ProjectMessage {self.id} by {self.sender_id} on project {self.project_id}>'
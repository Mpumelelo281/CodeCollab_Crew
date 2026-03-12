"""WTForms form definitions."""
from datetime import datetime, date
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (StringField, PasswordField, BooleanField, TextAreaField, 
                    SelectField, IntegerField, FloatField, DateField, 
                    DateTimeField, SelectMultipleField, HiddenField)
from wtforms.validators import (DataRequired, Email, EqualTo, Length, 
                               Optional, NumberRange, ValidationError)


# Authentication Forms
class LoginForm(FlaskForm):
    """User login form."""
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Please enter a valid email address')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required')
    ])
    remember_me = BooleanField('Remember Me')


class RegistrationForm(FlaskForm):
    """User registration form."""
    email = StringField('Institutional Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Please enter a valid email address'),
        Length(max=120)
    ])
    first_name = StringField('First Name', validators=[
        DataRequired(message='First name is required'),
        Length(min=2, max=50)
    ])
    last_name = StringField('Last Name', validators=[
        DataRequired(message='Last name is required'),
        Length(min=2, max=50)
    ])
    role = SelectField('I am a', choices=[
        ('student', 'Student'),
        ('lecturer', 'Faculty/Lecturer')
    ], validators=[DataRequired()])
    institution_id = StringField('Student/Employee ID', validators=[
        DataRequired(message='Institution ID is required'),
        Length(min=4, max=20)
    ])
    department = SelectField('Department', coerce=int, validators=[Optional()])
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required'),
        Length(min=8, message='Password must be at least 8 characters')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(message='Please confirm your password'),
        EqualTo('password', message='Passwords must match')
    ])
    agree_terms = BooleanField('I agree to the Terms of Service', validators=[
        DataRequired(message='You must agree to the terms')
    ])


class ForgotPasswordForm(FlaskForm):
    """Forgot password form."""
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Please enter a valid email address')
    ])


class ResetPasswordForm(FlaskForm):
    """Password reset form."""
    password = PasswordField('New Password', validators=[
        DataRequired(message='Password is required'),
        Length(min=8, message='Password must be at least 8 characters')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(message='Please confirm your password'),
        EqualTo('password', message='Passwords must match')
    ])


class ChangePasswordForm(FlaskForm):
    """Change password form."""
    current_password = PasswordField('Current Password', validators=[
        DataRequired(message='Current password is required')
    ])
    new_password = PasswordField('New Password', validators=[
        DataRequired(message='New password is required'),
        Length(min=8, message='Password must be at least 8 characters')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(message='Please confirm your password'),
        EqualTo('new_password', message='Passwords must match')
    ])


# Profile Forms
class ProfileForm(FlaskForm):
    """User profile edit form."""
    first_name = StringField('First Name', validators=[
        DataRequired(message='First name is required'),
        Length(min=2, max=50)
    ])
    last_name = StringField('Last Name', validators=[
        DataRequired(message='Last name is required'),
        Length(min=2, max=50)
    ])
    phone = StringField('Phone Number', validators=[
        Optional(),
        Length(max=20)
    ])
    bio = TextAreaField('Bio', validators=[
        Optional(),
        Length(max=500)
    ])
    department = SelectField('Department', coerce=int, validators=[Optional()])
    skills = StringField('Skills (comma-separated)', validators=[Optional()])
    avatar = FileField('Profile Picture', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only!')
    ])


# Project Forms
class ProjectForm(FlaskForm):
    """Project creation/edit form."""
    title = StringField('Project Title', validators=[
        DataRequired(message='Project title is required'),
        Length(min=5, max=200, message='Title must be 5-200 characters')
    ])
    description = TextAreaField('Description', validators=[
        DataRequired(message='Description is required')
    ])
    goals = TextAreaField('Project Goals', validators=[
        Optional(),
        Length(max=2000)
    ])
    expected_outcomes = TextAreaField('Expected Outcomes', validators=[
        Optional(),
        Length(max=2000)
    ])
    status = SelectField('Status', choices=[
        ('draft', 'Draft'),
        ('open', 'Open for Applications'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], default='draft')
    visibility = SelectField('Visibility', choices=[
        ('public', 'Public - Visible to all'),
        ('department', 'Department - Visible to department members'),
        ('private', 'Private - Visible only to team members')
    ], default='public')
    department = SelectField('Department', coerce=int, validators=[DataRequired()])
    course = SelectField('Related Course', coerce=int, validators=[Optional()])
    skills = StringField('Required Skills (comma-separated)', validators=[
        Optional(),
        Length(max=500)
    ])
    tools = StringField('Tools/Technologies (comma-separated)', validators=[
        Optional(),
        Length(max=500)
    ])
    team_size = IntegerField('Team Size', validators=[
        Optional(),
        NumberRange(min=0)
    ], default=0)  # 0 = unlimited/flexible
    start_date = DateField('Start Date', validators=[Optional()])
    end_date = DateField('End Date', validators=[Optional()])
    application_deadline = DateTimeField('Application Deadline', 
                                        format='%Y-%m-%dT%H:%M',
                                        validators=[Optional()])
    
    def validate_end_date(self, field):
        """Validate that end date is after start date."""
        if self.start_date.data and field.data:
            if field.data < self.start_date.data:
                raise ValidationError('End date must be after start date')


class ProjectSearchForm(FlaskForm):
    """Project search form."""
    search = StringField('Search', validators=[Optional(), Length(max=100)])
    department = SelectField('Department', coerce=int, validators=[Optional()])
    course = SelectField('Course', coerce=int, validators=[Optional()])
    skills = SelectMultipleField('Skills', coerce=int, validators=[Optional()])
    status = SelectField('Status', choices=[
        ('', 'All Statuses'),
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed')
    ], validators=[Optional()])
    sort = SelectField('Sort By', choices=[
        ('newest', 'Newest First'),
        ('oldest', 'Oldest First'),
        ('deadline', 'Application Deadline'),
        ('title', 'Title A-Z')
    ], default='newest')


# Application Form
class ApplicationForm(FlaskForm):
    """Project application form."""
    message = TextAreaField('Cover Letter / Message', validators=[
        Optional(),
        Length(max=2000, message='Message must be under 2000 characters')
    ], description='Explain why you want to join this project and what you can contribute.')


# Milestone Forms
class MilestoneForm(FlaskForm):
    """Milestone creation/edit form."""
    title = StringField('Milestone Title', validators=[
        DataRequired(message='Title is required'),
        Length(min=3, max=200)
    ])
    description = TextAreaField('Description', validators=[
        Optional(),
        Length(max=1000)
    ])
    due_date = DateTimeField('Due Date', 
                            format='%Y-%m-%dT%H:%M',
                            validators=[DataRequired()])
    priority = SelectField('Priority', choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], default='medium')
    assigned_to = SelectField('Assign To', coerce=int, validators=[Optional()])
    
    def validate_due_date(self, field):
        """Validate that due date is in the future."""
        if field.data and field.data < datetime.now():
            raise ValidationError('Due date must be in the future')


# Contribution Forms
class ContributionForm(FlaskForm):
    """Contribution log form."""
    description = TextAreaField('Description of Work', validators=[
        DataRequired(message='Description is required'),
        Length(min=10, max=1000, message='Description must be 10-1000 characters')
    ])
    contribution_type = SelectField('Type of Contribution', choices=[
        ('code', 'Code/Development'),
        ('documentation', 'Documentation'),
        ('design', 'Design/UI'),
        ('research', 'Research'),
        ('testing', 'Testing/QA'),
        ('planning', 'Planning/Management'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    hours_spent = FloatField('Hours Spent', validators=[
        Optional(),
        NumberRange(min=0.1, max=24, message='Hours must be between 0.1 and 24')
    ])
    date = DateField('Date', validators=[DataRequired()], default=date.today)
    milestone = SelectField('Related Milestone', coerce=int, validators=[Optional()])


# Project Update Forms
class ProjectUpdateForm(FlaskForm):
    """Project update/announcement form."""
    title = StringField('Title', validators=[
        DataRequired(message='Title is required'),
        Length(min=3, max=200)
    ])
    content = TextAreaField('Content', validators=[
        DataRequired(message='Content is required'),
        Length(min=10, max=5000)
    ])
    update_type = SelectField('Type', choices=[
        ('general', 'General Update'),
        ('milestone', 'Milestone Update'),
        ('announcement', 'Announcement'),
        ('progress', 'Progress Report')
    ], default='general')


# Submission Forms
class SubmissionForm(FlaskForm):
    """Milestone submission form."""
    content = TextAreaField('Submission Notes', validators=[
        DataRequired(message='Please provide submission details'),
        Length(min=20, max=5000)
    ])
    files = FileField('Attach Files', validators=[Optional()])


# Feedback Forms
class FeedbackForm(FlaskForm):
    """Feedback form."""
    content = TextAreaField('Feedback', validators=[
        DataRequired(message='Feedback content is required'),
        Length(min=10, max=2000)
    ])
    rating = SelectField('Rating (Optional)', choices=[
        (0, 'No Rating'),
        (1, '1 - Needs Improvement'),
        (2, '2 - Below Expectations'),
        (3, '3 - Meets Expectations'),
        (4, '4 - Exceeds Expectations'),
        (5, '5 - Outstanding')
    ], coerce=int, validators=[Optional()])
    feedback_type = SelectField('Feedback Type', choices=[
        ('general', 'General Feedback'),
        ('milestone', 'Milestone Feedback'),
        ('final', 'Final Evaluation')
    ], default='general')
    recipient = SelectField('For', coerce=int, validators=[Optional()])
    milestone = SelectField('Related Milestone', coerce=int, validators=[Optional()])

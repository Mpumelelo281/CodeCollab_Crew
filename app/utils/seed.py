"""Database seeding utilities."""
from app import db
from app.models import Role, Department, Course, Skill, Tool, User


def seed_database():
    """Seed the database with initial data."""
    print("Seeding database...")
    
    # Create roles
    roles = [
        Role(name='admin', description='System administrator'),
        Role(name='lecturer', description='Faculty member who can create and manage projects'),
        Role(name='student', description='Student who can join projects and contribute')
    ]
    
    for role in roles:
        existing = Role.query.filter_by(name=role.name).first()
        if not existing:
            db.session.add(role)
    
    db.session.commit()
    print("- Roles created")
    
    # Create departments
    departments = [
        Department(name='Computer Science', code='CS', 
                  description='Department of Computer Science'),
        Department(name='Information Technology', code='IT',
                  description='Department of Information Technology'),
        Department(name='Software Engineering', code='SE',
                  description='Department of Software Engineering'),
        Department(name='Data Science', code='DS',
                  description='Department of Data Science'),
        Department(name='Electrical Engineering', code='EE',
                  description='Department of Electrical Engineering'),
        Department(name='Business Administration', code='BA',
                  description='Department of Business Administration'),
    ]
    
    for dept in departments:
        existing = Department.query.filter_by(code=dept.code).first()
        if not existing:
            db.session.add(dept)
    
    db.session.commit()
    print("- Departments created")
    
    # Create courses
    cs_dept = Department.query.filter_by(code='CS').first()
    it_dept = Department.query.filter_by(code='IT').first()
    se_dept = Department.query.filter_by(code='SE').first()
    ds_dept = Department.query.filter_by(code='DS').first()
    
    courses = [
        Course(name='Web Development', code='CS301', 
               description='Introduction to web development', department=cs_dept),
        Course(name='Database Systems', code='CS302',
               description='Database design and management', department=cs_dept),
        Course(name='Software Engineering', code='SE401',
               description='Software development methodologies', department=se_dept),
        Course(name='Machine Learning', code='DS401',
               description='Introduction to machine learning', department=ds_dept),
        Course(name='Mobile App Development', code='IT302',
               description='Mobile application development', department=it_dept),
        Course(name='Cloud Computing', code='IT401',
               description='Cloud services and deployment', department=it_dept),
        Course(name='Capstone Project', code='CS499',
               description='Final year capstone project', department=cs_dept),
    ]
    
    for course in courses:
        existing = Course.query.filter_by(code=course.code).first()
        if not existing:
            db.session.add(course)
    
    db.session.commit()
    print("- Courses created")
    
    # Create skills
    skills = [
        # Programming languages
        Skill(name='Python', category='Programming'),
        Skill(name='JavaScript', category='Programming'),
        Skill(name='Java', category='Programming'),
        Skill(name='C++', category='Programming'),
        Skill(name='TypeScript', category='Programming'),
        Skill(name='SQL', category='Programming'),
        
        # Frameworks
        Skill(name='React', category='Framework'),
        Skill(name='Angular', category='Framework'),
        Skill(name='Vue.js', category='Framework'),
        Skill(name='Django', category='Framework'),
        Skill(name='Flask', category='Framework'),
        Skill(name='Node.js', category='Framework'),
        Skill(name='Spring Boot', category='Framework'),
        
        # Other skills
        Skill(name='Machine Learning', category='Data Science'),
        Skill(name='Data Analysis', category='Data Science'),
        Skill(name='UI/UX Design', category='Design'),
        Skill(name='Project Management', category='Management'),
        Skill(name='Technical Writing', category='Communication'),
        Skill(name='Git', category='Tools'),
        Skill(name='Docker', category='DevOps'),
        Skill(name='AWS', category='Cloud'),
    ]
    
    for skill in skills:
        existing = Skill.query.filter_by(name=skill.name).first()
        if not existing:
            db.session.add(skill)
    
    db.session.commit()
    print("- Skills created")
    
    # Create tools
    tools = [
        Tool(name='VS Code', category='IDE', description='Visual Studio Code editor'),
        Tool(name='GitHub', category='Version Control', description='Git hosting platform'),
        Tool(name='Jira', category='Project Management', description='Issue tracking'),
        Tool(name='Slack', category='Communication', description='Team communication'),
        Tool(name='Figma', category='Design', description='UI/UX design tool'),
        Tool(name='PostgreSQL', category='Database', description='Relational database'),
        Tool(name='MongoDB', category='Database', description='NoSQL database'),
        Tool(name='Docker', category='DevOps', description='Containerization'),
        Tool(name='AWS', category='Cloud', description='Amazon Web Services'),
        Tool(name='Postman', category='Testing', description='API testing tool'),
    ]
    
    for tool in tools:
        existing = Tool.query.filter_by(name=tool.name).first()
        if not existing:
            db.session.add(tool)
    
    db.session.commit()
    print("- Tools created")
    
    print("Database seeding complete!")


def create_sample_users():
    """Create sample users for testing."""
    admin_role = Role.query.filter_by(name='admin').first()
    lecturer_role = Role.query.filter_by(name='lecturer').first()
    student_role = Role.query.filter_by(name='student').first()
    
    cs_dept = Department.query.filter_by(code='CS').first()
    
    # Create admin
    admin = User.query.filter_by(email='admin@university.edu').first()
    if not admin:
        admin = User(
            email='admin@university.edu',
            first_name='System',
            last_name='Admin',
            employee_id='ADMIN001',
            is_verified=True,
            is_active=True,
            department=cs_dept
        )
        admin.set_password('Admin@123')
        admin.roles.append(admin_role)
        db.session.add(admin)
    
    # Create lecturer
    lecturer = User.query.filter_by(email='prof.smith@university.edu').first()
    if not lecturer:
        lecturer = User(
            email='prof.smith@university.edu',
            first_name='John',
            last_name='Smith',
            employee_id='FAC001',
            is_verified=True,
            is_active=True,
            department=cs_dept,
            bio='Professor of Computer Science with 15 years of experience.'
        )
        lecturer.set_password('Lecturer@123')
        lecturer.roles.append(lecturer_role)
        db.session.add(lecturer)
    
    # Create students
    students_data = [
        ('alice@university.edu', 'Alice', 'Johnson', 'STU001'),
        ('bob@university.edu', 'Bob', 'Williams', 'STU002'),
        ('carol@university.edu', 'Carol', 'Brown', 'STU003'),
    ]
    
    for email, first, last, student_id in students_data:
        student = User.query.filter_by(email=email).first()
        if not student:
            student = User(
                email=email,
                first_name=first,
                last_name=last,
                student_id=student_id,
                is_verified=True,
                is_active=True,
                department=cs_dept
            )
            student.set_password('Student@123')
            student.roles.append(student_role)
            db.session.add(student)
    
    db.session.commit()
    print("Sample users created!")
    print("  Admin: admin@university.edu / Admin@123")
    print("  Lecturer: prof.smith@university.edu / Lecturer@123")
    print("  Students: alice/bob/carol@university.edu / Student@123")


def create_sample_projects():
    """Create sample projects for testing."""
    from datetime import datetime, timezone, timedelta
    from app.models import Project, Milestone
    
    lecturer = User.query.filter_by(email='prof.smith@university.edu').first()
    if not lecturer:
        print("Please run create_sample_users first!")
        return
    
    cs_dept = Department.query.filter_by(code='CS').first()
    web_course = Course.query.filter_by(code='CS301').first()
    
    # Get some skills
    python = Skill.query.filter_by(name='Python').first()
    flask = Skill.query.filter_by(name='Flask').first()
    js = Skill.query.filter_by(name='JavaScript').first()
    react = Skill.query.filter_by(name='React').first()
    
    # Create a sample project
    project = Project.query.filter_by(title='Student Portal Development').first()
    if not project:
        project = Project(
            title='Student Portal Development',
            description='Build a comprehensive student portal with course management, grade tracking, and communication features. This project will give students hands-on experience with full-stack development.',
            goals='1. Create user authentication system\n2. Implement course enrollment\n3. Build grade tracking dashboard\n4. Add notification system',
            expected_outcomes='A fully functional web application that can be used by students to manage their academic life.',
            status='open',
            visibility='public',
            max_team_size=5,
            min_team_size=2,
            start_date=datetime.now(timezone.utc).date(),
            end_date=(datetime.now(timezone.utc) + timedelta(days=90)).date(),
            application_deadline=datetime.now(timezone.utc) + timedelta(days=14),
            owner=lecturer,
            department=cs_dept,
            course=web_course
        )
        
        if python:
            project.skills.append(python)
        if flask:
            project.skills.append(flask)
        if js:
            project.skills.append(js)
        
        db.session.add(project)
        db.session.commit()
        
        # Add milestones
        milestones = [
            Milestone(
                project=project,
                title='Project Setup & Planning',
                description='Set up development environment, create project structure, and finalize requirements.',
                due_date=datetime.now(timezone.utc) + timedelta(days=14),
                priority='high'
            ),
            Milestone(
                project=project,
                title='User Authentication',
                description='Implement user registration, login, and authentication system.',
                due_date=datetime.now(timezone.utc) + timedelta(days=30),
                priority='high'
            ),
            Milestone(
                project=project,
                title='Core Features',
                description='Develop main features including course management and grade tracking.',
                due_date=datetime.now(timezone.utc) + timedelta(days=60),
                priority='medium'
            ),
            Milestone(
                project=project,
                title='Testing & Deployment',
                description='Complete testing and deploy the application.',
                due_date=datetime.now(timezone.utc) + timedelta(days=85),
                priority='high'
            ),
        ]
        
        for milestone in milestones:
            db.session.add(milestone)
        
        db.session.commit()
        print(f"Sample project created: {project.title}")
    
    # Create another project
    project2 = Project.query.filter_by(title='Mobile Health Tracker').first()
    if not project2:
        project2 = Project(
            title='Mobile Health Tracker',
            description='Develop a mobile application that helps users track their health metrics, including exercise, nutrition, and sleep patterns.',
            goals='Create an intuitive mobile app with data visualization and goal tracking.',
            expected_outcomes='A cross-platform mobile application available on iOS and Android.',
            status='open',
            visibility='public',
            max_team_size=4,
            min_team_size=2,
            start_date=datetime.now(timezone.utc).date(),
            end_date=(datetime.now(timezone.utc) + timedelta(days=120)).date(),
            application_deadline=datetime.now(timezone.utc) + timedelta(days=21),
            owner=lecturer,
            department=cs_dept
        )
        
        if react:
            project2.skills.append(react)
        if js:
            project2.skills.append(js)
        
        db.session.add(project2)
        db.session.commit()
        print(f"Sample project created: {project2.title}")
    
    print("Sample projects created!")

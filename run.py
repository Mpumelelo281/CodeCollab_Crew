"""Application entry point."""
import os
from app import create_app, db
from app.models import User, Role, Project, Milestone, Department, Course, Skill


app = create_app(os.environ.get('FLASK_CONFIG', 'development'))


@app.shell_context_processor
def make_shell_context():
    """Make database objects available in flask shell."""
    return {
        'db': db,
        'User': User,
        'Role': Role,
        'Project': Project,
        'Milestone': Milestone,
        'Department': Department,
        'Course': Course,
        'Skill': Skill
    }


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

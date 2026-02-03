from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
import os

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

def init_database(app):
    """Initialize database with tables"""
    with app.app_context():
        # Create instance directory if it doesn't exist
        instance_path = os.path.join(app.root_path, 'instance')
        if not os.path.exists(instance_path):
            os.makedirs(instance_path)
        
        # Create all tables
        db.create_all()
        
        # Create default admin user if not exists
        from auth import User
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                password_hash=User.hash_password('admin'),
                is_admin=True,
                is_active=True
            )
            db.session.add(admin)
            db.session.commit()
            print("✓ Default admin user created (admin/admin)")

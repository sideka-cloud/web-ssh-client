from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from database import db
from datetime import datetime

class User(UserMixin, db.Model):
    """User model for authentication"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    connections = db.relationship('SSHConnection', backref='user', lazy=True, cascade='all, delete-orphan')
    
    @staticmethod
    def hash_password(password):
        """Hash a password using bcrypt"""
        from werkzeug.security import generate_password_hash
        return generate_password_hash(password, method='pbkdf2:sha256')
    
    def verify_password(self, password):
        """Verify password against hash"""
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)
    
    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login = datetime.utcnow()
        db.session.commit()
    
    def change_password(self, new_password):
        """Change user password"""
        self.password_hash = self.hash_password(new_password)
        db.session.commit()
    
    @staticmethod
    def get_user_by_username(username):
        """Get user by username"""
        return User.query.filter_by(username=username).first()

class SSHConnection(db.Model):
    """SSH connection model"""
    __tablename__ = 'ssh_connections'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    hostname = db.Column(db.String(100), nullable=False)
    port = db.Column(db.Integer, default=22)
    username = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(500), nullable=False)  # Encrypted
    private_key = db.Column(db.Text)  # For key-based auth
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used = db.Column(db.DateTime)
    
    # Foreign key
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    def update_last_used(self):
        """Update last used timestamp"""
        self.last_used = datetime.utcnow()
        db.session.commit()

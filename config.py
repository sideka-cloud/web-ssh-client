import os
from datetime import timedelta

class Config:
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-in-production'
    
    # Database
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(
        os.path.abspath(os.path.dirname(__file__)), 
        'instance', 
        'database.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    
    # SSH Settings
    SSH_TIMEOUT = 30
    SSH_BUFFER_SIZE = 65536
    
    # Application
    APP_NAME = "Web SSH Client"
    VERSION = "1.0.0"
    
    # Security Headers
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False  # Set True for HTTPS
    REMEMBER_COOKIE_HTTPONLY = True

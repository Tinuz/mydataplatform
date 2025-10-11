"""
Custom Amundsen Frontend Configuration for Development/Demo
Provides a simple authentication method that uses a default 'root' user
"""

import os
from amundsen_application.config import LocalConfig as BaseLocalConfig


class CustomConfig(BaseLocalConfig):
    """
    Custom configuration that adds a simple auth method for development
    """
    
    # Base service URLs
    METADATASERVICE_BASE = os.environ.get('METADATASERVICE_BASE', 'http://amundsen-metadata:5002')
    SEARCHSERVICE_BASE = os.environ.get('SEARCHSERVICE_BASE', 'http://amundsen-search:5001')
    
    # Simple auth method - returns a default user for development
    AUTH_USER_METHOD = lambda self, app: {
        'user_id': 'root',
        'display_name': 'Demo User',
        'email': 'demo@example.com',
        'is_active': True
    }
    
    # Enable bookmark feature
    MAIL_CLIENT = None  # Disable email for bookmarks
    
    # Session timeout
    REQUEST_SESSION_TIMEOUT_SEC = int(os.environ.get('REQUEST_SESSION_TIMEOUT_SEC', 1200))
    
    # Logging
    LOG_LEVEL = 'INFO'
    
    # Optional: Custom branding
    SITE_NAME = 'Data Platform Catalog'

"""
Keycloak OIDC Authentication for Dagster
Using Flask-OIDC for authentication flow
"""
import os
from flask import redirect, url_for, session, request
from flask_oidc import OpenIDConnect
from dagster_webserver import DagsterWebserver

# Keycloak OIDC Configuration
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "data-platform")
CLIENT_ID = os.getenv("OIDC_CLIENT_ID", "dagster")
CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET", "dagster_client_secret_2025")
REDIRECT_URI = os.getenv("OIDC_REDIRECT_URI", "http://localhost:3000/oidc_callback")

# Flask-OIDC Configuration
OIDC_CONFIG = {
    'SECRET_KEY': os.getenv("FLASK_SECRET_KEY", "dagster_secret_key_change_me"),
    'OIDC_CLIENT_SECRETS': {
        'web': {
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'auth_uri': f'{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth',
            'token_uri': f'{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token',
            'issuer': f'{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}',
            'userinfo_uri': f'{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/userinfo',
            'redirect_uris': [REDIRECT_URI],
        }
    },
    'OIDC_ID_TOKEN_COOKIE_SECURE': False,  # Set to True in production with HTTPS
    'OIDC_REQUIRE_VERIFIED_EMAIL': False,
    'OIDC_OPENID_REALM': KEYCLOAK_REALM,
    'OIDC_INTROSPECTION_AUTH_METHOD': 'client_secret_post',
}


def setup_keycloak_auth(app):
    """
    Setup Keycloak OIDC authentication for Dagster Flask app
    
    Args:
        app: Flask application instance
    """
    # Apply OIDC configuration
    for key, value in OIDC_CONFIG.items():
        app.config[key] = value
    
    # Initialize Flask-OIDC
    oidc = OpenIDConnect(app)
    
    # Add authentication routes
    @app.route('/oidc_callback')
    @oidc.require_login
    def oidc_callback():
        """Handle OIDC callback after authentication"""
        # Store user info in session
        user_info = oidc.user_getinfo(['preferred_username', 'email', 'name'])
        session['user'] = {
            'username': user_info.get('preferred_username'),
            'email': user_info.get('email'),
            'name': user_info.get('name', user_info.get('preferred_username')),
        }
        # Redirect to main Dagster UI
        return redirect('/')
    
    @app.route('/logout')
    def logout():
        """Logout and clear session"""
        oidc.logout()
        session.clear()
        return redirect(f'{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/logout')
    
    # Protect all routes with authentication
    @app.before_request
    def require_authentication():
        """Require authentication for all routes except public ones"""
        public_routes = ['/oidc_callback', '/logout', '/health']
        
        if request.path not in public_routes and not request.path.startswith('/static'):
            if not oidc.user_loggedin:
                return oidc.redirect_to_auth_server(request.url)
    
    return oidc


if __name__ == "__main__":
    print("Keycloak OIDC Authentication Module")
    print(f"Keycloak URL: {KEYCLOAK_URL}")
    print(f"Realm: {KEYCLOAK_REALM}")
    print(f"Client ID: {CLIENT_ID}")
    print(f"Redirect URI: {REDIRECT_URI}")

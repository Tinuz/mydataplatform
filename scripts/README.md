# Scripts Directory

Collection of utility scripts for managing the data platform.

## 📁 Directory Structure

- `setup/` - Setup and initialization scripts
- `tests/` - Testing and cleanup scripts  
- Core management scripts (Keycloak, investigations, etc.)

## 🔧 Key Scripts

### Setup
- **setup_keycloak.sh** - Initial Keycloak setup with users, roles, OAuth clients
- **update_dagster_oidc.sh** - Update Dagster OAuth client configuration

### User & Access Management
- **assign_keycloak_roles.sh** - Assign roles to users
- **grant_investigation_access.sh** - Grant investigation access
- **revoke_investigation_access.sh** - Revoke investigation access
- **list_investigation_access.sh** - List investigation permissions

### Testing
- **tests/test_jwt_rls.sh** - Test JWT-based RLS
- **tests/test_keycloak.sh** - Test Keycloak OAuth
- **demo_security.sh** - Interactive security demo

### Cleanup
- **tests/cleanup_platform.sh** - Full cleanup (with confirmation)
- **tests/quick_cleanup.sh** - Quick cleanup (no confirmation)

### Platform Management
- **bootstrap.sh** - Initialize entire platform
- **health_check.sh** - Check service health

See [main README](../README.md) for detailed usage instructions.

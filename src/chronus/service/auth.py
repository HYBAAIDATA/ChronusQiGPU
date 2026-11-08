"""Authentication and RBAC service module alias for Chronus CIaaS.

Re-exports core auth dependencies and middleware for backwards compatibility and ergonomics.
"""

from chronus.service.dependencies import AuthService, auth_service, security
from chronus.service.auth_middleware import (
    AuthenticatedIdentity,
    JWTValidator,
    Role,
    create_jwt_token,
    get_current_identity,
    jwt_validator,
    require_roles,
)

__all__ = [
    "AuthService",
    "auth_service",
    "security",
    "Role",
    "AuthenticatedIdentity",
    "JWTValidator",
    "jwt_validator",
    "get_current_identity",
    "require_roles",
    "create_jwt_token",
]

"""
JWT authentication service.

Implementation Assumption: the architecture diagram calls for "Authenticate
users (JWT)" inside the Flask business logic box but does not draw an
identity provider or user store. For this POC we self-issue JWTs for any
{username, role} pair via POST /api/auth/login (no password store). For a
production build, replace `issue_token` with a call to Amazon Cognito (or
another IdP) and keep `verify_token` / `require_auth` unchanged, since they
only depend on the JWT contract, not on how the token was issued.
"""
import datetime
from functools import wraps

import jwt
from flask import current_app, g, request

from app.utils.errors import AuthError


def issue_token(username, role):
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": username,
        "role": role,
        "iat": now,
        "exp": now + datetime.timedelta(minutes=current_app.config["JWT_EXPIRY_MINUTES"]),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")


def verify_token(token):
    try:
        return jwt.decode(token, current_app.config["JWT_SECRET_KEY"], algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired")
    except jwt.InvalidTokenError:
        raise AuthError("Invalid token")


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise AuthError("Missing Authorization: Bearer <token> header")
        token = header.split(" ", 1)[1]
        g.user = verify_token(token)
        return fn(*args, **kwargs)

    return wrapper

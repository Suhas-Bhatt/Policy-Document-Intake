from flask import Blueprint, jsonify, request

from app.models.schemas import validate_login_request
from app.services.auth_service import issue_token

bp = Blueprint("auth", __name__)


@bp.post("/api/auth/login")
def login():
    """
    POC-only token issuance (see auth_service.py docstring for the
    Implementation Assumption). Accepts {"username": "...", "role": "..."}.
    """
    payload = validate_login_request(request.get_json(silent=True))
    token = issue_token(payload["username"], payload["role"])
    return jsonify({"access_token": token, "token_type": "Bearer"})

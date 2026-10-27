from flask import Blueprint, jsonify

from app.services.auth_service import require_auth
from app.services.snowflake_service import get_policy_by_id
from app.utils.errors import NotFoundError

bp = Blueprint("policies", __name__)


@bp.get("/api/policies/<policy_id>")
@require_auth
def get_policy(policy_id):
    policy = get_policy_by_id(policy_id)
    if not policy:
        raise NotFoundError(f"No policy found with id {policy_id}")
    return jsonify(policy)

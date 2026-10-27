from flask import Blueprint, jsonify, request

from app.services.auth_service import require_auth
from app.services.snowflake_service import search_policies_and_documents
from app.utils.errors import ValidationError

bp = Blueprint("search", __name__)


@bp.get("/api/search")
@require_auth
def search():
    query_text = request.args.get("q")
    if not query_text:
        raise ValidationError("Query parameter 'q' is required")
    limit = int(request.args.get("limit", 25))
    results = search_policies_and_documents(query_text, limit)
    return jsonify({"query": query_text, "count": len(results), "results": results})

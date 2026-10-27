from flask import Blueprint, jsonify

from app.services.auth_service import require_auth
from app.services import snowflake_service
from app.services.snowflake_service import get_processing_dashboard_metrics

bp = Blueprint("dashboard", __name__)


@bp.get("/api/dashboard")
@require_auth
def dashboard_metrics():
    rows = get_processing_dashboard_metrics()
    total_documents = sum(row["DOCUMENT_COUNT"] for row in rows)
    return jsonify({
        "total_documents": total_documents,
        "rows": rows,
        "demo_data": not snowflake_service.SNOWFLAKE_AVAILABLE,
    })

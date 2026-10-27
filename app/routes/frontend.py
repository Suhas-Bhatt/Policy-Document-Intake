from flask import Blueprint, render_template

bp = Blueprint("frontend", __name__)


@bp.get("/")
def index():
    """
    Minimal web UI calling the JSON API (app/static/app.js). Not part of the
    original architecture diagram -- the diagram's only drawn interface is
    the Flask REST API itself -- added on request to make the API usable
    from a browser instead of curl/scripts only.
    """
    return render_template("index.html")


@bp.get("/dashboard")
def dashboard_page():
    """Separate page for the processing dashboard (PROCESSING_DASHBOARD_VIEW)."""
    return render_template("dashboard.html")

import logging
import mimetypes
import uuid

from flask import Flask, g, request

from app.config import Config
from app.utils.errors import register_error_handlers

# On some Windows machines the registry entries Python's mimetypes module
# relies on are missing/wrong for .css and .js, causing Flask to serve them
# with an incorrect Content-Type (e.g. text/plain). Browsers then refuse to
# apply the stylesheet/script. Force the correct types explicitly so static
# file serving doesn't depend on the local registry.
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    logging.basicConfig(level=logging.INFO)

    register_error_handlers(app)
    register_blueprints(app)
    register_request_logging(app)

    return app


def register_blueprints(app):
    from app.routes.health import bp as health_bp
    from app.routes.auth import bp as auth_bp
    from app.routes.documents import bp as documents_bp
    from app.routes.policies import bp as policies_bp
    from app.routes.search import bp as search_bp
    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.frontend import bp as frontend_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(policies_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(frontend_bp)


def register_request_logging(app):
    """
    Assigns a correlation/request ID to every request so a single document's
    journey (Flask -> API Gateway -> S3 -> EventBridge -> Lambda -> DynamoDB
    -> Snowflake) can be traced across CloudWatch and application logs by
    document_id; this header-level request ID ties the Flask-side hop to
    that trail. See PART 15 (Logging & Monitoring) in the README.
    """

    @app.before_request
    def assign_request_id():
        g.request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
        app.logger.info("request_start method=%s path=%s request_id=%s", request.method, request.path, g.request_id)

    @app.after_request
    def add_request_id_header(response):
        response.headers["X-Request-Id"] = getattr(g, "request_id", "")
        return response

class ApiError(Exception):
    """Base error carrying an HTTP status code and a machine-readable code."""

    status_code = 500
    code = "internal_error"

    def __init__(self, message, status_code=None, code=None, details=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        self.details = details or {}

    def to_dict(self):
        body = {"error": self.code, "message": self.message}
        if self.details:
            body["details"] = self.details
        return body


class ValidationError(ApiError):
    status_code = 400
    code = "validation_error"


class NotFoundError(ApiError):
    status_code = 404
    code = "not_found"


class AuthError(ApiError):
    status_code = 401
    code = "unauthorized"


class UpstreamServiceError(ApiError):
    status_code = 502
    code = "upstream_service_error"


def register_error_handlers(app):
    from flask import jsonify

    @app.errorhandler(ApiError)
    def handle_api_error(err):
        response = jsonify(err.to_dict())
        response.status_code = err.status_code
        return response

    @app.errorhandler(404)
    def handle_404(_err):
        return jsonify({"error": "not_found", "message": "Resource not found"}), 404

    @app.errorhandler(413)
    def handle_413(_err):
        return jsonify({"error": "payload_too_large", "message": "File exceeds maximum allowed size"}), 413

    @app.errorhandler(Exception)
    def handle_unexpected(err):
        app.logger.exception("Unhandled exception")
        return jsonify({"error": "internal_error", "message": "An unexpected error occurred"}), 500

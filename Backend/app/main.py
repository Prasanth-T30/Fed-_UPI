"""Flask application for the FedUPI API and built frontend."""

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from app.api.auth_routes import router as auth_router
from app.api.routes import public, router
from app.config import FRONTEND_DIST

app = Flask(__name__, static_folder=None)
CORS(app, origins=["http://127.0.0.1:5173", "http://localhost:5173"])
app.register_blueprint(public)
app.register_blueprint(auth_router)
app.register_blueprint(router)


@app.errorhandler(HTTPException)
def http_error(error):
    return jsonify(detail=error.description), error.code

if (FRONTEND_DIST / "index.html").exists():
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def spa(path):
        file = FRONTEND_DIST / path
        if path and file.is_file() and file.resolve().is_relative_to(FRONTEND_DIST.resolve()):
            return send_from_directory(FRONTEND_DIST, path)
        return send_from_directory(FRONTEND_DIST, "index.html")

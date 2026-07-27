"""
dashboard/server.py

Lightweight Flask dashboard server for Syntra AI Mail Agent.
Provides:
  - GET /             -> Serves dashboard/index.html
  - GET /health       -> Health check endpoint (Issue #13)
  - GET /metrics      -> System metrics (Issue #13)
  - GET /api/stats    -> Aggregated email statistics (Issue #8)
  - GET /api/emails   -> Paginated recent email list (Issue #8)

Run automatically in background when FEATURE_ENABLE_DASHBOARD=true.
Controlled via DASHBOARD_PORT env var (default: 8080).
"""
import os
import sys
import time
from pathlib import Path

# Ensure src is on path when run as a module from project root
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    from flask import Flask, jsonify, send_from_directory, request
    from flask_cors import CORS
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False

from dotenv import load_dotenv
load_dotenv()

_START_TIME = time.time()
_DASHBOARD_DIR = Path(__file__).parent


def create_app():
    """Create and configure the Flask dashboard application."""
    if not HAS_FLASK:
        raise ImportError(
            "Flask is required for the dashboard. Install with: pip install flask flask-cors"
        )

    app = Flask(__name__, static_folder=str(_DASHBOARD_DIR), static_url_path="")
    CORS(app)

    # Import repository lazily to avoid circular imports
    def _get_repo():
        from src.infrastructure.database.sqlite_repo import SQLiteRepository
        return SQLiteRepository()

    # Cache a single repository instance per server lifetime
    _repo_cache = {}

    def get_repo():
        if "repo" not in _repo_cache:
            _repo_cache["repo"] = _get_repo()
        return _repo_cache["repo"]

    @app.route("/")
    def index():
        """Serve the dashboard HTML."""
        return send_from_directory(str(_DASHBOARD_DIR), "index.html")

    @app.route("/health")
    def health():
        """
        Issue #13: Health check endpoint.
        Returns agent uptime and version.
        """
        try:
            version = "unknown"
            version_file = _project_root / "VERSION"
            if version_file.exists():
                version = version_file.read_text().strip()

            uptime = round(time.time() - _START_TIME, 1)
            return jsonify({
                "status": "ok",
                "uptime_seconds": uptime,
                "version": version,
                "service": "Syntra AI Mail Agent",
            }), 200
        except Exception as e:
            return jsonify({"status": "error", "error": str(e)}), 500

    @app.route("/metrics")
    def metrics():
        """
        Issue #13: System metrics endpoint.
        Returns aggregated processing statistics.
        """
        try:
            repo = get_repo()
            data = repo.get_metrics()
            data["uptime_seconds"] = round(time.time() - _START_TIME, 1)
            return jsonify(data), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/stats")
    def stats():
        """
        Issue #8: Dashboard statistics endpoint.
        Returns category distribution, risk distribution, daily counts, and totals.
        """
        try:
            repo = get_repo()
            data = repo.get_stats()
            return jsonify(data), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/emails")
    def emails():
        """
        Issue #8: Paginated email list for the dashboard table.
        Query params: limit (default 50), offset (default 0)
        """
        try:
            limit = min(int(request.args.get("limit", 50)), 200)
            offset = int(request.args.get("offset", 0))
            repo = get_repo()
            data = repo.get_recent_emails(limit=limit, offset=offset)
            return jsonify({"emails": data, "limit": limit, "offset": offset}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return app


def run_server(port: int = 8080, debug: bool = False):
    """Start the Flask dashboard server."""
    if not HAS_FLASK:
        print("Flask not installed. Dashboard server cannot start.")
        return

    app = create_app()
    print(f"[Dashboard] Starting on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)


if __name__ == "__main__":
    port = int(os.environ.get("DASHBOARD_PORT", 8080))
    run_server(port=port)

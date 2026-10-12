"""Web Application Backend for AI Automation Pipeline.

Provides RESTful APIs and serves the modern interactive dashboard.
Connects SQLite storage, Gemini AI Service, and Selenium scraper.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request, send_file

from config import PipelineConfig, default_config, logger
from pipeline import run_pipeline
from storage.db_handler import DatabaseHandler

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)

# Shared Database Handler
db_handler = DatabaseHandler()


@app.route("/")
def index():
    """Renders the primary automation dashboard."""
    return render_template("index.html")


@app.route("/api/status", methods=["GET"])
def get_status():
    """Returns real-time health and configuration status."""
    is_api_key_valid = default_config.is_api_key_configured()
    stats = db_handler.fetch_stats()

    return jsonify(
        {
            "status": "online",
            "gemini": {
                "configured": is_api_key_valid,
                "model": default_config.gemini_model,
                "key_preview": (
                    f"AIzaSy...{default_config.gemini_api_key[-4:]}"
                    if is_api_key_valid and default_config.gemini_api_key
                    else "Not Set / Simulated Mode"
                ),
            },
            "scraper": {
                "engine": "Selenium Headless Chrome",
                "default_url": default_config.default_target_url,
                "headless_default": default_config.headless_browser,
            },
            "database": {
                "connected": True,
                "path": str(default_config.database_path.resolve()),
                "total_records": stats["total_records"],
            },
        }
    )


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Returns analytics and distribution metrics."""
    stats = db_handler.fetch_stats()
    return jsonify(stats)


@app.route("/api/records", methods=["GET"])
def get_records():
    """Fetches all stored extraction records with optional query filtering."""
    search_query = request.args.get("q", "").strip().lower()
    risk_filter = request.args.get("risk", "").strip()
    sentiment_filter = request.args.get("sentiment", "").strip()

    records = db_handler.fetch_all_records(limit=200)

    # In-memory filtering if query params are provided
    if search_query:
        records = [
            r
            for r in records
            if search_query in r["title"].lower()
            or search_query in r["summary"].lower()
            or any(search_query in t.lower() for t in r.get("categorized_topics", []))
        ]

    if risk_filter and risk_filter.lower() != "all":
        records = [r for r in records if r["risk_level"].lower() == risk_filter.lower()]

    if sentiment_filter and sentiment_filter.lower() != "all":
        records = [
            r for r in records if r["sentiment"].lower() == sentiment_filter.lower()
        ]

    return jsonify({"count": len(records), "records": records})


@app.route("/api/records/<int:record_id>", methods=["GET"])
def get_single_record(record_id: int):
    """Fetches details for a single record."""
    record = db_handler.fetch_record_by_id(record_id)
    if not record:
        return jsonify({"error": f"Record #{record_id} not found"}), 404
    return jsonify(record)


@app.route("/api/records/<int:record_id>", methods=["DELETE"])
def delete_record(record_id: int):
    """Deletes a record from the SQLite database."""
    success = db_handler.delete_record(record_id)
    if not success:
        return jsonify({"error": f"Record #{record_id} not found"}), 404
    return jsonify({"message": f"Record #{record_id} successfully deleted."})


@app.route("/api/pipeline/run", methods=["POST"])
def trigger_pipeline():
    """Executes the pipeline synchronously and returns the structured extraction result."""
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    url = payload.get("url") or default_config.default_target_url
    dry_run = payload.get("dry_run", False)
    headless = payload.get("headless", True)

    logger.info(
        f"API Request to run pipeline: URL='{url}', dry_run={dry_run}, headless={headless}"
    )

    try:
        execution_result = run_pipeline(
            target_url=url,
            dry_run=dry_run,
            headless=headless,
        )
        return jsonify(
            {
                "success": True,
                "record_id": execution_result["record_id"],
                "data": execution_result["structured_data"],
                "source_url": execution_result["source_url"],
                "message": "Automation pipeline executed successfully.",
            }
        )
    except Exception as e:
        logger.error(f"Pipeline execution API error: {e}", exc_info=True)
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "message": "Automation pipeline failed during execution.",
                }
            ),
            500,
        )


@app.route("/api/export/json", methods=["GET"])
def export_json():
    """Serves the generated results.json file for download."""
    export_path = db_handler.export_to_json()
    if not export_path.exists():
        return jsonify({"error": "Export file not found."}), 404
    return send_file(
        str(export_path.resolve()),
        mimetype="application/json",
        as_attachment=True,
        download_name="pipeline_results.json",
    )


@app.route("/api/export/db", methods=["GET"])
def export_db():
    """Serves the SQLite database file for download."""
    db_file = default_config.database_path
    if not db_file.exists():
        return jsonify({"error": "Database file not found."}), 404
    return send_file(
        str(db_file.resolve()),
        mimetype="application/x-sqlite3",
        as_attachment=True,
        download_name="pipeline_data.db",
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Starting Web Application Server at http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)

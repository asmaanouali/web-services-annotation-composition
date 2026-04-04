"""Service management endpoints — upload, list, get, download annotated WSDL."""

import io
import zipfile
from flask import Blueprint, request, jsonify, Response

from state import app_state
from helpers import generate_enriched_wsdl
from services.annotator import ServiceAnnotator
from services.classic_composer import ClassicComposer
from services.llm_composer import LLMComposer
from validators import safe_route

services_bp = Blueprint("services", __name__)


@services_bp.route("/api/services/upload", methods=["POST"])
@safe_route
def upload_services():
    """Upload WSDL / XML service files."""
    try:
        files = request.files.getlist("files")
        if not files:
            return jsonify({"error": "No files provided"}), 400

        services = []
        errors = []

        for idx, file in enumerate(files):
            if idx % 100 == 0:
                print(f"Progress: {idx}/{len(files)} files processed")

            if file.filename.endswith(".wsdl") or file.filename.endswith(".xml"):
                try:
                    content = file.read().decode("utf-8")
                    service = app_state["parser"].parse_content(content, file.filename)
                    if service:
                        services.append(service)
                    else:
                        errors.append(f"{file.filename}: Parse failed")
                except Exception as e:
                    errors.append(f"{file.filename}: {e}")

        print(f"Processing completed: {len(services)} services loaded, {len(errors)} errors")

        if services:
            app_state["services"].extend(services)

            # Reset composers with learning capability
            app_state["annotator"] = ServiceAnnotator(
                app_state["services"],
                training_examples=app_state["learning_state"].get("training_examples"),
                interaction_store=app_state["interaction_store"],
            )
            app_state["classic_composer"] = ClassicComposer(app_state["services"])

            if app_state["learning_state"]["is_trained"]:
                app_state["llm_composer"] = LLMComposer(
                    app_state["services"],
                    training_examples=app_state["learning_state"]["training_examples"],
                )
            else:
                app_state["llm_composer"] = LLMComposer(app_state["services"])

            # Reset annotation status
            app_state["annotation_status"] = {
                "services_annotated": False,
                "annotation_count": 0,
                "total_services": len(app_state["services"]),
            }

            message = f"{len(services)} services loaded successfully"
            if errors:
                message += f" ({len(errors)} errors)"

            return jsonify({
                "message": message,
                "total_services": len(app_state["services"]),
                "services": [s.to_dict() for s in services],
                "errors": errors if errors else None,
            })
        else:
            return jsonify({
                "error": "No valid services found",
                "errors": errors[:10],
                "total_errors": len(errors),
            }), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@services_bp.route("/api/services", methods=["GET"])
@safe_route
def get_services():
    """Retrieve service list."""
    return jsonify({
        "services": [s.to_dict() for s in app_state["services"]],
        "total": len(app_state["services"]),
    })


@services_bp.route("/api/services/<service_id>", methods=["GET"])
@safe_route
def get_service(service_id):
    """Retrieve a specific service."""
    service = next((s for s in app_state["services"] if s.id == service_id), None)
    if not service:
        return jsonify({"error": "Service not found"}), 404
    return jsonify(service.to_dict())


@services_bp.route("/api/services/<service_id>/download", methods=["GET"])
@safe_route
def download_annotated_service(service_id):
    """Download an annotated service in enriched WSDL format."""
    try:
        service = next((s for s in app_state["services"] if s.id == service_id), None)
        if not service:
            return jsonify({"error": "Service not found"}), 404

        xml_content = generate_enriched_wsdl(service)
        response = Response(xml_content, mimetype="application/xml")
        response.headers["Content-Disposition"] = (
            f"attachment; filename={service_id}_enriched.xml"
        )
        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@services_bp.route("/api/services/download-all", methods=["GET"])
@safe_route
def download_all_annotated():
    """Download all annotated services as a ZIP archive of enriched WSDL files.

    Query params:
      - annotated_only=true  (default) — only include services that have annotations
      - ids=id1,id2,...       — restrict to a comma-separated list of service IDs
    """
    try:
        annotated_only = request.args.get("annotated_only", "true").lower() != "false"
        ids_param = request.args.get("ids", "")
        requested_ids = {i.strip() for i in ids_param.split(",") if i.strip()}

        services = app_state["services"]
        if requested_ids:
            services = [s for s in services if s.id in requested_ids]
        if annotated_only:
            services = [s for s in services if s.annotations]

        if not services:
            return jsonify({"error": "No annotated services found"}), 404

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for svc in services:
                xml_content = generate_enriched_wsdl(svc)
                zf.writestr(f"{svc.id}_enriched.xml", xml_content)
        buf.seek(0)

        response = Response(buf.read(), mimetype="application/zip")
        response.headers["Content-Disposition"] = (
            "attachment; filename=annotated_services.zip"
        )
        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 500

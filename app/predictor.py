"""Vertex AI prediction adapter with an explicit local demonstration mode."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from app.config import settings
from app.domain import ANTIBIOTICS, matching_markers


def predict(hits: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    if settings.app_mode == "production":
        if not settings.vertex_configured:
            raise RuntimeError("Vertex AI is not configured for production mode.")
        instances = _automl_instances(hits)
        raw = _vertex_predict(instances)
        return _normalize_vertex_predictions(raw, hits), "vertex-ai"
    return _demo_predict(hits), "demo"


def _canonical(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _automl_instances(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    schema_path = Path(settings.model_schema_path)
    if not schema_path.is_absolute():
        schema_path = Path(__file__).resolve().parents[1] / schema_path
    columns = json.loads(schema_path.read_text(encoding="utf-8"))
    canonical_columns = {_canonical(column): column for column in columns}
    present = {
        canonical_columns[_canonical(str(hit["gene_symbol"]))]
        for hit in hits
        if _canonical(str(hit["gene_symbol"])) in canonical_columns
    }
    instances = []
    for profile in ANTIBIOTICS:
        instance: dict[str, Any] = {column: int(column in present) for column in columns}
        instance["antibiotic"] = profile.name.lower()
        instances.append(instance)
    return instances


def _vertex_predict(instances: list[dict[str, Any]]) -> list[Any]:
    from google.cloud import aiplatform

    credentials_path = _materialize_render_credentials()
    if credentials_path:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    aiplatform.init(project=settings.gcp_project_id, location=settings.gcp_region)
    endpoint = aiplatform.Endpoint(settings.gcp_endpoint_id)
    response = endpoint.predict(instances=instances)
    return list(response.predictions)


def _materialize_render_credentials() -> str | None:
    encoded = settings.gcp_service_account_json_base64
    if not encoded:
        return None
    payload = base64.b64decode(encoded)
    json.loads(payload)
    path = Path(tempfile.gettempdir()) / "gcp-service-account.json"
    path.write_bytes(payload)
    path.chmod(0o600)
    return str(path)


def _normalize_vertex_predictions(raw: list[Any], hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(raw) != len(ANTIBIOTICS):
        raise RuntimeError("Vertex AI returned no predictions.")
    results = []
    genes = [str(hit["gene_symbol"]) for hit in hits]
    for profile, model_item in zip(ANTIBIOTICS, raw):
        probability = _resistance_probability(model_item)
        results.append(_decision(profile, probability, genes))
    return results


def _resistance_probability(prediction: Any) -> float:
    if not isinstance(prediction, dict):
        raise RuntimeError("Vertex AI returned an unsupported prediction format.")
    labels = prediction.get("displayNames") or prediction.get("classes") or []
    scores = prediction.get("confidences") or prediction.get("scores") or []
    probabilities = {str(label).lower(): float(score) for label, score in zip(labels, scores)}
    if "likely to fail" not in probabilities:
        raise RuntimeError("Vertex AI response does not include the 'likely to fail' class.")
    return probabilities["likely to fail"]


def _demo_predict(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    genes = [str(hit["gene_symbol"]) for hit in hits]
    results = []
    for index, profile in enumerate(ANTIBIOTICS):
        markers = matching_markers(genes, profile)
        if markers:
            probability = min(0.97, 0.73 + 0.06 * len(markers))
        else:
            probability = (0.17, 0.46, 0.28)[index]
        results.append(_decision(profile, probability, genes))
    return results


def _decision(profile, resistance_probability: float, genes: list[str]) -> dict[str, Any]:
    probability = max(0.0, min(1.0, resistance_probability))
    markers = matching_markers(genes, profile)
    if 0.35 <= probability <= 0.65:
        call = "No-call"
        confidence = 1 - abs(probability - 0.5) * 2
    elif probability > 0.65:
        call = "Likely to Fail"
        confidence = probability
    else:
        call = "Likely to Work"
        confidence = 1 - probability

    if markers:
        evidence_type = "Known resistance marker"
        evidence = ", ".join(markers)
    elif call == "No-call":
        evidence_type = "Statistical association only"
        evidence = "Model evidence is weak or conflicting."
    else:
        evidence_type = "No known resistance signal"
        evidence = "No relevant known marker was detected; this does not prove susceptibility."
    return {
        "antibiotic": profile.name,
        "drug_class": profile.drug_class,
        "target": profile.target,
        "target_status": "Present (species-level deterministic gate)",
        "call": call,
        "confidence": round(confidence * 100, 1),
        "resistance_probability": round(probability * 100, 1),
        "evidence_type": evidence_type,
        "evidence": evidence,
    }

"""Local XGBoost inference using the bundled, versioned model artifact."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from app.config import settings
from app.domain import ANTIBIOTICS, matching_markers


CLASS_TO_CALL = {
    "likely to fail": "Likely to Fail",
    "likely to work": "Likely to Work",
    "uncertain": "No-call",
}


def _canonical(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


@lru_cache(maxsize=1)
def load_model_bundle() -> dict[str, Any]:
    """Load and validate the trusted model artifact once per server process."""
    model_path = Path(settings.model_path)
    if not model_path.is_absolute():
        model_path = Path(__file__).resolve().parents[1] / model_path
    if not model_path.is_file():
        raise RuntimeError(f"XGBoost model file was not found: {model_path}")

    bundle = joblib.load(model_path)
    required = {"model", "label_encoder", "feature_columns"}
    missing = required - set(bundle)
    if missing:
        raise RuntimeError(f"Model bundle is missing: {', '.join(sorted(missing))}")
    feature_columns = list(bundle["feature_columns"])
    if len(feature_columns) != int(bundle["model"].n_features_in_):
        raise RuntimeError("Model feature count does not match the bundled schema.")
    if set(map(str, bundle["label_encoder"].classes_)) != set(CLASS_TO_CALL):
        raise RuntimeError("Model label classes do not match the application contract.")
    return bundle


def predict(hits: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    bundle = load_model_bundle()
    features = _model_frame(hits, list(bundle["feature_columns"]))
    probabilities = bundle["model"].predict_proba(features)
    labels = [str(label) for label in bundle["label_encoder"].classes_]
    genes = [str(hit["gene_symbol"]) for hit in hits]

    results = []
    for profile, probability_row in zip(ANTIBIOTICS, probabilities):
        class_probabilities = {
            label: float(probability) for label, probability in zip(labels, probability_row)
        }
        predicted_label = max(class_probabilities, key=class_probabilities.get)
        predicted_confidence = class_probabilities[predicted_label]
        threshold_no_call = predicted_confidence < settings.no_call_threshold
        if predicted_confidence < settings.no_call_threshold:
            predicted_label = "uncertain"
        results.append(
            _decision(
                profile,
                predicted_label,
                predicted_confidence,
                threshold_no_call,
                class_probabilities,
                genes,
            )
        )
    return results, "xgboost-local"


def _model_frame(hits: list[dict[str, Any]], feature_columns: list[str]) -> pd.DataFrame:
    canonical_columns = {
        _canonical(column): column
        for column in feature_columns
        if not column.startswith("antibiotic_")
    }
    present = {
        canonical_columns[_canonical(str(hit["gene_symbol"]))]
        for hit in hits
        if _canonical(str(hit["gene_symbol"])) in canonical_columns
    }
    rows = []
    for profile in ANTIBIOTICS:
        row = {column: 0 for column in feature_columns}
        for gene in present:
            row[gene] = 1
        one_hot_column = f"antibiotic_{profile.name.lower()}"
        if one_hot_column not in row:
            raise RuntimeError(f"Model schema does not support {profile.name}.")
        row[one_hot_column] = 1
        rows.append(row)
    return pd.DataFrame(rows, columns=feature_columns, dtype="int8")


def _decision(
    profile,
    predicted_label: str,
    predicted_confidence: float,
    threshold_no_call: bool,
    class_probabilities: dict[str, float],
    genes: list[str],
) -> dict[str, Any]:
    markers = matching_markers(genes, profile)
    call = CLASS_TO_CALL[predicted_label]
    confidence = (
        predicted_confidence
        if threshold_no_call
        else class_probabilities[predicted_label]
    )
    if markers:
        evidence_type = "Known resistance marker"
        evidence = ", ".join(markers)
    elif threshold_no_call:
        evidence_type = "Statistical association only"
        evidence = "The strongest model signal did not meet the minimum confidence threshold."
    elif call == "No-call":
        evidence_type = "Statistical association only"
        evidence = "Model evidence is weak, conflicting, or classified as uncertain."
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
        "resistance_probability": round(class_probabilities["likely to fail"] * 100, 1),
        "evidence_type": evidence_type,
        "evidence": evidence,
        "class_probabilities": {
            CLASS_TO_CALL[label]: round(probability * 100, 1)
            for label, probability in class_probabilities.items()
        },
    }

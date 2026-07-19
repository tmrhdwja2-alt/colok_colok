"""FastAPI entry point for the Colok Colok research prototype."""

from pathlib import Path
import asyncio
import logging
import tempfile
import time
from uuid import uuid4

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.amrfinder import run_amrfinder
from app.config import settings
from app.fasta import FastaValidationError, validate_fasta


BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Colok Colok", version="0.1.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
logger = logging.getLogger(__name__)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Return a stable JSON contract for unexpected API failures."""
    logger.error(
        "Unhandled error while processing %s",
        request.url.path,
        exc_info=exc,
    )
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            {"error": "The analysis service encountered an unexpected error."},
            status_code=500,
        )
    return JSONResponse({"error": "Internal server error."}, status_code=500)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"app_mode": settings.app_mode},
    )


@app.get("/health")
async def health():
    model_path = Path(settings.model_path)
    if not model_path.is_absolute():
        model_path = BASE_DIR.parent / model_path
    return {
        "status": "ok",
        "annotation_mode": settings.app_mode,
        "prediction_engine": "xgboost-local",
        "model_available": model_path.is_file(),
    }


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    started = time.perf_counter()
    allowed = (".fa", ".fasta", ".fna")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed:
        return JSONResponse({"error": "Upload a .fa, .fasta, or .fna file."}, status_code=400)

    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        return JSONResponse({"error": f"File exceeds the {settings.max_upload_mb} MB limit."}, status_code=413)
    try:
        quality = validate_fasta(content)
    except FastaValidationError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)

    sample_id = f"GF-{uuid4().hex[:8].upper()}"
    try:
        with tempfile.TemporaryDirectory(prefix="colok-colok-") as directory:
            fasta_path = Path(directory) / f"sample{suffix}"
            fasta_path.write_bytes(content)
            hits, annotation_engine = await asyncio.to_thread(
                run_amrfinder,
                fasta_path,
            )
            hit_dicts = [hit.to_dict() for hit in hits]
            predictions, model_engine = await asyncio.to_thread(
                _predict,
                hit_dicts,
            )
    except (RuntimeError, TimeoutError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)

    elapsed = round(time.perf_counter() - started, 2)
    return {
        "sample_id": sample_id,
        "filename": file.filename,
        "species": "Klebsiella pneumoniae",
        "quality": {
            "status": quality.status,
            "contigs": quality.contigs,
            "total_bases": quality.total_bases,
            "n_fraction": round(quality.n_fraction * 100, 2),
            "gc_fraction": round(quality.gc_fraction * 100, 2),
            "warnings": quality.warnings,
        },
        "annotation_engine": annotation_engine,
        "model_engine": model_engine,
        "amr_hits": hit_dicts,
        "predictions": predictions,
        "elapsed_seconds": elapsed,
        "disclaimer": "Research prototype only. Confirm every result with standard laboratory testing and qualified professional review.",
    }


def _predict(hit_dicts: list[dict]):
    """Load the ML runtime only after AMRFinderPlus releases its resources."""
    from app.predictor import predict

    return predict(hit_dicts)

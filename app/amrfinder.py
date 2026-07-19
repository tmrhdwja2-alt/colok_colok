"""AMRFinderPlus execution and structured feature extraction."""

from dataclasses import asdict, dataclass
import csv
import io
from pathlib import Path
import shutil
import subprocess

from app.config import settings


@dataclass(frozen=True)
class AmrHit:
    gene_symbol: str
    element_name: str
    element_type: str
    subclass: str
    identity: float | None
    coverage: float | None
    method: str

    def to_dict(self) -> dict:
        return asdict(self)


def run_amrfinder(fasta_path: Path) -> tuple[list[AmrHit], str]:
    if settings.app_mode == "demo":
        return _demo_hits(fasta_path), "demo"

    executable = shutil.which("amrfinder")
    if not executable:
        return _demo_hits(fasta_path), "demo"

    command = [
        executable,
        "--nucleotide",
        str(fasta_path),
        "--organism",
        "Klebsiella_pneumoniae",
        "--plus",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"AMRFinderPlus failed: {completed.stderr.strip()[:400]}")
    return _parse_tsv(completed.stdout), "amrfinderplus"


def _parse_tsv(output: str) -> list[AmrHit]:
    rows = csv.DictReader(io.StringIO(output), delimiter="\t")
    hits = []
    for row in rows:
        hits.append(
            AmrHit(
                gene_symbol=row.get("Gene symbol") or row.get("Gene") or "Unspecified",
                element_name=row.get("Element name") or row.get("Protein name") or "AMR element",
                element_type=row.get("Type") or "AMR",
                subclass=row.get("Subclass") or row.get("Class") or "Unclassified",
                identity=_float_or_none(row.get("% Identity to reference sequence")),
                coverage=_float_or_none(row.get("% Coverage of reference sequence")),
                method=row.get("Method") or "AMRFinderPlus",
            )
        )
    return hits


def _float_or_none(value: str | None) -> float | None:
    try:
        return round(float(value), 2) if value else None
    except ValueError:
        return None


def _demo_hits(fasta_path: Path) -> list[AmrHit]:
    """Return deterministic, clearly labeled demo evidence when the binary is absent."""
    checksum = sum(fasta_path.read_bytes())
    catalog = [
        AmrHit("blaSHV-1", "Broad-spectrum beta-lactamase SHV-1", "AMR", "BETA-LACTAM", 99.8, 100.0, "DEMO"),
        AmrHit("oqxA", "Multidrug efflux transporter OqxA", "AMR", "QUINOLONE", 98.7, 99.2, "DEMO"),
        AmrHit("fosA", "Fosfomycin resistance protein FosA", "AMR", "FOSFOMYCIN", 100.0, 100.0, "DEMO"),
        AmrHit("blaKPC-2", "Carbapenem-hydrolyzing beta-lactamase KPC-2", "AMR", "CARBAPENEM", 100.0, 100.0, "DEMO"),
    ]
    count = 2 + (checksum % 3)
    return catalog[:count]


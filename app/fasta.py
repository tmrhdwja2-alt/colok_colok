"""Strict, defensive validation for assembled bacterial FASTA input."""

from dataclasses import dataclass
import re


VALID_BASES = set("ACGTNRYKMSWBDHV")


@dataclass(frozen=True)
class FastaQuality:
    contigs: int
    total_bases: int
    n_fraction: float
    gc_fraction: float
    status: str
    warnings: tuple[str, ...]


class FastaValidationError(ValueError):
    """Raised when an upload is not a usable assembled FASTA file."""


def validate_fasta(raw: bytes) -> FastaQuality:
    if not raw:
        raise FastaValidationError("The uploaded file is empty.")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FastaValidationError("FASTA must be UTF-8 plain text.") from exc

    headers = 0
    sequences: list[str] = []
    current: list[str] = []
    for line_number, original_line in enumerate(text.splitlines(), 1):
        line = original_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if len(line) == 1:
                raise FastaValidationError(f"Missing FASTA identifier at line {line_number}.")
            if current:
                sequences.append("".join(current))
                current = []
            headers += 1
        else:
            if headers == 0:
                raise FastaValidationError("Sequence data appears before the first FASTA header.")
            sequence = re.sub(r"\s+", "", line).upper()
            invalid = sorted(set(sequence) - VALID_BASES)
            if invalid:
                raise FastaValidationError(
                    f"Invalid nucleotide symbol(s) at line {line_number}: {', '.join(invalid)}"
                )
            current.append(sequence)
    if current:
        sequences.append("".join(current))
    if not sequences or headers != len(sequences):
        raise FastaValidationError("Each FASTA record must contain a nucleotide sequence.")

    joined = "".join(sequences)
    total = len(joined)
    if total < 500:
        raise FastaValidationError("The assembly is too short for analysis (minimum: 500 bases).")

    n_fraction = joined.count("N") / total
    gc_fraction = (joined.count("G") + joined.count("C")) / total
    warnings = []
    if n_fraction > 0.05:
        warnings.append("More than 5% of bases are ambiguous (N).")
    if headers > 500:
        warnings.append("The assembly is highly fragmented (more than 500 contigs).")
    status = "Review recommended" if warnings else "Passed"
    return FastaQuality(headers, total, n_fraction, gc_fraction, status, tuple(warnings))


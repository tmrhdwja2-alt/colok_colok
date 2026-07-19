"""Domain constants and deterministic safety gates."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AntibioticProfile:
    name: str
    drug_class: str
    target: str
    resistance_markers: tuple[str, ...]


ANTIBIOTICS = (
    AntibioticProfile(
        "Meropenem",
        "Carbapenem",
        "Penicillin-binding proteins",
        ("blaKPC", "blaNDM", "blaOXA-48", "blaVIM", "blaIMP", "ompK35", "ompK36"),
    ),
    AntibioticProfile(
        "Ciprofloxacin",
        "Fluoroquinolone",
        "DNA gyrase / topoisomerase IV",
        ("gyrA", "parC", "qnrA", "qnrB", "qnrS", "aac(6')-Ib-cr", "oqxA", "oqxB"),
    ),
    AntibioticProfile(
        "Gentamicin",
        "Aminoglycoside",
        "30S ribosomal subunit",
        ("aac(3)", "aac(6')", "ant(2'')", "aph(3')", "armA", "rmtB", "rmtF"),
    ),
    AntibioticProfile(
        "Ceftazidime",
        "Third-generation cephalosporin",
        "Penicillin-binding proteins",
        ("blaCTX-M", "blaSHV", "blaTEM", "blaDHA", "blaCMY", "blaKPC", "blaNDM"),
    ),
)


def matching_markers(gene_names: list[str], profile: AntibioticProfile) -> list[str]:
    """Return detected markers relevant to an antibiotic profile."""
    matches = []
    for gene in gene_names:
        normalized = gene.lower()
        if any(marker.lower() in normalized for marker in profile.resistance_markers):
            matches.append(gene)
    return sorted(set(matches))


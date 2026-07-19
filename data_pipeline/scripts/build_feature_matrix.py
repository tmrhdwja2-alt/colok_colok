#!/usr/bin/env python3
"""
Module 01 (final step): aggregate raw AMRFinderPlus TSV reports into structured,
model-ready tables.

Reads every file in amrfinder_raw/<genome_id>.tsv and produces:

  amr_hits_long.csv       - one row per (genome_id, detected element): the full
                             annotated hit list (gene symbol, class, subclass,
                             identity/coverage, element type). This is the audit trail.
  amr_gene_matrix.csv      - wide format: one row per genome_id, one column per AMR gene
                             symbol seen anywhere in the cohort, 1/0 presence-absence.
                             This is the feature matrix for Module 02's per-antibiotic model.
  amr_subclass_matrix.csv  - wide format: one row per genome_id, one column per drug
                             subclass (e.g. CARBAPENEM, FLUOROQUINOLONE), 1 if genome
                             carries >=1 AMR gene/mutation annotated to that subclass.
                             Coarser signal, useful for the antibiotic-compatibility gate.

Only rows with Type == AMR (acquired resistance genes + resistance-conferring point
mutations) are used for the AMR matrices - VIRULENCE and STRESS rows are dropped, since
they are not antimicrobial-resistance determinants.
"""
import csv
import glob
import os
import sys

RAW_DIR = sys.argv[1] if len(sys.argv) > 1 else "amrfinder_raw"
OUT_DIR = sys.argv[2] if len(sys.argv) > 2 else "."

long_rows = []
gene_by_genome = {}
subclass_by_genome = {}

for path in sorted(glob.glob(os.path.join(RAW_DIR, "*.tsv"))):
    genome_id = os.path.basename(path).replace(".tsv", "")
    genes = set()
    subclasses = set()
    with open(path) as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if row.get("Type") != "AMR":
                continue
            gene = row.get("Element symbol", "").strip()
            subclass = row.get("Subclass", "").strip()
            long_rows.append({
                "genome_id": genome_id,
                "gene_symbol": gene,
                "element_name": row.get("Element name", "").strip(),
                "type": row.get("Type", "").strip(),
                "subtype": row.get("Subtype", "").strip(),
                "class": row.get("Class", "").strip(),
                "subclass": subclass,
                "pct_identity": row.get("% Identity to reference", "").strip(),
                "pct_coverage": row.get("% Coverage of reference", "").strip(),
                "method": row.get("Method", "").strip(),
            })
            if gene:
                genes.add(gene)
            if subclass and subclass != "NA":
                subclasses.add(subclass)
    gene_by_genome[genome_id] = genes
    subclass_by_genome[genome_id] = subclasses

all_genes = sorted(set().union(*gene_by_genome.values())) if gene_by_genome else []
all_subclasses = sorted(set().union(*subclass_by_genome.values())) if subclass_by_genome else []

os.makedirs(OUT_DIR, exist_ok=True)

with open(os.path.join(OUT_DIR, "amr_hits_long.csv"), "w", newline="") as f:
    fields = ["genome_id", "gene_symbol", "element_name", "type", "subtype", "class",
              "subclass", "pct_identity", "pct_coverage", "method"]
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(long_rows)

with open(os.path.join(OUT_DIR, "amr_gene_matrix.csv"), "w", newline="") as f:
    fields = ["genome_id"] + all_genes
    w = csv.writer(f)
    w.writerow(fields)
    for gid in sorted(gene_by_genome):
        genes = gene_by_genome[gid]
        w.writerow([gid] + [1 if g in genes else 0 for g in all_genes])

with open(os.path.join(OUT_DIR, "amr_subclass_matrix.csv"), "w", newline="") as f:
    fields = ["genome_id"] + all_subclasses
    w = csv.writer(f)
    w.writerow(fields)
    for gid in sorted(subclass_by_genome):
        subs = subclass_by_genome[gid]
        w.writerow([gid] + [1 if s in subs else 0 for s in all_subclasses])

print(f"genomes processed: {len(gene_by_genome)}")
print(f"distinct AMR gene symbols (feature columns): {len(all_genes)}")
print(f"distinct AMR subclasses (feature columns): {len(all_subclasses)}")
print(f"total AMR hit rows: {len(long_rows)}")

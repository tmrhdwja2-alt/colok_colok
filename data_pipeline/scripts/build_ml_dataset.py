#!/usr/bin/env python3
"""
Module 02: join the gene feature matrix with the resolved labels into one
ML-ready table.

Reads:
  amr_gene_matrix.csv   - genome_id x gene_symbol, 0/1 (feature matrix)
  amr_labels_final.csv  - genome_id x antibiotic, one resolved final_call each

Writes:
  ml_dataset_gene.csv   - one row per (genome_id, antibiotic) pair that has both
                           a label and a gene profile: genome_id, antibiotic,
                           final_call (target), final_phenotype, then one 0/1
                           column per AMR gene symbol.

This is a long-format table covering all 5 antibiotics at once (unlike
example_training_table_meropenem.csv, which is a single-antibiotic wide
example) - filter on `antibiotic` to get a per-drug training table, e.g.
`df[df.antibiotic == "meropenem"]`. `final_call` includes "uncertain" rows;
drop those before training if a binary target is needed.

Usage:
    python3 build_ml_dataset.py [gene_matrix.csv] [labels.csv] [out.csv]
"""
import csv
import sys

GENE_MATRIX = sys.argv[1] if len(sys.argv) > 1 else "amr_gene_matrix.csv"
LABELS = sys.argv[2] if len(sys.argv) > 2 else "amr_labels_final.csv"
OUT = sys.argv[3] if len(sys.argv) > 3 else "ml_dataset_gene.csv"

with open(GENE_MATRIX, newline="") as f:
    reader = csv.reader(f)
    gene_header = next(reader)
    gene_cols = gene_header[1:]
    genes_by_genome = {row[0]: row[1:] for row in reader}

with open(LABELS, newline="") as f:
    label_rows = list(csv.DictReader(f))

fields = ["genome_id", "antibiotic", "final_call", "final_phenotype"] + gene_cols

n_written, n_missing_genes = 0, 0
with open(OUT, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(fields)
    for row in label_rows:
        gid = row["genome_id"]
        gene_values = genes_by_genome.get(gid)
        if gene_values is None:
            n_missing_genes += 1
            continue
        w.writerow([gid, row["antibiotic"], row["final_call"], row["final_phenotype"]] + gene_values)
        n_written += 1

print(f"label pairs read: {len(label_rows)}")
print(f"dropped (no gene profile for genome_id, e.g. failed AMRFinder run): {n_missing_genes}")
print(f"rows written to {OUT}: {n_written}")
print(f"columns: {len(fields)} (4 metadata/target + {len(gene_cols)} gene features)")

# Data pipeline — how the bundled model's training data was built

This documents, end to end, how `models/best_model_xgboost_final.pkl`'s training data
(`ml_dataset_gene_final.csv` and its train-only-SMOTE variant) was produced. It complements the
model description in the top-level [`README.md`](../README.md) with the full data provenance and
reproduction steps required by the challenge brief's Module 01/02 documentation requirement.

Source data and full-scale scripts (including the 5-antibiotic, 1,000-genome raw dataset this was
drawn from) live outside this repo; this folder contains the exact scripts used, copied in for
transparency and reproducibility, along with the derived documentation.

## Pipeline overview

```
BV-BRC genome_amr API   ──(evidence=Laboratory Method, phenotype non-empty)──>  labels
BV-BRC genome API       ──(genome_quality=Good, CheckM completeness>=90%, contam<=5%)──>  genome list
BV-BRC genome_sequence API  ──>  reconstructed multi-FASTA per genome
        │
        ▼  scripts/build_features.py   (AMRFinderPlus via the official ncbi/amr Docker image)
amrfinder_raw/<id>.tsv   (raw AMRFinderPlus report per genome)
        │
        ▼  scripts/build_feature_matrix.py
amr_gene_matrix.csv      (genome_id x gene_symbol -> 0/1, the feature matrix)
        │
        ▼  scripts/build_ml_dataset.py   (join with resolved labels)
ml_dataset_gene.csv      (long format, all 5 antibiotics, includes genome_id)
        │
        ▼  filtered to this app's 3-antibiotic scope, id columns dropped
ml_dataset_gene_final.csv   (antibiotic, final_call, 398 gene/mutation feature columns — bundled model's training source)
        │
        ▼  scripts/smote_oversample_final_call.py
ml_dataset_gene_final_smote.csv   (train-only SMOTE oversampling, see below)
```

## 1. Source data (BV-BRC)

*Klebsiella pneumoniae* (BV-BRC `taxon_id=573`) genomes and lab-measured antimicrobial
susceptibility results were pulled from **BV-BRC** (Bacterial and Viral Bioinformatics Resource
Center, https://www.bv-brc.org), a NIAID/NIH-funded public resource, via its REST Data API.

- Genomes were quality-filtered (`genome_quality=Good`, CheckM completeness ≥90%, contamination
  ≤5%) and prioritized by antibiotic-label coverage, seed=42 for reproducibility.
- Only AMR records already carrying an explicit **Resistant / Susceptible / Intermediate**
  category from a laboratory method were kept — no MIC-only, uninterpreted records are included.
- The full pull covered 5 antibiotics (meropenem, ciprofloxacin, gentamicin, ceftazidime,
  colistin) across 1,000 genomes. **This app's model only covers the 3 best-supported antibiotics**
  — meropenem, ciprofloxacin, gentamicin — dropping ceftazidime and the data-sparse colistin.

See `LICENSE_ATTRIBUTION.md` for the required BV-BRC citation and funding acknowledgment.

## 2. Labeling rule

Full derivation is in `LABELING_RULE.md`. Summary:

| Lab `resistant_phenotype` | Final call |
|---|---|
| Resistant | likely to fail |
| Susceptible | likely to work |
| Intermediate | uncertain |
| Conflicting across records for the same genome-antibiotic pair | uncertain |

`Intermediate` and genuine cross-record conflicts both resolve to `uncertain` rather than being
forced to a side — consistent with the brief's guidance that "returning no-call for weak or
conflicting evidence is a strength." Only 0.02% of pairs in the full pool hit the conflict case.

## 3. AMR gene/mutation annotation (AMRFinderPlus)

`scripts/build_features.py` runs each genome's FASTA through the official `ncbi/amr` Docker image:

```
docker run --rm -v <dir>:/data ncbi/amr amrfinder -n /data/<id>.fna \
  -O Klebsiella_pneumoniae --plus -o /data/<id>.out.tsv
```

`-O Klebsiella_pneumoniae` enables the organism-specific point-mutation catalog (e.g. porin loss
mutations like `ompK36_K231SfsTer16`, correctly tagged `Class=BETA-LACTAM, Subclass=CARBAPENEM`)
on top of the universal acquired-resistance-gene database. `--plus` also reports stress/virulence
genes, which are kept in the audit trail but excluded from the model's feature set.

`scripts/build_feature_matrix.py` collapses all per-genome TSVs into `amr_gene_matrix.csv`
(genome_id x gene_symbol -> 0/1), keeping only `Type == AMR` rows.

Both scripts skip already-processed genomes, so a full re-run is safe to resume at any point.

## 4. Joining features with labels

`scripts/build_ml_dataset.py` joins `amr_gene_matrix.csv` with the resolved labels on
`genome_id`, producing one row per (genome, antibiotic) pair that has both. This long-format
table (`ml_dataset_gene.csv`) covers all 5 antibiotics; `ml_dataset_gene_final.csv` — the file
actually used to train the bundled model — is this table filtered down to the app's 3-antibiotic
scope, with `genome_id`/`final_phenotype` dropped so each row is just
`antibiotic, final_call, <398 gene/mutation columns>`.

Result: **2,997 rows** (999 each for meropenem, ciprofloxacin, gentamicin) x 398 AMR gene/mutation
feature columns.

| final_call | count |
|---|---:|
| likely to work | 1,564 |
| likely to fail | 1,357 |
| uncertain | 76 |

## 5. Train-only SMOTE oversampling (`scripts/smote_oversample_final_call.py`)

`final_call` is imbalanced, particularly `uncertain` (76 rows, 2.5% of the data). To make the
class distribution usable for AutoML/GCP training without leaking synthetic data into evaluation:

1. **Split first**: stratified 80/10/10 train/validation/test split on the *original* data
   (preserves each split's natural class ratio, including the imbalance).
2. **SMOTE only the training split**, oversampling `likely to fail` and `uncertain` up to the
   majority class (`likely to work`) count. Validation and test are left untouched — they must
   reflect the real-world distribution for an honest evaluation, and oversampling before the split
   would let synthetic rows derived from a test-set genome leak into training (or vice versa).
3. A `data_split` column (`TRAIN` / `VALIDATE` / `TEST`) is written to the output CSV so a
   downstream trainer (e.g. Vertex AI AutoML's manual/predefined split) can honor this exact split
   instead of re-randomizing it.
4. Gene/mutation column names are sanitized (non-alphanumeric characters, e.g. in
   `aac(6')-Ib-cr`, replaced with `_`) since some downstream training platforms reject the raw
   AMRFinderPlus symbol punctuation as column identifiers.

| split | rows before SMOTE | rows after SMOTE |
|---|---:|---:|
| train | 2,397 (1,251 work / 1,085 fail / 61 uncertain) | 3,753 (1,251 / 1,251 / 1,251) |
| validation | 300 (untouched) | 300 |
| test | 300 (untouched) | 300 |
| **total** | **2,997** | **4,353** |

```bash
python3 scripts/smote_oversample_final_call.py
```

Reads `ml_dataset_gene_final.csv`, writes `ml_dataset_gene_final_smote.csv` in the same directory.
Requires `pandas`, `scikit-learn`, `imbalanced-learn`.

## 6. Known limitations

- **Colistin and ceftazidime are out of scope** for this app (dropped for data sparsity /
  narrower support), even though they exist in the wider 5-antibiotic source pool.
- **Sequence-homology leakage risk**: genomes sharing near-identical strains/outbreak clusters can
  end up split across train/validation/test, inflating held-out metrics. The organizer's
  genetically-grouped held-out split (if provided) should be used to re-check the reported metrics
  before trusting them beyond this prototype.
- **`uncertain` remains small** (76 of 2,997 rows) even after train-only SMOTE — validation/test
  only have 7-8 `uncertain` examples each, so metrics on that class specifically are noisy.

## Source & license

BV-BRC (NIAID/NIH Grant U24AI183849); cite Olson RD et al., *Nucleic Acids Res.* 2022 gkac1003.
AMRFinderPlus is NCBI public-domain software (github.com/ncbi/amr). Full attribution and terms in
`LICENSE_ATTRIBUTION.md`.

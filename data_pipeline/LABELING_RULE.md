# Labeling Rule — from lab measurement to final call

Documents how each row in `amr_labels_final.csv` was derived, satisfying the challenge brief's
requirement for "a documented rule for likely to fail / likely to work / uncertain" and "one
final label for each genome-antibiotic pair."

## Step 1 — source filter

Only BV-BRC `genome_amr` records tagged `evidence=Laboratory Method` (excludes BV-BRC's own
computational/ML-predicted phenotypes) **and carrying a non-empty `resistant_phenotype`** were
pulled. Records that only had a raw MIC value with no categorical Resistant/Susceptible/
Intermediate interpretation were excluded at the query stage — this dataset contains only pairs
BV-BRC already labeled with a category, per the user's explicit request. (An earlier version of
this dataset also pulled MIC-only records and flagged them `no_call_available`; that version was
deleted and rebuilt as this categorical-only version.)

## Step 2 — category -> call mapping

| Source `resistant_phenotype` | Final call |
|---|---|
| Resistant | likely to fail |
| Susceptible | likely to work |
| Intermediate | uncertain |
| (present but conflicting across multiple records for the same pair) | uncertain |

`Intermediate` maps to `uncertain` rather than either side, because CLSI/EUCAST define it as a
genuinely borderline zone (drug may still work at higher/local dosing, but is not reliably
effective) — collapsing it into "likely to work" or "likely to fail" would misrepresent the
underlying lab call.

## Step 3 — one final label per genome-antibiotic pair

A single genome can have more than one lab record for the same antibiotic (repeat testing,
different methods, or different source studies). For every `(genome_id, antibiotic)` pair, all
matching records were grouped and resolved:

1. Collect the set of distinct `resistant_phenotype` values across all records for the pair.
2. **Exactly one distinct value** → use it directly.
3. **More than one distinct value** (different lab tests genuinely disagree, e.g. broth dilution
   says Intermediate but disk diffusion says Susceptible for the same isolate) →
   `final_call = uncertain`, and `conflicting_evidence` records exactly which values conflicted.
   Only 3 of 17,420 categorical pairs (0.02%) hit this case.

This conflict rule is deliberately conservative: rather than majority-voting away disagreement, a
genuine conflict between independent lab tests becomes an explicit `uncertain` label, consistent
with the brief's Module 03 requirement that "returning no-call for weak or conflicting evidence is
a strength."

## Result (full categorical-only pool, before the 1,000-genome selection for AMRFinderPlus)

- 17,420 genome-antibiotic pairs, every one with a categorical label (no MIC-only rows).
- 8,623 `likely to fail`, 8,323 `likely to work`, 474 `uncertain` (Intermediate or conflict).
- 5,459 distinct genomes carry at least one categorical label.
- `amr_labels_final.csv` in this folder is the subset of these pairs restricted to the 1,000
  genomes actually run through AMRFinderPlus (4,141 pairs). The full 17,420-pair /
  5,459-genome pool is in `raw/amr_labels_all_categorical_resolved.csv` /
  `raw/genome_ids_categorical.txt` for scaling up later.

## Known limitation: colistin is still the sparsest antibiotic

Restricting to categorical-only records does not fix colistin's underlying data scarcity — it
just means the "missing" colistin pairs are absent entirely rather than present-but-uninterpreted.
Colistin will have visibly fewer rows in `amr_labels_final.csv` than the other 4 antibiotics. See
`README.md` for antibiotic-level counts.

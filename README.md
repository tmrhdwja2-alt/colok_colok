# Colok Colok

Colok Colok is a defensive research prototype for the Hack-Nation Genome Firewall challenge. It accepts a reconstructed *Klebsiella pneumoniae* genome in FASTA format, detects existing antimicrobial-resistance evidence with AMRFinderPlus, and predicts antibiotic response with a bundled XGBoost model.

> Research prototype only. Every result must be confirmed by standard laboratory testing and qualified professional review. This software is not a medical device and must not make treatment decisions autonomously.

## Supported scope

- Species: *Klebsiella pneumoniae* only
- Input: reconstructed nucleotide assembly (`.fa`, `.fasta`, or `.fna`)
- Antibiotics: meropenem, ciprofloxacin, and gentamicin
- Output: Likely to Work, Likely to Fail, or No-call, with model confidence and supporting AMR evidence
- Explicitly excluded: sample collection, sequencing, assembly, species identification, mixed-sample separation, organism design, and organism modification

## Pipeline

1. Validate FASTA structure, nucleotide alphabet, size, ambiguity, and fragmentation.
2. Run AMRFinderPlus in nucleotide mode for *K. pneumoniae*.
3. Convert detected genes and mutations into the bundled model's 401-feature schema.
4. Add the antibiotic one-hot features and run local XGBoost inference.
5. Apply the confidence-based No-call policy and species-level molecular-target gate.
6. Combine model output with known AMR evidence and render the decision report.

## Bundled model

The application loads `models/best_model_xgboost_final.pkl` with `joblib`. The trusted artifact contains:

- an `XGBClassifier` with three output classes;
- a `LabelEncoder` for `likely to fail`, `likely to work`, and `uncertain`;
- the exact ordered list of 401 input features;
- held-out evaluation metadata.

Artifact SHA-256:

```text
68484b94a91dfd1cf4ab96b76d57bf7af351d133d75e33405ad559b3076b2e42
```

The artifact metadata reports that it was trained on `ml_dataset_gene_final.csv` without SMOTE, using a stratified 80/20 split and `random_state=42`.

| Reported metric | Value |
| --- | ---: |
| Macro recall | 0.7059 |
| Macro F1 | 0.7116 |
| Balanced accuracy | 0.7059 |

These figures are artifact metadata, not an independent reproduction. For challenge evaluation, the model should also be tested on the organizer's genetically grouped held-out split to rule out sequence-homology leakage.

Pickle/joblib artifacts can execute code during loading. Only replace this file with a trusted artifact produced by the team, and update the documented checksum whenever it changes.

The Docker image installs the Bioconda package `ncbi-amrfinderplus=4.2.7` and downloads its reference database during the image build.

## Decision policy

The model returns probabilities for all three classes. The highest-probability class is used unless its confidence is below `NO_CALL_THRESHOLD`, in which case the result is No-call. A model prediction is kept separate from known AMRFinderPlus evidence; statistical importance is never presented as proof of biological causality.

## Local development

Python 3.11 or 3.12 and AMRFinderPlus are recommended. Without the AMRFinderPlus executable, the app returns deterministic, clearly labeled demo annotations. The XGBoost model is always used for prediction.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open `http://localhost:8000` and upload `sample_data/demo_klebsiella.fasta`.

For the full containerized pipeline:

```bash
docker build -t colok-colok .
docker run --rm -p 10000:10000 --env-file .env colok-colok
```

## Configuration

| Variable | Purpose |
| --- | --- |
| `APP_MODE` | Controls annotation fallback labeling; use `production` on Render |
| `MAX_UPLOAD_MB` | Upload limit, default `10` |
| `MODEL_PATH` | Trusted joblib model bundle path |
| `NO_CALL_THRESHOLD` | Minimum winning-class confidence, default `0.60` |

## Safety and privacy

- Uploaded assemblies are processed in an isolated temporary directory and deleted after each request.
- File type, size, and nucleotide symbols are validated before external processes run.
- Subprocess arguments are never built through a shell.
- The service is defensive by construction and does not generate biological sequences or optimization advice.
- Production deployments should add authentication, rate limiting, audit logging, encryption policies, and an approved clinical governance process.

## API

- `GET /health` - model and service health check
- `POST /api/analyze` - multipart upload using the `file` field

## License

Prototype code is provided for hackathon demonstration and research evaluation. AMRFinderPlus is developed by NCBI and is public domain. Review the licenses and attribution requirements of every training dataset and model artifact before redistribution.

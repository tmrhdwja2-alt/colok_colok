# Genome Firewall

Genome Firewall is a defensive research prototype for the Hack-Nation Genome Firewall challenge. It accepts a quality-checked, reconstructed *Klebsiella pneumoniae* genome in FASTA format, detects existing antimicrobial-resistance evidence with AMRFinderPlus, and sends structured gene features to a GCP Vertex AI AutoML endpoint. The report combines model output with a deterministic molecular-target gate and transparent evidence categories.

> Research prototype only. Every result must be confirmed by standard laboratory testing and qualified professional review. This software is not a medical device and must not make treatment decisions autonomously.

## Supported scope

- Species: *Klebsiella pneumoniae* only
- Input: reconstructed nucleotide assembly (`.fa`, `.fasta`, or `.fna`)
- Antibiotics: meropenem, ciprofloxacin, and gentamicin
- Output: Likely to Work, Likely to Fail, or No-call, with calibrated confidence and evidence
- Explicitly excluded: sample collection, sequencing, assembly, species identification, mixed-sample separation, organism design, and organism modification

## Pipeline

1. Validate FASTA structure, nucleotide alphabet, size, ambiguity, and fragmentation.
2. Run AMRFinderPlus in nucleotide mode for *K. pneumoniae*.
3. Convert detected genes and mutations into the exact 398-column presence/absence schema used by `ml_dataset_gene_final_smote.csv`.
4. Send one instance per antibiotic to a Vertex AI AutoML Endpoint.
5. Apply confidence thresholds and the species-level molecular-target gate.
6. Combine model output with known AMR evidence and render the decision report.

## Local development

Python 3.11 and AMRFinderPlus are recommended. Without the AMRFinderPlus executable, the app returns deterministic, clearly labeled demo annotations. This fallback is for interface demonstrations only.

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
docker build -t genome-firewall .
docker run --rm -p 10000:10000 --env-file .env genome-firewall
```

## Training dataset

The model contract is based on:

`hack_nation/datasets/klebsiella_pneumoniae/ml_dataset_gene_final_smote.csv`

The current file contains 4,353 rows and 401 columns: `antibiotic`, the three-class label `final_call`, 398 binary AMR gene or mutation features, and the organizer-provided `data_split`. The split contains 3,753 training, 300 validation, and 300 test rows. `data_split` is used for evaluation partitioning and removed from model inputs to prevent leakage. The source dataset is intentionally not copied into this repository. Run the preparation script against the organizer-provided file:

```bash
python scripts/prepare_automl_data.py \
  --input /path/to/ml_dataset_gene_final_smote.csv \
  --output training_data/automl_training.csv
```

Upload the generated 400-column CSV to Cloud Storage and use `final_call` as the Vertex AI AutoML Tabular classification target. Keep `antibiotic` as a categorical input and all remaining columns as numeric binary inputs. Preserve the organizer split when creating the corresponding Vertex AI training, validation, and test data sources; do not randomly re-split rows.

> SMOTE is useful only inside the training partition. Do not apply synthetic oversampling before creating genetically grouped train, calibration, and held-out test splits, because that can leak information and inflate evaluation results.

## Vertex AI prediction contract

The app sends three dense feature objects, one per antibiotic. The keys exactly match the training CSV schema:

```json
{
  "antibiotic": "meropenem",
  "blaKPC_2": 1,
  "ompK36_K231SfsTer16": 1,
  "oqxA": 0
}
```

Vertex AI AutoML Tabular should return one classification object per input instance. Both standard response variants below are supported (`displayNames`/`confidences` or `classes`/`scores`):

```json
{
  "displayNames": ["likely to fail", "likely to work", "uncertain"],
  "confidences": [0.91, 0.06, 0.03]
}
```

Decision thresholds are intentionally conservative:

- `p(resistant) > 0.65`: Likely to Fail
- `p(resistant) < 0.35`: Likely to Work
- otherwise: No-call

The model should be trained and calibrated with genetically grouped splits so near-identical genomes never occur in both training and test sets. Report balanced accuracy, resistant and susceptible recall, F1, AUROC, PR-AUC, Brier score, reliability, no-call rate, and called-case accuracy per antibiotic.

## Configuration

| Variable | Purpose |
| --- | --- |
| `APP_MODE` | `demo` uses deterministic UI predictions; `production` requires Vertex AI |
| `MAX_UPLOAD_MB` | Upload limit, default `10` |
| `GCP_PROJECT_ID` | GCP project containing the endpoint |
| `GCP_REGION` | Endpoint region, default `us-central1` |
| `GCP_ENDPOINT_ID` | Deployed Vertex AI Endpoint ID |
| `MODEL_SCHEMA_PATH` | Packaged list of the 398 model feature columns |
| `GOOGLE_APPLICATION_CREDENTIALS` | Local service-account JSON path |
| `GCP_SERVICE_ACCOUNT_JSON_BASE64` | Base64 service-account JSON for Render |

## Safety and privacy

- Uploaded assemblies are processed in an isolated temporary directory and deleted after each request.
- File type, size, and nucleotide symbols are validated before external processes run.
- Subprocess arguments are never built through a shell.
- The service is defensive by construction and does not generate biological sequences or optimization advice.
- Production deployments should add authentication, rate limiting, audit logging, encryption policies, and an approved clinical governance process.

## API

- `GET /health` - health and mode check
- `POST /api/analyze` - multipart upload using the `file` field

## License

Prototype code is provided for hackathon demonstration and research evaluation. AMRFinderPlus is developed by NCBI and is public domain. Review the licenses and attribution requirements of every training dataset and deployed model before redistribution.

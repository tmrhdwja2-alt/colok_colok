# Genome Firewall

Genome Firewall is a defensive research prototype for the Hack-Nation Genome Firewall challenge. It accepts a quality-checked, reconstructed *Klebsiella pneumoniae* genome in FASTA format, detects existing antimicrobial-resistance evidence with AMRFinderPlus, and sends structured gene features to a GCP Vertex AI AutoML endpoint. The report combines model output with a deterministic molecular-target gate and transparent evidence categories.

> Research prototype only. Every result must be confirmed by standard laboratory testing and qualified professional review. This software is not a medical device and must not make treatment decisions autonomously.

## Supported scope

- Species: *Klebsiella pneumoniae* only
- Input: reconstructed nucleotide assembly (`.fa`, `.fasta`, or `.fna`)
- Antibiotics: meropenem, ciprofloxacin, gentamicin, and ceftazidime
- Output: Likely to Work, Likely to Fail, or No-call, with calibrated confidence and evidence
- Explicitly excluded: sample collection, sequencing, assembly, species identification, mixed-sample separation, organism design, and organism modification

## Pipeline

1. Validate FASTA structure, nucleotide alphabet, size, ambiguity, and fragmentation.
2. Run AMRFinderPlus in nucleotide mode for *K. pneumoniae*.
3. Convert detected genes and mutations into a sparse presence/absence feature object.
4. Send the feature object to a Vertex AI AutoML Endpoint.
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

## Vertex AI prediction contract

The app sends one sparse feature object. Keys are AMRFinderPlus gene or mutation symbols and values are `1`:

```json
{
  "blaKPC-2": 1,
  "ompK36_K231SfsTer16": 1,
  "oqxA": 1
}
```

The endpoint should return one record containing `predictions`, with one object per supported antibiotic:

```json
{
  "predictions": [
    {"antibiotic": "Meropenem", "resistance_probability": 0.91},
    {"antibiotic": "Ciprofloxacin", "resistance_probability": 0.48},
    {"antibiotic": "Gentamicin", "resistance_probability": 0.18},
    {"antibiotic": "Ceftazidime", "resistance_probability": 0.79}
  ]
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

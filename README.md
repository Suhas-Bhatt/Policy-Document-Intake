# Policy Document Intake & Policy Intelligence — POC

Implementation of the architecture diagram: Flask REST API → AWS document
intake/processing pipeline → Snowflake analytics platform, for insurance
policy documents.

See the **Implementation Assumptions** block at the top of this project for
the handful of details the diagram left open (Flask deployment target,
API Gateway→S3 flow, Textract placement, JWT issuance). Every route/service
docstring also cross-references the exact diagram label it implements.

## Architecture Checklist

| # | Diagram Component | Implemented As | Status |
|---|---|---|---|
| 1 | Users / Agents | `POST /api/auth/login` (role-based JWT) | ✅ |
| 2 | Flask REST API | `app/` (routes, services, models) | ✅ |
| 3 | Amazon API Gateway | S3 proxy integration, see `aws/apigateway/s3-proxy-integration.md` | ✅ |
| 4 | Amazon S3 | `policy-documentz` bucket | ✅ |
| 5 | Amazon EventBridge | `aws/eventbridge/rule.json` | ✅ |
| 6 | AWS Lambda (Document Processor) | `aws/lambda/document_processor/handler.py` | ✅ |
| 7 | Amazon CloudWatch | Structured logging + alarm in `aws/setup-commands.md` §6 | ✅ |
| 8 | Amazon DynamoDB | `PolicyDocumentProcessing` table, `app/services/aws_service.py` | ✅ |
| 9 | Amazon SNS | Completion topic, subscribed by ops + Snowflake loader | ✅ |
| 10 | Snowflake Connector (ingestion) | `aws/lambda/snowflake_loader/handler.py` | ✅ |
| 11 | Snowflake Data Warehouse (4 tables + views) | `sql/02_tables.sql`, `sql/03_views.sql` | ✅ |
| 12 | Business Outcomes (Lookup/Status/Dashboard/Audit) | `app/services/snowflake_service.py` + routes | ✅ |

---

## Running Commands (Quick Reference)

All commands run from the project root. Tested with Python 3.12 (the
Dockerfile's version) and 3.14 locally.

### 1. First-time setup

PowerShell (Windows):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1      # if blocked: Set-ExecutionPolicy -Scope Process Bypass
pip install -r requirements-dev.txt
Copy-Item .env.example .env      # then fill in real AWS / Snowflake values
```

bash / macOS / Linux / Git Bash:

```bash
python -m venv venv
source venv/bin/activate         # Git Bash on Windows: source venv/Scripts/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Optional — Snowflake-backed routes (`/api/policies/*`, `/api/search`,
`/api/dashboard`, CSV bulk upload) need the connector, installed separately
(see PART 5 for why):

```bash
pip install -r requirements-snowflake.txt
```

### 2. Run the app

| Goal | Command | URL |
|---|---|---|
| Dev server (debug + auto-reload) | `python run.py` | http://localhost:5000/ |
| Production-style server (Linux/macOS/Docker only — gunicorn doesn't run on Windows) | `gunicorn -b 0.0.0.0:5000 -w 2 run:app` | http://localhost:5000/ |
| Docker | `docker build -t policy-intake-poc .` then `docker run --env-file .env -p 5000:5000 policy-intake-poc` | http://localhost:5000/ |

Pages and health check:

- `http://localhost:5000/` — main UI
- `http://localhost:5000/dashboard` — processing dashboard
- `http://localhost:5000/api/health` — health check (no auth)

### 3. Run the tests

```bash
pytest -v                          # all tests, mocked AWS (moto), no credentials needed
pytest tests/test_documents.py -v  # one file
pytest -k auth -v                  # tests matching a name
```

### 4. Generate and upload sample documents

Needs the app running in another terminal (`python run.py`) and a real
`API_GATEWAY_UPLOAD_URL` in `.env`.

```bash
pip install -r requirements-tools.txt
python scripts/generate_sample_pdfs.py     # writes sample_documents/*.pdf
python scripts/upload_samples.py           # uploads them through the Flask API
```

Point the upload script at a non-default server with
`FLASK_BASE_URL` (PowerShell: `$env:FLASK_BASE_URL="http://host:5000"`;
bash: `FLASK_BASE_URL=http://host:5000 python scripts/upload_samples.py`).

### 5. Provision cloud resources (one-time, needs your credentials)

- **AWS** — follow `aws/setup-commands.md` (DynamoDB → SNS → Lambdas →
  EventBridge → CloudWatch) and `aws/apigateway/s3-proxy-integration.md`
  (S3 bucket + API Gateway). Those snippets use `cp`, `zip` and `$(...)`, so
  run them in Git Bash or WSL on Windows.
- **Snowflake** — run in order: `sql/01_database_schema.sql`,
  `02_tables.sql`, `03_views.sql`, then optionally `04_seed_data.sql`.
  Bulk data: `sql/seed/policy_documents_100.csv`.

---

## Frontend

Not part of the original architecture diagram (it only draws the Flask REST
API as the interface) — added on request as a thin browser client over the
same JSON API, served directly by Flask so there's no separate server, build
step, or CORS setup to manage.

```
python run.py
```

Then open **http://localhost:5000/** in a browser. It's one page
(`app/templates/index.html` + `app/static/app.js`) that calls the existing
endpoints: log in → upload a document (or bulk-upload a policy CSV) → check
its status → look up a policy → search. `access_token` is kept in
`localStorage` and sent as `Authorization: Bearer <token>` on every
subsequent call.

There's also a **Skip login — explore as guest** button on the login card.
Since `auth_service.issue_token` accepts any `{username, role}` pair with no
password check (POC-only, see the Security Checklist), this just logs in as
`guest`/`agent` with one click instead of filling the form — handy for
quickly poking at the UI.

A second page, **http://localhost:5000/dashboard**
(`app/templates/dashboard.html` + `app/static/dashboard.js`), shows the
processing dashboard from `GET /api/dashboard` (Snowflake
`PROCESSING_DASHBOARD_VIEW`). If `snowflake-connector-python` isn't
installed, this route no longer 502s — it falls back to fixed sample rows
(`snowflake_service._dummy_processing_dashboard_metrics`) so the dashboard UI
is always browsable, and the response carries `"demo_data": true` so the page
can show a "Demo data — Snowflake not connected" badge instead of silently
passing off fake numbers as real.

Both pages are responsive (viewport meta tag + media queries at 768px/480px
in `app/static/style.css`) — forms, stat tiles, and tables reflow for phone
widths instead of just shrinking the desktop layout.

### API endpoints

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/health` | no | Health check |
| POST | `/api/auth/login` | no | JSON `{"username","role"}` → JWT |
| POST | `/api/documents/upload` | yes | multipart: `file`, `customer_id`, optional `policy_id` → `202` |
| GET | `/api/documents/<document_id>/status` | yes | Reads DynamoDB |
| POST | `/api/documents/bulk-upload` | yes | multipart: CSV `file` with the columns of `sql/seed/policy_documents_100.csv`; archived to S3 (`csv-uploads/`), loaded into Snowflake in a background thread → `202` |
| GET | `/api/policies/<policy_id>` | yes | Snowflake — `502 snowflake_unavailable` if the connector isn't installed |
| GET | `/api/search?q=...&limit=25` | yes | Snowflake — `502 snowflake_unavailable` if the connector isn't installed |
| GET | `/api/dashboard` | yes | Snowflake if available, otherwise demo data (`"demo_data": true` in the response) — never 502s |

Login and upload work today without any AWS/Snowflake setup (upload will
`502` until `API_GATEWAY_UPLOAD_URL` points at a real API Gateway — see
above). Policy lookup and search still need Snowflake configured and seeded
(`sql/seed/policy_documents_100.csv`); the dashboard works either way.

---

## Test Data

Two separate artifacts, for two separate purposes — don't confuse them:

| Artifact | Purpose | Touches Textract/Lambda? |
|---|---|---|
| `sql/seed/policy_documents_100.csv` | 100 rows to bulk-load `CURATED.CURATED_POLICY` / `CURATED.POLICY_DOCUMENT` directly, for testing `/api/policies/{id}`, `/api/search`, and the dashboard view without uploading anything | No — bypasses the whole intake pipeline |
| `sample_documents/*.pdf` (generated) | Real PDF files to actually `POST /api/documents/upload`, exercising API Gateway → S3 → EventBridge → Lambda (Textract) → DynamoDB → SNS → Snowflake loader | Yes — this is the real end-to-end path |

Generate and use the sample PDFs:

```bash
pip install -r requirements-tools.txt
python scripts/generate_sample_pdfs.py      # writes sample_documents/*.pdf

python run.py                                # in one terminal
python scripts/upload_samples.py             # in another — uploads all 10 via the real API
```

`scripts/upload_samples.py` logs in, then `POST`s each PDF to
`/api/documents/upload`. It needs `API_GATEWAY_UPLOAD_URL` in `.env` pointing
at a real, provisioned API Gateway (see `aws/apigateway/s3-proxy-integration.md`)
— it drives the real Flask→AWS path, it doesn't mock anything.

Load the CSV into Snowflake with `snowsql` or the Snowflake UI's "Load Data"
wizard against `CURATED.CURATED_POLICY` and `CURATED.POLICY_DOCUMENT` (after
running `sql/01_database_schema.sql` and `sql/02_tables.sql`).

---

## PART 5 — Setup

See **Running Commands** above for the exact setup steps per shell.

`snowflake-connector-python` is installed separately (`requirements-snowflake.txt`)
because its `cffi` dependency needs a prebuilt wheel for your exact Python
version; on very new interpreters that wheel may not exist yet, forcing a
source build that needs MSVC Build Tools. The Flask app runs fine without it
— Snowflake-backed routes (`/api/policies/*`, `/api/search`) return a clear
`502 snowflake_unavailable` instead of crashing on startup. Once you can
install it (older Python, or Build Tools available), add it with:

```bash
pip install -r requirements-snowflake.txt
```

Run locally:

```bash
python run.py
```

Expected output: `Running on http://0.0.0.0:5000`.

---

## PART 9 — How Everything Connects (Integration)

1. `.env` wires Flask to a real API Gateway URL, DynamoDB table, and
   Snowflake account.
2. `aws/setup-commands.md` provisions DynamoDB, SNS, both Lambdas, and the
   EventBridge rule against your real AWS account.
3. `sql/01_database_schema.sql` → `02_tables.sql` → `03_views.sql` →
   `04_seed_data.sql` provision Snowflake, in that order.
4. Once both sides exist, a real upload flows exactly along the diagram's
   arrows — see PART 13 below for the walkthrough.

---

## PART 10 / 12 — Testing

### Flask unit/integration tests (mocked AWS via moto, no cloud account needed)

```bash
pytest -v
```

Expected: all tests in `tests/` pass. These mock DynamoDB and the API
Gateway HTTP call, so they run with zero AWS credentials.

### Manual API testing (curl)

```bash
# 1. Log in
TOKEN=$(curl -s -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","role":"agent"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 2. Upload a document (requires a real API_GATEWAY_UPLOAD_URL in .env)
curl -X POST http://localhost:5000/api/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sample_policy.pdf" \
  -F "customer_id=CUST-001"

# 3. Check status
curl http://localhost:5000/api/documents/<document_id>/status \
  -H "Authorization: Bearer $TOKEN"

# 4. Look up a policy (requires Snowflake seeded via sql/04_seed_data.sql)
curl http://localhost:5000/api/policies/POL-1001 \
  -H "Authorization: Bearer $TOKEN"

# 5. Search
curl "http://localhost:5000/api/search?q=AUTO" \
  -H "Authorization: Bearer $TOKEN"

# 6. Bulk-load policies from CSV (requires API Gateway + Snowflake)
curl -X POST http://localhost:5000/api/documents/bulk-upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sql/seed/policy_documents_100.csv"

# 7. Dashboard metrics (real data if Snowflake is configured, demo data otherwise)
curl http://localhost:5000/api/dashboard \
  -H "Authorization: Bearer $TOKEN"
```

PowerShell equivalents for the first two calls (use `curl.exe`, since bare
`curl` is an alias for `Invoke-WebRequest`):

```powershell
$TOKEN = (curl.exe -s -X POST http://localhost:5000/api/auth/login `
  -H "Content-Type: application/json" `
  -d '{\"username\":\"alice\",\"role\":\"agent\"}' | ConvertFrom-Json).access_token

curl.exe -X POST http://localhost:5000/api/documents/upload `
  -H "Authorization: Bearer $TOKEN" `
  -F "file=@sample_documents/CUST-001_POL-1001_auto.pdf" -F "customer_id=CUST-001"
```

### AWS verification

```bash
aws s3 ls s3://policy-documentz/incoming/ --recursive
aws dynamodb get-item --table-name PolicyDocumentProcessing \
  --key '{"document_id": {"S": "<document_id>"}}'
aws logs tail /aws/lambda/policy-document-processor --follow
```

### Snowflake verification

```sql
SELECT * FROM POLICY_INTELLIGENCE.RAW.RAW_POLICY_DOCUMENTS ORDER BY ingested_at DESC LIMIT 10;
SELECT * FROM POLICY_INTELLIGENCE.CURATED.CURATED_POLICY;
SELECT * FROM POLICY_INTELLIGENCE.ANALYTICS.PROCESSING_DASHBOARD_VIEW;
```

---

## PART 13 — End-to-End Test Scenario

```
Insurance Agent
    │ POST /api/auth/login -> JWT
    ▼
POST /api/documents/upload  (file=sample.pdf, customer_id=CUST-001)
    │ Flask validates + writes DynamoDB item (status=UPLOADED)
    ▼
API Gateway PUT -> S3 (incoming/CUST-001/<doc_id>_sample.pdf)
    │ S3 emits Object Created -> EventBridge
    ▼
Lambda (document_processor): Textract -> classify -> extract fields
    │ updates DynamoDB item (status=PROCESSED) + publishes SNS
    ▼
Lambda (snowflake_loader): reads DynamoDB item -> INSERT RAW_POLICY_DOCUMENTS
    │ MERGE INTO CURATED_POLICY
    ▼
GET /api/documents/<doc_id>/status -> "PROCESSED"
GET /api/policies/POL-1001 -> curated policy record
GET /api/search?q=CUST-001 -> matching documents
```

---

## PART 14 — Error Handling

Implemented in `app/utils/errors.py` / route-level exceptions:

| Failure | Behavior |
|---|---|
| Missing/invalid JWT | `401 unauthorized` (`auth_service.require_auth`) |
| Missing file or `customer_id` | `400 validation_error` (`schemas.validate_upload_request`) |
| API Gateway/S3 upload fails | `502 upstream_service_error` (`aws_service.upload_document_via_api_gateway`) |
| Document not found | `404 not_found` |
| File exceeds `MAX_CONTENT_LENGTH` (15MB) | `413 payload_too_large` |
| Lambda processing exception | Logged, DynamoDB item marked `FAILED` with `error_details`, exception re-raised so Lambda's built-in retry/DLQ behavior applies |
| Snowflake connection fails | Uncaught exception bubbles to Flask's generic `500 internal_error` handler; add a `try/except` around `snowflake_service` calls if you want a friendlier `503` for a down warehouse |

---

## PART 15 — Logging & Monitoring

- Every Flask request gets an `X-Request-Id` (see `app/__init__.py`,
  `register_request_logging`), echoed back in the response header.
- Lambda logs are structured with `document_id` so you can trace one
  document across `Flask logs -> CloudWatch (Lambda) -> Snowflake` by
  grepping/Insights-querying that ID.
- Trace a failing document:
  1. `X-Request-Id` from the Flask response / Flask logs.
  2. `aws logs tail /aws/lambda/policy-document-processor --follow` filtered
     by `document_id`.
  3. `SELECT * FROM RAW.POLICY_DOCUMENT_STATUS WHERE document_id = '...'`.

---

## PART 16 — Security Checklist (POC-appropriate, production notes inline)

- [x] No secrets committed — `.env` / `.env.*` are gitignored (only `.env.example`, which has blanks, is tracked).
- [x] IAM least privilege — each Lambda/API Gateway role scoped to exactly the actions/resources it needs (`aws/iam/*.json`).
- [x] JWT-protected routes (`require_auth` on all routes except `/api/health`, `/api/auth/login`).
- [x] Input validation on upload (`schemas.py`) and file size cap (`MAX_CONTENT_LENGTH`).
- [ ] **Production gap:** file-type/content validation is extension-only; add magic-byte checks before trusting uploads.
- [ ] **Production gap:** `auth_service.issue_token` accepts any username/role with no password check — replace with Amazon Cognito or a real credential store before this leaves POC status.
- [x] Parameterized Snowflake queries (`%(name)s` bind params, no string-built SQL).
- [ ] **Production gap:** put Flask behind HTTPS (ALB/CloudFront + ACM cert) — not configured in this POC's Dockerfile/Procfile.
- [ ] **Production gap:** CORS is not configured; add `flask-cors` scoped to your real frontend origin if a browser client calls this API.
- [x] No sensitive data (tokens, passwords) is logged — only `document_id`, method, path.

---

## PART 17 — Deployment

Simplest path consistent with "Flask ... Deployed on AWS" + free-tier-conscious:

```
Local Flask (tested) → Docker image → AWS Elastic Beanstalk (single instance, free-tier eligible) → talks to already-provisioned S3/Lambda/DynamoDB/Snowflake
```

```bash
docker build -t policy-intake-poc .
docker run --env-file .env -p 5000:5000 policy-intake-poc

# Elastic Beanstalk (Docker platform)
eb init policy-intake-poc --platform docker --region us-east-1
eb create policy-intake-poc-env --single --instance-type t3.micro
eb setenv $(cat .env | grep -v '^#' | xargs)
eb deploy
eb open
```

After deploy, re-run the PART 10 curl tests against the EB URL instead of
`localhost:5000`.

---

## PART 18 — Troubleshooting

**Flask can't reach API Gateway**
- Check `API_GATEWAY_UPLOAD_URL` is the `prod` stage invoke URL (not the console edit URL).
- `curl -X PUT <url>/incoming/test/test.pdf --data-binary @sample.pdf` directly to isolate Flask vs. API Gateway.
- Check the API Gateway execution role has `s3:PutObject` on the exact bucket/prefix (`aws/iam/apigateway-s3-role-policy.json`).

**EventBridge rule never fires Lambda**
- Confirm bucket has EventBridge notifications enabled: `aws s3api get-bucket-notification-configuration --bucket policy-documentz`.
- Confirm the rule's `detail.bucket.name` matches your real bucket name.
- Check `aws lambda get-policy --function-name policy-document-processor` includes the EventBridge invoke permission.

**Lambda runs but DynamoDB never updates**
- `aws logs tail /aws/lambda/policy-document-processor` for a stack trace.
- Confirm `DYNAMODB_TABLE_NAME` env var on the Lambda matches the real table name.
- Confirm the document_id regex in `_extract_document_id` matches your actual S3 key format (`incoming/<customer>/<uuid>_<filename>`).

**Flask can't connect to Snowflake**
- `SNOWFLAKE_ACCOUNT` must be the account identifier (e.g. `xy12345.us-east-1`), not a URL.
- Confirm the warehouse (`POLICY_WH`) is not suspended/dropped and the role has USAGE on database/schema.
- Test outside Flask first: `python -c "import snowflake.connector as sc; sc.connect(account='...', user='...', password='...').cursor().execute('SELECT 1')"`.

**`moto` tests fail with real-AWS-looking errors**
- Ensure `mock_aws()` wraps table creation *before* any boto3 client/resource is constructed (see `tests/conftest.py` fixture ordering).

---

## Final Checklist

- [x] Architecture understood (see chat: PART 1 analysis)
- [x] Flask implemented (`app/`)
- [x] AWS configured (`aws/setup-commands.md`, `aws/iam/*`, `aws/eventbridge/rule.json`)
- [x] AWS ↔ Flask connected (`app/services/aws_service.py`)
- [x] Snowflake configured (`sql/*.sql`)
- [x] Snowflake ↔ application connected (`app/services/snowflake_service.py`, `aws/lambda/snowflake_loader`)
- [x] APIs tested (`tests/`, curl examples above)
- [ ] AWS workflow tested against a **real** AWS account — needs your credentials, not runnable from this environment
- [ ] Data verified in a **real** Snowflake account — needs your credentials
- [ ] End-to-end workflow tested against real cloud resources — needs your credentials
- [x] Error handling implemented and unit-tested
- [ ] Deployed to Elastic Beanstalk — run PART 17 commands with your AWS account

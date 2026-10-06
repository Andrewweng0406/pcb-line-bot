# PCB Quote Bot v2.0

AI-powered PCB quoting, available as both an internal login-protected web
dashboard and a LINE bot, with support for text and image recognition. Both
channels share the same quote engine, AI parser, and database — a quote
created from either one shows up in the same history.

## Live Demo

- Rehearsal: https://web-staging-ee69.up.railway.app/login
- Production: https://web-production-803c7.up.railway.app/login
- Use privately supplied demo credentials; passwords are not listed here.
- Interview walkthrough: [docs/INTERVIEW_DEMO.md](docs/INTERVIEW_DEMO.md)
- Rehearsal and production-release checks: [docs/RELEASE_ACCEPTANCE.md](docs/RELEASE_ACCEPTANCE.md)
- Recorded staging rehearsal: [docs/REHEARSAL_2026-10-05.md](docs/REHEARSAL_2026-10-05.md)
- Latest staging deployment: [docs/STAGING_RELEASE_2026-10-05.md](docs/STAGING_RELEASE_2026-10-05.md)
- Latest production deployment: [docs/PRODUCTION_RELEASE_2026-10-05.md](docs/PRODUCTION_RELEASE_2026-10-05.md)
- Customer estimate/formal release policy: [docs/CUSTOMER_EXPORT_POLICY.md](docs/CUSTOMER_EXPORT_POLICY.md)
- Vereyo-specific positioning: [docs/VEREYO_ALIGNMENT.md](docs/VEREYO_ALIGNMENT.md)
- AI evaluation plan: [docs/AI_EVALUATION.md](docs/AI_EVALUATION.md)
- Runnable extraction benchmark: [docs/EXTRACTION_EVALUATION.md](docs/EXTRACTION_EVALUATION.md)
- Latest progress and outstanding release gates: [docs/PROGRESS_2026-10-04.md](docs/PROGRESS_2026-10-04.md)

Demo accounts are intended for interview review only. Rotate the password
or replace the account before using the deployment for real customer data.

## Features

- ✅ Internal web dashboard (login/self-registration, quote creation with
  AI-assisted form filling, quote list/detail/status tracking, customer
  management, stats charts) — see [Web Dashboard](#web-dashboard) below
- ✅ English-first web UI with a built-in Chinese language toggle
- ✅ Real-time PCB quote calculation
- ✅ Text specification parsing with OpenAI
- ✅ PCB image recognition and parsing
- ✅ AI extraction review layer with field source/confidence audit metadata
- ✅ Quote history lookup
- ✅ Average price statistics
- ✅ Excel and formal quote document export
- ✅ Repeatable interview/demo data seeding
- ✅ User memory storage with Redis support
- ✅ S3 file storage support
- ✅ Complete error handling and logging
- ✅ Ready for Docker, AWS Fargate, and Railway

## Interview Demo

For a guided 3-5 minute demo flow, use
[docs/INTERVIEW_DEMO.md](docs/INTERVIEW_DEMO.md). It includes:

- a click-by-click walkthrough
- sample RFQ text to paste into AI Form Assist
- backup manual RFQ values if AI parsing is unavailable
- architecture talking points

For Vereyo interviews, use
[docs/VEREYO_ALIGNMENT.md](docs/VEREYO_ALIGNMENT.md) to frame this project as
the same vertical estimating workflow pattern in a different technical domain.

For AI trust and production-readiness discussion, use
[docs/AI_EVALUATION.md](docs/AI_EVALUATION.md). It explains how this kind of
system should measure extraction quality, human corrections, review workflow,
and pricing guardrails.

## Tech Stack

- **Backend**: FastAPI + Uvicorn
- **Database**: PostgreSQL
- **Cache**: Redis-compatible memory store support
- **File storage**: Local/Railway persistent volume or S3
- **Containerization**: Docker + Docker Compose
- **Infrastructure**: Railway for demo, AWS CloudFormation support
- **Monitoring**: Application logs and `/health`

## Local Development

### Using Docker Compose (recommended)

```bash
# Copy the environment variable file
cp .env.example .env

# Edit .env and add LINE Bot and OpenAI credentials
nano .env

# Start the services
docker-compose up

# The app will be available at http://localhost:8000
```

### Without Docker

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env

# Edit .env and configure the local database
DATABASE_URL=sqlite:///./quotes.db

# Initialize the database
python -c "from app.core.database import init_db; init_db()"

# Start the app
uvicorn app.main:app --reload --port 8000
```

## Local Testing

### Workflow acceptance

```bash
DEBUG=false python3 -m pytest -q
DEBUG=false python3 -m pytest tests/test_quote_acceptance.py -q
```

The acceptance test runs RFQ parsing, draft corrections, release blocking,
human confirmation, approval, real Excel downloads and a second revision.
It verifies persisted evidence, reviewer attribution, original-record integrity
and unchanged contents at previous download URLs. Export filenames are unique
across same-second requests and process-counter resets.

Browser acceptance is opt-in and requires Playwright with Chromium:

```bash
python3 -m pip install playwright
python3 -m playwright install chromium
DEBUG=false RUN_BROWSER_ACCEPTANCE=1 python3 -m pytest tests/test_browser_acceptance.py -q
```

Browser tests click through the workflow at desktop and mobile widths, using
temporary SQLite databases, temporary export directories and a loopback server
that is stopped after each test. Only the external LLM response is stubbed;
these tests do not measure model extraction accuracy. Existing demo or Railway
data is not used. Screenshots are written to each test's temporary directory.

### Test the quote text endpoint

```bash
curl "http://localhost:8000/quote_text?text=46L%20Megtron%206%20109.5x59.5mm%202pcs%20ENIG%2010u%20VIP%20impedance%20back%20drill%20BVH"
```

### Test image parsing

```bash
curl http://localhost:8000/image_test
```

### Test the LINE webhook with ngrok

```bash
# Install ngrok
brew install ngrok

# Start ngrok
ngrok http 8000

# Copy the HTTPS URL and set the Webhook URL in LINE Developers
# Example: https://xxxx.ngrok-free.app/callback
```

## Web Dashboard

The web dashboard is the primary way staff create and manage quotes day to
day; the LINE bot remains available as a secondary channel (e.g. sending a
photo in from the field). Both call the same `quote_engine.calculate_quote()`.

The dashboard defaults to English for demos and interviews. Staff can switch
between English and Chinese from the navigation bar; the language preference is
stored in a cookie. Chinese RFQ/specification input remains supported by the AI
parsers and LINE command aliases.

### First-time setup

```bash
# Initialize the database (if not already done above)
python -c "from app.core.database import init_db; init_db()"

# Create the first login account
python scripts/create_user.py owner@example.com your-password

# Start the app (same command as above)
uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/login`. Additional staff can either be created
the same way (`scripts/create_user.py`) or self-register at `/register` using
the shared `INVITE_CODE` (see Environment Variables) — registration is gated
by that code rather than left open, since the dashboard may be reachable on
a public URL.

### Extraction review workflow

Production: https://web-production-803c7.up.railway.app/login
Staging: https://web-staging-ee69.up.railway.app/login

Staging uses independent PostgreSQL data, environment-scoped storage, and
session keys. Validate changes there before promoting them to production.

AI-assisted quotes retain the original RFQ text, matched evidence, extracted
values, and field review status. Conflicting quantities, layer counts, dimensions,
thicknesses, or lead times require confirmation, as do defaults, inferred values,
and image extractions. Confidence levels are evidence rules, not calibrated
probabilities; image evidence still requires manual verification.

Save an unconfirmed quote as a pending draft. Confirm selected fields in the new
quote form or the quote detail review table. Corrections require a review note;
the audit history stores original and final values, the authenticated reviewer,
and a UTC timestamp. Approval, ordering, and formal export are blocked until all
pending extraction fields have been confirmed. Internal Excel exports remain
available for review. Quotes entered manually without AI extraction metadata
have no AI confirmation gate, but still undergo the customer-export checks.

Customer estimates and formal quotations are separate documents. Manager/Admin
can download a clearly labelled preliminary estimate after review. Formal export
also requires complete specifications, a resolved saved pricing review and an
Approved/Ordered business status. Missing legacy pricing reviews fail closed;
use a verified revision instead of overwriting the original. See the
[customer-export policy](docs/CUSTOMER_EXPORT_POLICY.md). The `b591af5`
application is deployed and verified on both Railway staging and production.
This remains a pilot; see the production record for remaining release limits.

Use **Create Revision** on a saved quote to correct its specifications. This
creates a new pending quote linked to the original and preserves its extraction
and review history. Changing a confirmed value requires a new confirmation;
the original quote stays intact. Resolving a conflict requires a review note.
The revision form includes area-only quotes and pricing inputs such as press
count, internal layers, trace-to-hole spacing, flatness, and back-drill fees.
Clearing an optional extracted field is recorded as a correction and requires
a note; changing only a number's representation (for example `6` to `6.0`)
does not invalidate an existing confirmation.

The customer clarification draft lists unresolved fields for staff to edit and
copy. It is generated from review findings and does not send email. Text evidence
checks cover supported patterns within one RFQ; cross-document comparison and
image conflict detection are not implemented. Signed extraction payloads are
bound to the current user and expire after 24 hours.

For hands-on staging practice, use the [20 synthetic RFQs and answer keys](docs/SYNTHETIC_RFQ_PRACTICE.md).
The pack includes basic, intermediate and high-risk review cases, with individual
text files and an evaluation-compatible JSONL dataset. It is not real RFQ accuracy
evidence and does not seed production data.

### Historical comparison and evidence

Quote detail and authenticated history APIs separate similarity discovery from
benchmark eligibility. Specification comparisons show current and historical
values, signed percentage differences, and unknown fields. Similarity is a
deterministic score out of 100, not AI confidence or a price recommendation.

The web page and authenticated history APIs inspect up to 200 candidates
preceding the current quote, within two layers of the current RFQ. The date
cutoff is applied before the candidate limit and revision-family selection;
same-timestamp records must have a lower ID. Material aliases are normalized
before comparison. Eligible references
require recorded, matching currency and pricing version; matching layer,
material, board thickness, copper, surface finish, gold thickness and special processes;
known positive area, quantity and delivery time within a factor of two; and
similarity of at least 75. Pending extraction reviews are excluded. Unknown
special-process flags are not interpreted as false. Missing or broken revision
lineage is excluded; only the newest eligible historical candidate from a revision family counts,
and the current RFQ's own family never counts as independent history.

Quoted unit price, accepted unit price and actual unit cost have separate sample
counts. Accepted prices and recorded actual costs require a won outcome; values
come from recorded totals divided by quantity, never estimated costs. Each
metric needs five valid independent references before its median is available.
Nonfinite or nonpositive prices are excluded; zero recorded cost is allowed.
Insufficient evidence remains visible instead of generating a suggested price.
The page displays eight candidates, but summaries use the full bounded search.
These conservative rules are not a comprehensive manufacturing-cost model;
fine trace geometry, tooling, panel utilization and market changes still need
professional judgment. No automatic repricing is applied.

### Price review

Quote detail and the authenticated historical-summary API now include a price
review assessment. Only positive finite **quoted** unit prices from eligible
independent RFQs preceding the current quote are used. Later and undated quotes
are outside the discovery window; invalid prices within the window are listed
with exclusion reasons. Pending
extraction review, unavailable current price, and fewer than five valid earlier
references each produce an explicit unavailable state with no price band.

The versioned `median-mad-v1` rule uses the historical median and median absolute
deviation (MAD). Its review band is:

```text
median +/- max(20% of median, 3 * 1.4826 * MAD)
```

Prices strictly outside the band are flagged above or below; boundary values
are inside. The 20% floor handles identical or tightly clustered history.
This is an explicit staff-review policy, not a predicted market price,
recommended selling price, calibrated confidence, or statistically validated
business threshold. It never changes the quote or its approval status.
Accepted prices and actual costs remain separate metrics and do not determine
this quoted-price band. Different area, quantity and delivery time are shown
alongside contributing RFQs as review context, without attributing a calculated
price impact to those differences.

The evidence panel lists every contributing quote and every rejected candidate,
plus the cutoff date, median, MAD and formula. Results are recalculated from the
current saved records; this is not an immutable assessment audit snapshot.
Future market movements, panel utilization and fine manufacturing geometry
remain outside the rule. The existing bounded 200-candidate discovery applies.

Three clearly labelled synthetic scenarios can be added to local or staging
data with `python scripts/seed_price_review_demo.py`. The command preserves
existing records and refuses Railway production. Its isolated pricing version
prevents illustrative prices from becoming references for normal quotes.

### Currency and release readiness

Quote pages and exports display the recorded currency and monetary precision
to two decimal places. Dashboard, customer and monthly monetary analytics are
grouped by currency; no exchange-rate conversion or cross-currency sum is
performed. Missing currencies remain `UNKNOWN`. Monetary API responses include
per-currency groups; legacy scalar totals/averages are `null` when currency is
unknown or multiple currencies are present.

The detail page separates the saved business status from extraction-review
readiness. A legacy approved quote with pending confirmations remains blocked
from formal export or a new ordered transition, but staff can still save notes.
Price review is near the top, with contributing evidence collapsed; pending
extraction fields are shown first and the full audit remains available.

### Demo data

Seed interview-ready customers and RFQs:

```bash
python scripts/seed_demo_data.py
```

The seed is idempotent. It upserts demo customers and RFQs using stable
`DEMO-RFQ-*` quote numbers, so it can be rerun before a demo without creating
duplicates. On Railway, run it in the production environment:

```bash
railway ssh --service web --environment production -- python scripts/seed_demo_data.py
```

### Pages

| Path | Purpose |
|------|---------|
| `/login`, `/register` | Session-cookie auth; registration requires `INVITE_CODE` |
| `/` | Dashboard — today/total quote counts, average price, recent RFQs |
| `/quotes/new` | Create a quote: paste spec text or upload a PCB photo for AI-assisted autofill, then review/submit the structured form |
| `/quotes` | List with filters (date, layer, material, customer, status) |
| `/quotes/{id}` | Full spec/price breakdown; edit status and notes; download Excel or a formal quote document |
| `/customers` | Customer list and creation |
| `/stats` | Layer/material distribution charts |

The JSON API under `/api/*` (`app/api.py`) requires the same login session
and is used internally by the dashboard's stats aggregation.

## Environment Variables

See `.env.example` for details. Main variables:

```env
# Web dashboard
SECRET_KEY=a-real-random-value-in-production
INVITE_CODE=a-shared-code-to-hand-out-for-self-registration

# LINE Bot
LINE_CHANNEL_ACCESS_TOKEN=xxx
LINE_CHANNEL_SECRET=xxx

# OpenAI (used for text/image parsing)
OPENAI_API_KEY=sk-xxx

# Database
DATABASE_URL=postgresql://user:pass@localhost/pcb_bot
DEFAULT_CURRENCY=NTD
PRICING_VERSION=v1

# Redis (optional)
REDIS_ENABLED=True
REDIS_URL=redis://localhost:6379

# AWS S3 (optional)
AWS_ENABLED=True
AWS_S3_BUCKET=your-bucket
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx

# Public URL (used for download links)
PUBLIC_BASE_URL=http://localhost:8000

# Persistent file storage
PERSISTENT_DIR=.
UPLOAD_DIR=./data/uploads
EXPORT_DIR=./exports
LOG_DIR=./logs
```

## API Endpoints

### Health check
```
GET /health
```

Note: `GET /` is the web dashboard's home page (see [Web Dashboard](#web-dashboard)),
not a health check — it redirects to `/login` when logged out.

### Quote
```
GET /quote_text?text=...
```

### LINE Webhook
```
POST /callback
```

### File download
```
GET /download/exports/{filename}
```

## LINE Bot Commands

| Command | Function |
|------|------|
| PCB specification text | Parse and calculate a quote |
| Upload PCB image | Recognize specifications and calculate a quote |
| Query quotes | Show the 5 most recent quotes |
| Export quote | Generate an Excel file |
| Formal quote | Generate a formal quote document |
| Query [Layer/material] | Search historical quotes |
| Average [Layer/material] | Look up average prices |
| End/reset/clear | Clear the current quote |

### Example PCB Specification Text

```
46L Megtron 6 109.5x59.5mm 2pcs ENIG 10u VIP impedance back drill BVH
```

Parsed result:
- Layer: 46L
- Material: Megtron 6
- Size: 109.5 x 59.5 mm
- Qty: 2 pcs
- Surface Finish: ENIG 10μ"
- Special processes: VIP, Impedance, Back Drill, BVH

## Deploying to AWS

See the [AWS deployment guide](aws/DEPLOYMENT.md).

Quick summary:
```bash
# 1. Build and push the Docker image
docker build -t pcb-bot:latest .
docker push <ecr-uri>/pcb-bot:latest

# 2. Deploy the CloudFormation stack
aws cloudformation create-stack \
  --stack-name pcb-bot-stack \
  --template-body file://aws/cloudformation.yaml \
  --parameters ParameterKey=ContainerImage,ParameterValue=<ecr-uri>/pcb-bot:latest

# 3. Update the LINE Webhook URL
# Use the ALB DNS name to configure the webhook
```

## Deploying to Railway

Used for an internal pilot deployment, kept deliberately separate from the
AWS production database (see [Deploying to AWS](#deploying-to-aws) above) —
the LINE bot and its real quote history stay on Fargate/RDS untouched.

```bash
# One-time setup
railway init --name pcb-quote-bot
railway add --database postgres
railway add --service web
railway domain --service web

# Env vars on the `web` service (see Environment Variables above for what
# each one does)
railway variable set SECRET_KEY=<random-value> --service web
railway variable set INVITE_CODE=<shared-code> --service web
railway variable set OPENAI_API_KEY=<key> --service web
railway variable set 'DATABASE_URL=${{Postgres.DATABASE_URL}}' --service web
railway variable set 'PUBLIC_BASE_URL=https://${{RAILWAY_PUBLIC_DOMAIN}}' --service web
railway variable set DEBUG=False --service web

# Persistent volume so exported Excel/formal-quote files survive redeploys
# (the container filesystem is otherwise wiped on every deploy). This project
# stores exports, uploads, and logs under the mounted volume.
railway volume add --mount-path /app/exports --service web
railway variable set PERSISTENT_DIR=/app/exports --service web
railway variable set EXPORT_DIR=/app/exports --service web
railway variable set UPLOAD_DIR=/app/exports/data/uploads --service web
railway variable set LOG_DIR=/app/exports/logs --service web

# Deploy
railway up --service web

# Create the first login account against the deployed Postgres. You can run
# this inside the web service container so it uses the private Railway DB URL:
railway ssh --service web -- python scripts/create_user.py owner@example.com your-password

# Take and verify an integrity-checked application snapshot before risky changes.
DATABASE_URL=<DATABASE_PUBLIC_URL> python scripts/backup_db.py backups
python scripts/backup_db.py --verify backups/backup_<timestamp>.json
```

The snapshot is written atomically with mode `0600` and includes row counts,
per-table SHA-256 checksums, a whole-content checksum, and relationship checks.
Restore drills are restricted to a separate empty database by
`scripts/restore_db.py`. See [Backup and Recovery Runbook](docs/BACKUP_RECOVERY.md)
for native Railway snapshots, PostgreSQL dumps, persistent-file archives, and
the disposable restore procedure. A database snapshot does not include files
under `/app/exports`; archive that volume separately and store both copies
outside Railway.

## Project Structure

```
pcb_line_bot/
├── app/                    # Application
│   ├── core/              # Core modules (config, database, auth, memory, storage)
│   ├── main.py            # FastAPI application (LINE webhook + app setup)
│   ├── web.py             # Web dashboard routes (login/register, quotes, customers, stats)
│   ├── api.py             # Login-protected JSON API used by the dashboard
│   ├── quote_engine.py    # Quote calculation engine
│   ├── ai_parser.py       # Text parsing (OpenAI)
│   ├── image_parser.py    # Image parsing (OpenAI Vision)
│   └── export_*.py        # File export
├── templates/              # Jinja2 templates for the web dashboard
├── static/                 # CSS for the web dashboard
├── scripts/
│   ├── create_user.py     # Create a web login account
│   ├── backup_db.py       # Atomic, checksum-verified database snapshot
│   ├── restore_db.py      # Empty-target-only recovery drill
│   └── seed_demo_data.py  # Repeatable synthetic interview dataset
├── tests/                  # pytest suite
├── aws/                    # AWS deployment configuration
│   ├── cloudformation.yaml # CloudFormation template
│   └── DEPLOYMENT.md      # Deployment guide
├── docs/superpowers/       # Design specs and implementation plans
├── data/                   # Data directory
│   └── uploads/           # Uploaded images
├── logs/                   # Application logs
├── exports/               # Exported files
├── docker-compose.yml     # Docker Compose configuration
├── Dockerfile             # Docker image definition
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variable example
└── .gitignore             # Git ignore list
```

## Logs

Log files are stored in the `logs/` directory and split by date:
```
logs/
├── pcb_bot_20260512.log
├── pcb_bot_20260513.log
└── ...
```

## Troubleshooting

### Database connection failure
```
error: can't connect to database
```
- Check whether `DATABASE_URL` is correct
- Make sure the database service is running
- Check firewall and security group rules

### LINE webhook failure
- Check `LINE_CHANNEL_ACCESS_TOKEN` and `LINE_CHANNEL_SECRET`
- Verify that the webhook URL is configured correctly
- Check the application logs

### Image parsing failure
- Make sure `OPENAI_API_KEY` is set
- Check the OpenAI account quota
- Verify the image format and size

## Performance Optimization

1. **Redis cache**: Enable `REDIS_ENABLED=True` to cache user memory
2. **Database indexes**: Indexes have been created on `created_at` and `customer_id`
3. **S3 storage**: Use S3 instead of local storage for automatic scaling support
4. **Connection pool**: The configured connection pool size is 10

## Security

- Environment variables are not committed to Git (see `.gitignore`)
- Web exports require a staff session; LINE download links use filename-bound tokens valid for one hour.
- Web approval and API approval enforce the same pending-extraction checks. Negotiated prices use `final_price`, not the immutable calculated total.
- Login, registration and web AI requests are rate limited. Redis-backed shared counters require `REDIS_ENABLED=true` and a reachable `REDIS_URL`; otherwise limits are process-local. Redis failures return 503.
- Workbook imports skip repeated exact-file/row submissions using a database unique key. Optional reference metadata is imported only when present; missing currency and specifications remain unknown.
- Image uploads validate bytes, size and pixel count; original-document access is protected by staff/manager permissions.
- Viewer, Staff, Manager and Admin permissions apply to both web and API actions. New registrations are Staff; legacy accounts retain Manager approval access without automatic Admin grants. See [Access Control](docs/ACCESS_CONTROL.md) for the permission matrix and audited role-assignment CLI.
- This remains a single-company pilot without tenant isolation or confidential-field filtering. PDF extraction and LINE AI rate limits are not implemented.
- AWS Secrets Manager, security groups and private buckets are deployment options, not guarantees provided by the application.

See [Guardrail Verification](docs/HARDENING_STATUS.md) for limitations, rate settings and migration precautions. Back up the database before deploying the additive `import_key` migration.

## Monitoring

- `/health` is a liveness endpoint, not a database/storage readiness check.
- CloudWatch and ECS metrics depend on the optional AWS deployment configuration.
- Deployed alerting and scheduled backups must be verified separately.

## Support and Feedback

Have questions or improvement suggestions? Please open an issue or pull request.

## License

MIT License

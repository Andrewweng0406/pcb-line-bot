# PCB Quote Bot v2.0

AI-powered PCB quoting, available as both an internal login-protected web
dashboard and a LINE bot, with support for text and image recognition. Both
channels share the same quote engine, AI parser, and database — a quote
created from either one shows up in the same history.

## Features

- ✅ Internal web dashboard (login/self-registration, quote creation with
  AI-assisted form filling, quote list/detail/status tracking, customer
  management, stats charts) — see [Web Dashboard](#web-dashboard) below
- ✅ Real-time PCB quote calculation
- ✅ Text specification parsing with OpenAI
- ✅ PCB image recognition and parsing
- ✅ Quote history lookup
- ✅ Average price statistics
- ✅ Excel and formal quote document export
- ✅ User memory storage with Redis support
- ✅ S3 file storage support
- ✅ Complete error handling and logging
- ✅ Ready for Docker, AWS Fargate, and Railway

## Tech Stack

- **Backend**: FastAPI + Uvicorn
- **Database**: PostgreSQL (RDS)
- **Cache**: Redis (ElastiCache)
- **File storage**: S3
- **Containerization**: Docker + Docker Compose
- **Infrastructure**: AWS CloudFormation
- **Monitoring**: CloudWatch

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

### Pages

| Path | Purpose |
|------|---------|
| `/login`, `/register` | Session-cookie auth; registration requires `INVITE_CODE` |
| `/` | Dashboard — today/total quote counts, average price |
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
# (the container filesystem is otherwise wiped on every deploy)
railway volume add --mount-path /app/exports --service web

# Deploy (manual — no GitHub auto-deploy is configured, so this must be
# re-run after every code change meant to reach the pilot)
railway up --service web

# Create the first login account against the deployed Postgres
DATABASE_URL=<DATABASE_PUBLIC_URL from `railway variable list --service Postgres`> \
  python scripts/create_user.py owner@example.com your-password

# Take a manual data snapshot before risky changes (see scripts/backup_db.py)
DATABASE_URL=<DATABASE_PUBLIC_URL> python scripts/backup_db.py
```

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
│   └── backup_db.py       # Manual JSON snapshot of all tables
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
- Use AWS Secrets Manager to manage production secrets
- Security groups restrict database and cache access
- S3 buckets are private and use signed URLs for downloads

## Monitoring

- CloudWatch Logs integration
- Health check endpoint `/health`
- ECS task-level CPU/memory monitoring

## Support and Feedback

Have questions or improvement suggestions? Please open an issue or pull request.

## License

MIT License

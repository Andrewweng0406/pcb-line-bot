# PCB Quote Bot v2.0

AI-powered PCB quote bot integrated with LINE, with support for text and image recognition.

## Features

- ✅ Real-time PCB quote calculation
- ✅ Text specification parsing with OpenAI
- ✅ PCB image recognition and parsing
- ✅ Quote history lookup
- ✅ Average price statistics
- ✅ Excel and formal quote document export
- ✅ User memory storage with Redis support
- ✅ S3 file storage support
- ✅ Complete error handling and logging
- ✅ Ready for Docker and AWS Fargate

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

## Environment Variables

See `.env.example` for details. Main variables:

```env
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
GET /
```

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

## Project Structure

```
pcb_line_bot/
├── app/                    # Application
│   ├── core/              # Core modules (config, database, memory, storage)
│   ├── main.py            # FastAPI application
│   ├── quote_engine.py    # Quote calculation engine
│   ├── ai_parser.py       # Text parsing (OpenAI)
│   ├── image_parser.py    # Image parsing (OpenAI Vision)
│   └── export_*.py        # File export
├── aws/                    # AWS deployment configuration
│   ├── cloudformation.yaml # CloudFormation template
│   └── DEPLOYMENT.md      # Deployment guide
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

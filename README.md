# Bitbucket AI Code Reviewer (FastAPI + OpenAI + AWS SES)

An AI agent that listens to Bitbucket PR webhooks, fetches the diff, generates a code review using an LLM, posts the review as a PR comment, and emails the review via AWS SES.

## Features

- FastAPI webhook for Bitbucket: `pullrequest:created` and `pullrequest:updated`
- Fetches PR diff using Bitbucket API
- Chunks large diffs safely for LLM
- LLM-based review (OpenAI)
- Posts review as a PR comment to Bitbucket
- Sends review via AWS SES (optional, configurable)
- Simple logging and health endpoint
- Dockerfile & requirements included

## Quick Start

### 1) Python env

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2) Environment variables

Copy `.env.example` to `.env` and set values. Or export them in your environment.

Required:

- `OPENAI_API_KEY`
- `BITBUCKET_USER`
- `BITBUCKET_TOKEN` (App Password)
- `BITBUCKET_WORKSPACE` (your workspace id/slug)
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
- `SES_SENDER` (verified email in SES)

Optional:

- `POST_PR_COMMENT` (default `true`)
- `SEND_EMAIL` (default `true`)
- `DEFAULT_RECIPIENT_EMAIL` (fallback if author email is unknown)
- `OPENAI_MODEL` (default `gpt-4o-mini`)
- `MAX_TOKENS_PER_CHUNK` (heuristic size for chunking, default 8000 characters)

### 3) Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4) Configure Bitbucket Webhook

In your repo:

- **Settings → Webhooks → Add webhook**
- **URL**: `https://your-domain.com/webhooks/bitbucket`
- **Triggers**: Pull request: Created, Pull request: Updated

### 5) Test locally

Use the sample payload:

```bash
curl -X POST http://localhost:8000/webhooks/bitbucket \
  -H "Content-Type: application/json" \
  -H "X-Event-Key: pullrequest:created" \
  -d @tests/sample-payload.json
```

> For real diffs, Bitbucket will call your public URL; run behind a tunnel (e.g., ngrok) or deploy.

## Docker

```bash
docker build -t bitbucket-ai-reviewer .
docker run -p 8000:8000 --env-file .env bitbucket-ai-reviewer
```

## Notes

- If your SES account is in sandbox, you can only send emails to verified addresses.
- Bitbucket Cloud PR payload may not include the author's email; set `DEFAULT_RECIPIENT_EMAIL` or implement your own mapping.
- Inline comments require file/line mapping; this project posts a summary PR comment by default.

## License

MIT

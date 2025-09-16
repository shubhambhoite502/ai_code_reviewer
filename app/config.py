import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

BITBUCKET_USER = os.getenv("BITBUCKET_USER", "")
BITBUCKET_TOKEN = os.getenv("BITBUCKET_TOKEN", "")
BITBUCKET_WORKSPACE = os.getenv("BITBUCKET_WORKSPACE", "")

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
SES_SENDER = os.getenv("SES_SENDER", "")
DEFAULT_RECIPIENT_EMAIL = os.getenv("DEFAULT_RECIPIENT_EMAIL", "")

POST_PR_COMMENT = os.getenv("POST_PR_COMMENT", "true").lower() == "true"
SEND_EMAIL = os.getenv("SEND_EMAIL", "true").lower() == "true"

NOTION_TESTCASES_DB_ID = os.getenv("NOTION_TESTCASES_DB_ID", "")
NOTION_BACKLOG_DB_ID = os.getenv("NOTION_BACKLOG_DB_ID", "")
NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# heuristic for chunking long diffs (characters per chunk)
MAX_TOKENS_PER_CHUNK = int(os.getenv("MAX_TOKENS_PER_CHUNK", "8000"))

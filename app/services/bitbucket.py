from typing import Optional
import requests
from . import review_formatter
from ..utils.logger import logger
from ..config import BITBUCKET_USER, BITBUCKET_TOKEN, BITBUCKET_WORKSPACE

API_BASE = "https://api.bitbucket.org/2.0"

def fetch_pr_diff(diff_url: str) -> str:
    logger.info("Fetching diff from Bitbucket: %s", diff_url)
    resp = requests.get(diff_url, auth=(BITBUCKET_USER, BITBUCKET_TOKEN))
    resp.raise_for_status()
    return resp.text

def post_pr_comment(repo_slug: str, pr_id: int, body: str) -> Optional[dict]:
    url = f"{API_BASE}/repositories/{BITBUCKET_WORKSPACE}/{repo_slug}/pullrequests/{pr_id}/comments"
    payload = { "content": { "raw": body } }
    logger.info("Posting PR comment to %s PR#%s", repo_slug, pr_id)
    resp = requests.post(url, json=payload, auth=(BITBUCKET_USER, BITBUCKET_TOKEN))
    if resp.status_code not in (200, 201):
        logger.error("Failed to post comment: %s - %s", resp.status_code, resp.text)
        return None
    return resp.json()

def test_bitbucket_auth():
    """
    Test Bitbucket authentication using App Password.
    Returns True if authenticated, False otherwise.
    """
    url = "https://api.bitbucket.org/2.0/user"
    try:
        resp = requests.get(url, auth=(BITBUCKET_USER, BITBUCKET_TOKEN))
        if resp.status_code == 200:
            user = resp.json()
            print(f"Authenticated as: {user.get('display_name')} ({user.get('uuid')})")
            return True
        else:
            print(f"Failed to authenticate. Status code: {resp.status_code}")
            return False
    except requests.RequestException as e:
        print(f"Error connecting to Bitbucket: {e}")
        return False

import json
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse
import os
from .config import (
    POST_PR_COMMENT, SEND_EMAIL, DEFAULT_RECIPIENT_EMAIL, MAX_TOKENS_PER_CHUNK
)
from .services.bitbucket import fetch_pr_diff, post_pr_comment
from .services.notion import save_testcases_to_notion, fetch_epic_from_notion
from .services.llm import review_diff_chunks,generate_test_cases
from .services.review_formatter import format_review
from .services.email_ses import send_email_ses
from .utils.chunker import chunk_text
from .utils.logger import logger
import time
import asyncio
import re

processed_prs = set()  # ideally, use a persistent cache like Redis

processed_mrs = set()  # ideally, use a persistent cache like Redis


app = FastAPI(title="Bitbucket AI Code Reviewer")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/webhooks/bitbucket")
async def handle_bitbucket(request: Request, x_event_key: str = Header(None)):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if x_event_key not in ("pullrequest:created", "pullrequest:updated"):
        return JSONResponse({"status": "ignored", "reason": "event not handled"})

    try:
        pr = payload["pullrequest"]
        repo = payload["repository"]
        pr_id = pr["id"]
        repo_slug = repo.get("slug") or repo.get("name")
        diff_url = pr["links"]["diff"]["href"]
        author_display = pr["author"]["display_name"]
        author_email = author_display+"@greatmanagerinstitute.com"

        key = f"{repo_slug}-{pr_id}"
        if key in processed_prs:
            return {"status": "ignored", "reason": "already processed."}

        processed_prs.add(key)
        # schedule removal after 10 min
        asyncio.create_task(remove_after_delay(key, 600))
    except KeyError as e:
        logger.error("Missing key in payload: %s", e)
        raise HTTPException(status_code=400, detail=f"Missing key: {e}")

    logger.info("Webhook for repo=%s PR#%s by %s", repo_slug, pr_id, author_display)

    # 1) Fetch diff
    diff = fetch_pr_diff(diff_url)

    # 2) Chunk and review via LLM
    chunks = chunk_text(diff, MAX_TOKENS_PER_CHUNK)
    sections = review_diff_chunks(chunks)

    # 3) Format once
    body_md = format_review(sections)

    # 4) Post PR comment
    result = None
    if POST_PR_COMMENT:
        result = post_pr_comment(repo_slug, pr_id, body_md)

    # 5) Email (optional)
    if SEND_EMAIL and author_email:
        html = f"""<h3>Hello {author_display},</h3>
        <p>Here is the AI-generated review for PR <b>#{pr_id}</b> in <b>{repo_slug}</b>:</p>
        <pre style="background:#f6f8fa;padding:12px;white-space:pre-wrap">{body_md}</pre>
        <p><em>This is an automated message.</em></p>
        """
        send_email_ses(
            to_email=author_email,
            subject=f"AI Code Review: {repo_slug} PR#{pr_id}",
            html_body=html,
            text_body=body_md
        )


    return {"status": "ok", "comment_posted": bool(result), "emailed": bool(author_email) and SEND_EMAIL}


async def remove_after_delay(key: str, delay: int = 600):
    await asyncio.sleep(delay)
    processed_prs.discard(key)

@app.post("/webhooks/bitbucket-pr-merged")
async def handle_pr_merge(request: Request):
    try:
        payload = await request.json()

        pr = payload["pullrequest"]
        repo = payload["repository"]
        pr_id = pr["id"]
        branch_name = pr["source"]["branch"]["name"]
        repo_slug = repo.get("slug") or repo.get("name")
        author = pr["author"]["display_name"]

        # --- Extract Epic No from branch name ---
        match = re.search(r"(EPIC-\d+)", branch_name, re.IGNORECASE)
        epic_no = match.group(1).upper() if match else None

        if not epic_no:
            logger.warning("No Epic No found in branch name: %s", branch_name)
            return JSONResponse({"status": "ignored", "reason": "no epic found"})

        logger.info("PR merged for repo=%s branch=%s epic=%s", repo_slug, branch_name, epic_no)

        if epic_no in processed_mrs:
            return {"status": "ignored", "reason": "already processed."}

        processed_mrs.add(epic_no)
        # schedule removal after 10 min
        asyncio.create_task(remove_after_delay(epic_no, 1000))

        # --- 1. Fetch Epic details from Notion ---
        epic_details = fetch_epic_from_notion(epic_no)

        page_id = (epic_details or {}).get("epicPageId", None)
        
        if not page_id:
            logger.warning("No Notion page ID found for Epic: %s", epic_no)
            return JSONResponse({"status": "ignored", "reason": "no notion page id found"})

        if not epic_details:
            logger.warning("No details found in Notion for Epic: %s", epic_no)
            return JSONResponse({"status": "ignored", "reason": "no epic details found"})
        epic_name = (epic_details or {}).get("Epic Name", "N/A")


        pr_title = pr.get("title") or ""
        pr_desc = pr.get("description") or ""
        diff = fetch_pr_diff(pr["links"]["diff"]["href"]) or ""

        # --- 2. Generate Test Cases via LLM ---
        combined_context = f"{pr_title}\n\n{pr_desc}\n\n{diff}"
        testcases = generate_test_cases(epic_no, epic_name, epic_details['PRD'], combined_context)

        print(testcases,'testcases')

        # --- 3. Store in Notion Test Cases DB ---
        save_testcases_to_notion(page_id, testcases)

        return {"status": "ok", "epic": epic_no, "testcases_stored": ''}

    except Exception as e:
        logger.error("Error in PR merge handler: %s", str(e), exc_info=True)
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)
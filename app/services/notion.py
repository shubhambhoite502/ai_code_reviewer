from wsgiref import headers
import requests
import json
from ..config import NOTION_TESTCASES_DB_ID, NOTION_API_KEY, NOTION_BACKLOG_DB_ID

HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
     "accept": "application/json",
}

def fetch_epic_from_notion(epic_no: str):
    """
    Fetch Epic details from Notion Epic DB by Epic No.
    Returns dict with Epic Name, PRD, Tech Notes.
    """

    url = "https://api.notion.com/v1/databases/d417ea956904407b93be2980314bd675/query"
 
    print(epic_no,"epic_no")
    try:
        response = requests.post(url, headers=HEADERS,json={})
        response.raise_for_status()
        results = response.json()
        epic = None
        for row in results["results"]:
            if  row["properties"]["04"]["unique_id"]["number"] == 1675:
                epic = row
                break
        
        # print(epic,'epic')
        if not epic:
            return None

        page = fetch_page_content(epic["id"])

        if not page:
            return None

        epic_details = {
            "Epic No": epic_no,
            "PRD": page,
            "epicPageId": epic["id"],
        }

        return epic_details
    except requests.exceptions.HTTPError as e:
        print("Status Code:", response.status_code)
        print("Error Response:", response.text)  # <-- Add this
    except Exception as e:
        print("Unexpected Error:", e)
        return ""


def fetch_page_content(page_id: str) -> str:
    """Recursively fetch content from a Notion page."""
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    all_texts = []

    try:
        while url:
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status()
            data = response.json()

            for block in data.get("results", []):
                all_texts.append(fetch_block_text(block))

                # If block has children, fetch them recursively
                if block.get("has_children"):
                    all_texts.append(fetch_page_content(block["id"]))

            # Pagination: Notion returns `next_cursor` for large pages
            url = data.get("next_cursor")
            if url:
                url = f"https://api.notion.com/v1/blocks/{page_id}/children?start_cursor={url}"

        return "\n".join(all_texts)

    except requests.exceptions.HTTPError as e:
        print("HTTP Error:", e)
        print("Response:", response.text)
        return ""
    except requests.exceptions.RequestException as e:
        print("Request Error:", e)
        return ""
    except Exception as e:
        print("Unexpected Error:", e)
        return ""


def fetch_block_text(block):
    """Extract text from a single block based on its type."""
    block_type = block.get("type")
    texts = []

    if block_type in ["paragraph", "heading_1", "heading_2", "heading_3", "quote", "callout", "to_do", "toggle"]:
        for rt in block[block_type]["rich_text"]:
            texts.append(rt.get("plain_text", ""))
    elif block_type in ["bulleted_list_item", "numbered_list_item"]:
        for rt in block[block_type]["rich_text"]:
            texts.append(rt.get("plain_text", ""))
        texts.append("\n")  # separate list items
    elif block_type == "code":
        code_text = "".join(rt.get("plain_text", "") for rt in block["code"]["rich_text"])
        texts.append(f"```{block['code'].get('language', '')}\n{code_text}\n```")
    # You can add more block types here if needed

    return "\n".join(texts)


def save_testcases_to_notion(epic_page_id, testcases):
    url = "https://api.notion.com/v1/pages"
    headers = HEADERS
    
    for tc in testcases:
        payload = {
            "parent": {"database_id": NOTION_TESTCASES_DB_ID},
            "properties": {
                # Relation to EPIC table
                "EPIC": {
                    "relation": [{"id": epic_page_id}]
                },
                "Test Case Description": {
                    "title": [{"text": {"content": tc["description"]}}]
                },
                "Test Steps": {
                    "rich_text": [{"text": {"content": "\n".join(tc["steps"])}}]
                },
                "Expected Result": {
                    "rich_text": [{"text": {"content": tc["expected_result"]}}]
                },
            }
        }
        response = requests.post(url, headers=headers, json=payload)


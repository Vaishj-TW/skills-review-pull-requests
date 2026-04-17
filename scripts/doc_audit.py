import os
import json
import requests

# -------------------------------------------------------
# STEP 1: Read the inputs
# -------------------------------------------------------
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
DOC360_API_KEY = os.environ["DOC360_API_KEY"]
PR_TITLE = os.environ.get("PR_TITLE", "untitled PR")
PR_BODY = os.environ.get("PR_BODY", "no description provided")

# Read the code diff that was saved by the workflow
with open("pr_diff.txt", "r") as f:
    diff = f.read()

# If the diff is empty, there's nothing to audit
if not diff.strip():
    with open("audit_findings.md", "w") as f:
        f.write("## 📋 Doc Coverage Audit\n\nNo code changes detected in this PR.")
    exit()

# -------------------------------------------------------
# STEP 2: Search Doc360 for potentially affected articles
# -------------------------------------------------------
doc360_headers = {"api_token": DOC360_API_KEY}

search_resp = requests.get(
    "https://apihub.document360.io/v2/articles/search",
    headers=doc360_headers,
    params={"query": PR_TITLE, "limit": 10}
)

# Safely extract article titles and slugs from the response
try:
    articles_raw = search_resp.json()
    articles = [
        {"title": a.get("title"), "slug": a.get("slug")}
        for a in articles_raw.get("data", {}).get("articles", [])
    ]
except Exception:
    articles = []

# -------------------------------------------------------
# STEP 3: Build the prompt for Claude
# -------------------------------------------------------
prompt = f"""
You are a technical documentation auditor for a SaaS compliance platform called Scrut Automation.

A pull request has just been merged. Your job is to identify documentation gaps.

PR Title: {PR_TITLE}
PR Description: {PR_BODY}

Code changes (diff):
<diff>
{diff[:8000]}
</diff>

Existing help center articles that may be relevant:
<articles>
{json.dumps(articles, indent=2)}
</articles>

Instructions:
1. Analyze the diff and identify what changed from a user-facing perspective — new features, modified flows, removed options, new configuration fields, renamed UI elements, etc.
2. Ignore changes that are purely internal — refactors, test files, comments, variable renames with no UX impact.
3. For each user-facing change, decide:
   - Does an existing article (from the list above) need to be updated? If yes, say which one and what specifically needs to change.
   - Does a new article need to be created? If yes, suggest a title and a brief outline of what it should cover.
   - Is no documentation change needed? Briefly say why.

Return your findings in this exact markdown format:

### Articles to Update
(list each article that needs changes, with a specific explanation)

### New Articles to Create
(list each new article needed, with suggested title and outline)

### No Action Needed
(if nothing doc-related changed, explain why)
"""

# -------------------------------------------------------
# STEP 4: Call the Claude API
# -------------------------------------------------------
response = requests.post(
    "https://api.anthropic.com/v1/messages",
    headers={
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    },
    json={
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}]
    }
)

# Extract Claude's response text
findings = response.json()["content"][0]["text"]

# -------------------------------------------------------
# STEP 5: Write the output file
# -------------------------------------------------------
with open("audit_findings.md", "w") as f:
    f.write("## 📋 Doc Coverage Audit\n\n")
    f.write(f"**PR:** {PR_TITLE}\n\n")
    f.write("---\n\n")
    f.write(findings)

print("Audit complete. Findings written to audit_findings.md")

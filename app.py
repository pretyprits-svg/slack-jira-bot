from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.signature import SignatureVerifier
import requests
from requests.auth import HTTPBasicAuth
import os

app = Flask(__name__)

# 🔐 Slack credentials

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
slack_client = WebClient(token=SLACK_BOT_TOKEN)
verifier = SignatureVerifier(SLACK_SIGNING_SECRET)

# 🔐 JIRA credentials
JIRA_EMAIL = "pganesan@ashleyfurniture.com"
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN")
JIRA_BASE_URL = "https://ashley-furniture-team.atlassian.net/rest/api/3/myself"
BOARD_ID = 1197  # Replace with your actual board ID
auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
headers = {"Accept": "application/json"}

# 🔍 Get active sprint
def get_active_sprint(board_id):
    url = f"{JIRA_BASE_URL}/rest/agile/1.0/board/{board_id}/sprint"
    response = requests.get(url, headers=headers, auth=auth)
    if response.status_code != 200:
        return None
    sprints = response.json().get("values", [])
    return next((s for s in sprints if s["state"] == "active"), None)

# 🔍 Get issues for a user in a sprint
def get_user_issues(account_id, sprint_id):
    jql = f'assignee = "{account_id}" AND sprint = {sprint_id}'
    url = f"{JIRA_BASE_URL}/rest/api/3/search"
    params = {"jql": jql, "fields": "summary,status"}
    response = requests.get(url, headers=headers, auth=auth)
    if response.status_code != 200:
        return []
    return response.json().get("issues", [])

# 🚪 Slack event endpoint
@app.route("/slack/events", methods=["POST"])
def slack_events():
    # ✅ Slack URL verification
    data = request.get_json()
    if data.get("type") == "url_verification":
        return jsonify({"challenge": data["challenge"]})

    # 🔒 Verify request signature
    if not verifier.is_valid_request(request.get_data(), request.headers):
        return "Invalid request", 403

    # 🧠 Handle slash command
    form_data = request.form
    user_text = form_data.get("text", "").strip()
    channel_id = form_data.get("channel_id")

    sprint = get_active_sprint(BOARD_ID)
    if not sprint:
        slack_client.chat_postMessage(channel=channel_id, text="No active sprint found.")
        return "", 200

    issues = get_user_issues(user_text, sprint["id"])
    if not issues:
        slack_client.chat_postMessage(channel=channel_id, text=f"No issues found for `{user_text}`.")
        return "", 200

    message = f"*{user_text}* is working in *{sprint['name']}*:\n"
    for issue in issues:
        key = issue["key"]
        summary = issue["fields"]["summary"]
        status = issue["fields"]["status"]["name"]
        message += f"• `{key}`: {summary} ({status})\n"

    slack_client.chat_postMessage(channel=channel_id, text=message)
    return "", 200

# 🏁 Run the Flask app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
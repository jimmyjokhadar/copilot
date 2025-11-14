import os
import requests

class SlackUtils:
    def send_message(self, channel, text):
        token = os.getenv("SLACK_BOT_TOKEN")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        requests.post("https://slack.com/api/chat.postMessage", headers=headers, json={"channel": channel, "text": text})

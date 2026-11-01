import os
import urllib.request
import urllib.parse

token = os.environ["TELEGRAM_BOT_TOKEN"]

chat_id = "1131645165"

message = "VOX Monitor: Telegram connection successful!"

url = f"https://api.telegram.org/bot{token}/sendMessage"

data = urllib.parse.urlencode({
    "chat_id": chat_id,
    "text": message
}).encode()

with urllib.request.urlopen(url, data=data, timeout=20) as response:
    print(response.read().decode())

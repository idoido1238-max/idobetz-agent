# -*- coding: utf-8 -*-
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import json
import time
import os

GREENAPI_INSTANCE = "7107659046"
GREENAPI_TOKEN = "b2e18cfe01024a64a311bd08000d400e64a744292b664c1780"
GREENAPI_URL = "https://7107.api.greenapi.com"
CLAUDE_API_KEY = "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"
CLAUDE_MODEL = "claude-sonnet-4-6"
OWNER_PHONE = "972527777927"
SERVER_PORT = int(os.environ.get("PORT", 8081))

conversation_history = {}
interested_customers = {}

SYSTEM_PROMPT = """אתה נציג מכירות ושירות לקוחות של idobetz — חנות ציוד מטבח מקצועי.

מידע על החנות:
- מוכרים: סכיני שף מקצועיים, מעשנות קמאדו, מכונות ברד וגלידה, מכונות נקניקיות, מכונות קרפ, מכונות וופל, מכונות פופקורן, מכונות צמר גפן, מקררי תצוגה, דוכני מזון
- המחירים הכי זולים בארץ
- משלוח חינם מעל 400 שח
- אחריות 12 חודשים
- שירות לקוחות 7 ימים בשבוע
- אתר: idobetz.co.il

הוראות:
- דבר בעברית בלבד
- היה ידידותי, חם ומקצועי
- ענה על שאלות על מוצרים
- עזור ללקוחות לבחור מוצר מתאים
- אם הלקוח רוצה להזמין — שלח אותו לאתר idobetz.co.il
- הודעות קצרות וברורות — לא יותר מ-3-4 משפטים"""

def ask_claude(phone, user_message):
    if phone not in conversation_history:
        conversation_history[phone] = []
    conversation_history[phone].append({"role": "user", "content": user_message})
    if len(conversation_history[phone]) > 20:
        conversation_history[phone] = conversation_history[phone][-20:]
    url = "https://api.anthropic.com/v1/messages"
    data = json.dumps({
        "model": CLAUDE_MODEL,
        "max_tokens": 500,
        "system": SYSTEM_PROMPT,
        "messages": conversation_history[phone]
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("x-api-key", CLAUDE_API_KEY)
    req.add_header("anthropic-version", "2023-06-01")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            reply = result["content"][0]["text"]
            conversation_history[phone].append({"role": "assistant", "content": reply})
            interest_keywords = ["מעניין", "כמה עולה", "מחיר", "אני רוצה", "אפשר לקנות"]
            if any(k in user_message for k in interest_keywords):
                interested_customers[phone] = {"time": time.time(), "followed_up": False}
            return reply
    except Exception as e:
        print("Claude error: " + str(e))
        return "מצטערים, יש תקלה זמנית. נחזור אליך בהקדם!"

def format_phone(phone):
    phone = str(phone).replace("-", "").replace(" ", "").replace("+", "")
    if phone.startswith("0"):
        phone = "972" + phone[1:]
    if not phone.startswith("972"):
        phone = "972" + phone
    return phone + "@c.us"

def send_whatsapp(phone, message):
    chat_id = format_phone(phone)
    url = GREENAPI_URL + "/waInstance" + GREENAPI_INSTANCE + "/sendMessage/" + GREENAPI_TOKEN
    data = json.dumps({"chatId": chat_id, "message": message}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            print("WA sent to " + chat_id)
            return True
    except Exception as e:
        print("WA error: " + str(e))
        return False

def check_follow_ups():
    now = time.time()
    for phone, data in list(interested_customers.items()):
        if not data["followed_up"] and (now - data["time"]) > 86400:
            send_whatsapp(phone, "היי! דיברנו אתמול — הסתדרת? אנחנו כאן לכל שאלה! idobetz.co.il")
            interested_customers[phone]["followed_up"] = True

class AgentHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body.decode("utf-8"))
        except:
            self.send_response(200)
            self.end_headers()
            return
        msg_type = data.get("typeWebhook", "")
        if msg_type == "incomingMessageReceived":
            sender = data.get("senderData", {})
            phone = sender.get("sender", "").replace("@c.us", "")
            msg_data = data.get("messageData", {})
            text_data = msg_data.get("textMessageData", {})
            message_text = text_data.get("textMessage", "")
            if message_text and phone:
                print("\nFrom " + phone + ": " + message_text)
                check_follow_ups()
                reply = ask_claude(phone, message_text)
                print("Reply: " + reply)
                time.sleep(1)
                send_whatsapp(phone, reply)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"success":true}')
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write("idobetz AI Agent Running!".encode())
    def log_message(self, format, *args):
        pass

def main():
    print("=" * 50)
    print("idobetz AI Agent")
    print("Port: " + str(SERVER_PORT))
    print("Ready!")
    print("=" * 50)
    server = HTTPServer(("0.0.0.0", SERVER_PORT), AgentHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")

if __name__ == "__main__":
    main()

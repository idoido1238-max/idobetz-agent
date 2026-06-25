# -*- coding: utf-8 -*-
# idobetz — שרת מלא עם דיבוג
import os
import json
import time
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

GREENAPI_INSTANCE = os.environ.get("GREENAPI_INSTANCE", "7107659046")
GREENAPI_TOKEN = os.environ.get("GREENAPI_TOKEN", "b2e18cfe01024a64a311bd08000d400e64a744292b664c1780")
GREENAPI_URL = "https://7107.api.greenapi.com"

ISTORES_API_KEY = os.environ.get("ISTORES_API_KEY", "b5adc1-89448f-d3734a-c74456-b1874d")
ISTORES_URL = "https://api.istores.co.il"

CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-6"

OWNER_PHONE = os.environ.get("OWNER_PHONE", "972527777927")
PORT = int(os.environ.get("PORT", 8080))

MANUALS_BASE = "https://raw.githubusercontent.com/idoido1238-max/idobetz-agent/master/"

ISTORES_HEADERS = {
    "x-token": ISTORES_API_KEY, "Company-Id": ISTORES_API_KEY,
    "Content-Type": "application/json", "User-Agent": "idobetz/1.0", "Accept": "application/json"
}

PRODUCT_MANUALS = {
    "akamado21": "kamado21_manual.pdf", "akamado16": "kamado16_manual.pdf",
    "akamado13": "kamado13_manual.pdf", "adivmk6618": "icecream_mk6618_manual.pdf",
    "adivsm212": "slush_sm212_manual.pdf", "adivpf1r": "thai_icecream_pf1r_manual.pdf"
}
KAMADO_SKUS = ["akamado21", "akamado16", "akamado13"]

agent_active = False
conversation_history = {}

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
        with urllib.request.urlopen(req, timeout=10) as r:
            print("WA sent to " + chat_id)
            return True
    except Exception as e:
        print("WA error: " + str(e))
        return False

def send_file(phone, file_url, filename, caption=""):
    chat_id = format_phone(phone)
    url = GREENAPI_URL + "/waInstance" + GREENAPI_INSTANCE + "/sendFileByUrl/" + GREENAPI_TOKEN
    data = json.dumps({"chatId": chat_id, "urlFile": file_url, "fileName": filename, "caption": caption}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            print("File sent: " + filename)
            return True
    except Exception as e:
        print("File error: " + str(e))
        return False

def create_invoice(order_id):
    url = ISTORES_URL + "/order/" + str(order_id) + "/create_doc"
    data = json.dumps({"doc_type": "invoice"}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    for k, v in ISTORES_HEADERS.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            result = json.loads(r.read().decode("utf-8"))
            if result.get("success"):
                resp = result.get("response", {})
                if isinstance(resp, dict):
                    return resp.get("url", resp.get("pdf_url", resp.get("doc_url", "")))
    except Exception as e:
        print("Invoice error: " + str(e))
    return None

def build_confirmation(order):
    first = order.get("firstname", "")
    last = order.get("lastname", "")
    name = (first + " " + last).strip() or "לקוח יקר"
    total = order.get("total", "")
    products = order.get("products", [])
    plist = ""
    for p in products:
        plist += "• " + str(p.get("name", "")) + " x" + str(p.get("quantity", 1)) + "\n"
    addr = order.get("shipping_address", order.get("payment_address", {}))
    street = addr.get("address_1", "")
    city = addr.get("city", "")
    addr_line = ""
    if street or city:
        addr_line = "📍 *כתובת משלוח:* " + street + " " + city + "\n\n"
    return ("שלום " + name + "! 😊\n\n✅ ההזמנה שלך התקבלה בהצלחה!\n\n🛒 *פרטי ההזמנה:*\n" + plist +
            "\n💰 *סה\"כ:* ₪" + str(total) + "\n\n" + addr_line +
            "🚚 *משלוח:* חברת המשלוחים תשלח לך הודעה יום לפני האספקה\n\nאנחנו זמינים לכל שאלה 😊\n\nתודה שבחרת idobetz! 🔪")

def build_kamado_promo():
    return ("🔥 *מבצע בלעדי לרוכשי מעשנת קמאדו!*\n\n🔪 סכין שף — רק ₪199\n🔪 סט 6 סכינים — רק ₪899\n\nרוצים להוסיף? שלחו לי הודעה ואוסיף להזמנה שלכם! 😊")

def get_sku(product):
    return str(product.get("sku", product.get("model", product.get("manufacturer_sku", "")))).lower().strip()

def handle_new_order(order):
    phone = order.get("telephone", order.get("phone", ""))
    order_id = order.get("order_id", "")
    products = order.get("products", [])
    if not phone:
        return
    send_whatsapp(phone, build_confirmation(order))
    time.sleep(2)
    if order_id:
        inv = create_invoice(order_id)
        if inv:
            send_file(phone, inv, "invoice.pdf", "📄 החשבונית שלך מ-idobetz")
            time.sleep(2)
    has_kamado = False
    for p in products:
        sku = get_sku(p)
        for known_sku, manual in PRODUCT_MANUALS.items():
            if known_sku.lower() in sku:
                send_file(phone, MANUALS_BASE + manual, manual, "📖 מדריך הפעלה ותחזוקה למוצר שלך")
                time.sleep(2)
                if known_sku in KAMADO_SKUS:
                    has_kamado = True
                break
    if has_kamado:
        send_whatsapp(phone, build_kamado_promo())
    send_whatsapp(OWNER_PHONE, "🔔 הזמנה חדשה!\nטלפון: " + str(phone) + "\nמספר: " + str(order_id))

SYSTEM_PROMPT = """אתה סוכן AI עבור Idobetz - חנות ציוד מטבח מקצועי (סכיני שף, מעשנות קמאדו, מכונות ברד וגלידה).
דבר עברית בלבד, קצר וברור. היה ידידותי ומקצועי.
משלוח חינם עד המדרכה, עד 5 ימי עסקים. איסוף עצמי מאלון תבור. עד 3 תשלומים. אחריות 12 חודשים.
הזמנות: idobetz.co.il
בכל התעניינות במוצר הוסף "תתחדשו!" בסוף. אל תציין שאתה בוט אלא אם שואלים."""

def ask_claude(phone, msg):
    print("ask_claude called. KEY exists: " + str(bool(CLAUDE_API_KEY)) + " len: " + str(len(CLAUDE_API_KEY)))
    if not CLAUDE_API_KEY:
        return "שגיאה: אין מפתח Claude"
    if phone not in conversation_history:
        conversation_history[phone] = []
    conversation_history[phone].append({"role": "user", "content": msg})
    if len(conversation_history[phone]) > 20:
        conversation_history[phone] = conversation_history[phone][-20:]
    data = json.dumps({"model": CLAUDE_MODEL, "max_tokens": 500, "system": SYSTEM_PROMPT, "messages": conversation_history[phone]}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("x-api-key", CLAUDE_API_KEY)
    req.add_header("anthropic-version", "2023-06-01")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read().decode("utf-8"))
            reply = result["content"][0]["text"]
            conversation_history[phone].append({"role": "assistant", "content": reply})
            print("Claude replied OK")
            return reply
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")
        except:
            pass
        print("Claude HTTP error " + str(e.code) + ": " + body[:300])
        return "שגיאת Claude: " + str(e.code)
    except Exception as e:
        print("Claude error: " + str(e))
        return "מצטערים, יש תקלה זמנית."

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"idobetz server running!")

    def do_POST(self):
        global agent_active
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body.decode("utf-8"))
        except:
            self.send_response(200); self.end_headers(); return

        event = data.get("event", data.get("event_slug", ""))
        if event == "new_order" or "new_order" in str(event):
            order = data.get("order", data.get("data", data))
            try:
                handle_new_order(order)
            except Exception as e:
                print("Order error: " + str(e))
            self.send_response(200); self.end_headers(); self.wfile.write(b'{"success":true}'); return

        if data.get("typeWebhook") == "incomingMessageReceived":
            sender = data.get("senderData", {})
            phone = sender.get("sender", "").replace("@c.us", "")
            msg = data.get("messageData", {}).get("textMessageData", {}).get("textMessage", "")
            print("MSG from " + phone + ": " + str(msg))

            if msg and phone:
                is_owner = phone.replace("+", "").replace("-", "") in ["972527777927", "527777927"]
                if is_owner and ("סוכן ON" in msg or "סוכן on" in msg.lower()):
                    agent_active = True
                    send_whatsapp(phone, "✅ הסוכן הופעל!")
                elif is_owner and ("סוכן OFF" in msg or "סוכן off" in msg.lower()):
                    agent_active = False
                    send_whatsapp(phone, "⛔ הסוכן כובה.")
                elif is_owner and "סטטוס" in msg:
                    send_whatsapp(phone, "סטטוס: " + ("✅ פעיל" if agent_active else "⛔ כבוי"))
                elif agent_active:
                    print("Agent active, calling Claude...")
                    reply = ask_claude(phone, msg)
                    time.sleep(1)
                    send_whatsapp(phone, reply)
                else:
                    print("Agent OFF, ignoring")

        self.send_response(200); self.end_headers(); self.wfile.write(b'{"success":true}')

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    print("=" * 50)
    print("idobetz server starting on port " + str(PORT))
    print("CLAUDE_API_KEY set: " + str(bool(CLAUDE_API_KEY)))
    print("=" * 50)
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

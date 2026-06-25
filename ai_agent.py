# -*- coding: utf-8 -*-
# idobetz — שרת מלא: סוכן AI + מוצרים אוטומטיים + מעקב משלוחים + אוטומציית הזמנות
import os
import json
import time
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

# ============ הגדרות ============
GREENAPI_INSTANCE = os.environ.get("GREENAPI_INSTANCE", "7107659046")
GREENAPI_TOKEN = os.environ.get("GREENAPI_TOKEN", "b2e18cfe01024a64a311bd08000d400e64a744292b664c1780")
GREENAPI_URL = "https://7107.api.greenapi.com"

ISTORES_API_KEY = os.environ.get("ISTORES_API_KEY", "b5adc1-89448f-d3734a-c74456-b1874d")
ISTORES_URL = "https://api.istores.co.il"

LIONWHEEL_KEY = os.environ.get("LIONWHEEL_KEY", "c_key_e596889d-08ec-4b1e-ba64-ea9e7e567cc9")
LIONWHEEL_URL = "https://members.lionwheel.com/api/v1"

CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-6"

OWNER_PHONE = os.environ.get("OWNER_PHONE", "972527777927")
PORT = int(os.environ.get("PORT", 8080))

MANUALS_BASE = "https://raw.githubusercontent.com/idoido1238-max/idobetz-agent/master/"
PROMPT_URL = MANUALS_BASE + "prompt.txt"

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
products_cache = ""   # נשמר כאן טקסט המוצרים, מתעדכן כל שעה
learned_notes = []    # לקחים שהבעלים מלמד דרך וואטסאפ
LEARN_FILE = "/tmp/learned_notes.json"

def load_learned():
    global learned_notes
    try:
        with open(LEARN_FILE, "r", encoding="utf-8") as f:
            learned_notes = json.load(f)
    except:
        learned_notes = []

def save_learned():
    try:
        with open(LEARN_FILE, "w", encoding="utf-8") as f:
            json.dump(learned_notes, f, ensure_ascii=False)
    except Exception as e:
        print("save_learned error: " + str(e))
DEFAULT_PROMPT = "אתה סוכן AI של idobetz - חנות ציוד מטבח. דבר עברית, קצר וידידותי."

# ============ קריאת prompt מ-GitHub ============
def get_system_prompt():
    try:
        with urllib.request.urlopen(urllib.request.Request(PROMPT_URL), timeout=10) as r:
            base = r.read().decode("utf-8")
    except Exception as e:
        print("Prompt load error: " + str(e))
        base = DEFAULT_PROMPT
    # המוצרים והמחירים נמצאים כבר ב-prompt.txt (מדויקים).
    # משיכת iStores משמשת רק לבדיקת מלאי (זמין/אזל), לא למחירים.
    if products_cache:
        base += "\n\n== בדיקת זמינות מלאי בלבד (לא מחירים!) ==\nהמחירים נמצאים ברשימת המחירים למעלה. המידע הבא הוא רק לבדיקה אם מוצר זמין:\n" + products_cache
    base += "\n\n== חשוב == אם שואלים כמה יחידות יש במלאי או כמה נמכרו - אל תענה על המספר, אמור שאתה לא חושף נתוני מלאי אך המוצר זמין/לא זמין."
    if learned_notes:
        base += "\n\n== תיקונים והנחיות נוספות מהבעלים (חשוב לפעול לפיהם) ==\n"
        for i, note in enumerate(learned_notes, 1):
            base += str(i) + ". " + note + "\n"
    return base

# ============ משיכת מוצרים מ-iStores ============
def fetch_products():
    global products_cache
    try:
        url = ISTORES_URL + "/products/200/1"
        req = urllib.request.Request(url, method="GET")
        for k, v in ISTORES_HEADERS.items():
            req.add_header(k, v)
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        products = data.get("Products", data.get("products", []))
        # דיבאג: מדפיס מבנה של מוצר אחד עם מבצע
        for dp in products[:5]:
            if isinstance(dp, dict):
                sku_dbg = dp.get("sku", dp.get("model", ""))
                if "adivmk6618" in str(sku_dbg).lower():
                    print("DEBUG product keys: " + str(list(dp.keys())))
                    print("DEBUG price: " + str(dp.get("price")) + " special: " + str(dp.get("special")) + " product_special: " + str(dp.get("product_special")))
        lines = []
        for p in products:
            if not isinstance(p, dict):
                continue
            # שם
            name = ""
            desc = p.get("product_description", {})
            if isinstance(desc, dict):
                for lang_id, d in desc.items():
                    if isinstance(d, dict) and d.get("name"):
                        name = d.get("name"); break
            if not name:
                name = p.get("name", p.get("model", ""))
            # מחיר + מבצע (בודק מבנים שונים)
            price = p.get("price", "")
            special = ""
            # נסיון 1: product_special / special / special_price
            for key in ["special", "product_special", "special_price", "price_special"]:
                sp = p.get(key)
                if sp:
                    if isinstance(sp, list) and len(sp) > 0:
                        item = sp[0]
                        if isinstance(item, dict):
                            special = item.get("price", item.get("special", item.get("value", "")))
                        else:
                            special = str(item)
                    elif isinstance(sp, dict):
                        special = sp.get("price", sp.get("special", sp.get("value", "")))
                    else:
                        special = str(sp)
                    if special and str(special) not in ["0", "0.0000", "0.00", ""]:
                        break
                    else:
                        special = ""
            # מלאי
            qty = p.get("quantity", 0)
            try:
                in_stock = int(qty) > 0
            except:
                in_stock = True
            stock_txt = "במלאי" if in_stock else "אזל"
            # בונה שורה - רק שם ומלאי, בלי מחיר (המחירים ב-prompt)
            line = "- " + str(name) + " | " + stock_txt
            lines.append(line)
        if lines:
            products_cache = "\n".join(lines)
            print("Products updated: " + str(len(lines)) + " items")
    except Exception as e:
        print("fetch_products error: " + str(e))

def product_updater():
    while True:
        fetch_products()
        time.sleep(3600)  # כל שעה

# ============ מעקב משלוחים LionWheel ============
LW_STATUS = {0:"טרם הוקצה",1:"הוקצה לשליח",2:"בדרך אליך",3:"נמסר",4:"בוטל",
             5:"נמסר (הלוך-חזור)",6:"במחסן",7:"יצא מהמחסן",8:"נכשל",9:"נכשל סופית",10:"בהעברה"}

def track_delivery(order_id):
    try:
        url = LIONWHEEL_URL + "/tasks/by_order_id/" + str(order_id) + "?key=" + LIONWHEEL_KEY
        with urllib.request.urlopen(urllib.request.Request(url), timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        print("LionWheel response for " + str(order_id) + ": " + json.dumps(data, ensure_ascii=False)[:300])
        # מחלץ את המשימה
        task = data
        if isinstance(data, dict):
            if "tasks" in data:
                tasks = data["tasks"]
                task = tasks[0] if tasks else None
            elif "task" in data:
                task = data["task"]
            elif "response" in data:
                task = data["response"]
                if isinstance(task, list):
                    task = task[0] if task else None
        elif isinstance(data, list):
            task = data[0] if data else None
        if not task or not isinstance(task, dict):
            return None
        dropoff = task.get("dropoff_at", task.get("pickup_at", task.get("date", "")))
        return {"date": dropoff}
    except urllib.error.HTTPError as e:
        print("track_delivery HTTP " + str(e.code))
        return None
    except Exception as e:
        print("track_delivery error: " + str(e))
        return None

# ============ פונקציות עזר ============
def format_phone(phone):
    phone = str(phone).replace("-", "").replace(" ", "").replace("+", "")
    if phone.startswith("0"):
        phone = "972" + phone[1:]
    if not phone.startswith("972"):
        phone = "972" + phone
    return phone + "@c.us"

def send_whatsapp(phone, message):
    url = GREENAPI_URL + "/waInstance" + GREENAPI_INSTANCE + "/sendMessage/" + GREENAPI_TOKEN
    data = json.dumps({"chatId": format_phone(phone), "message": message}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            print("WA sent")
            return True
    except Exception as e:
        print("WA error: " + str(e))
        return False

def send_file(phone, file_url, filename, caption=""):
    url = GREENAPI_URL + "/waInstance" + GREENAPI_INSTANCE + "/sendFileByUrl/" + GREENAPI_TOKEN
    data = json.dumps({"chatId": format_phone(phone), "urlFile": file_url, "fileName": filename, "caption": caption}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            print("File sent")
            return True
    except Exception as e:
        print("File error: " + str(e))
        return False

def create_invoice(order_id):
    url = ISTORES_URL + "/order/" + str(order_id) + "/create_doc"
    data = json.dumps({"doc_type": "חשבונית"}, ensure_ascii=False).encode("utf-8")
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
    name = (order.get("firstname", "") + " " + order.get("lastname", "")).strip() or "לקוח יקר"
    total = order.get("total", "")
    plist = ""
    for p in order.get("products", []):
        plist += "• " + str(p.get("name", "")) + " x" + str(p.get("quantity", 1)) + "\n"
    addr = order.get("shipping_address", order.get("payment_address", {}))
    addr_line = ""
    if addr.get("address_1") or addr.get("city"):
        addr_line = "📍 *כתובת משלוח:* " + addr.get("address_1", "") + " " + addr.get("city", "") + "\n\n"
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
    for p in order.get("products", []):
        sku = get_sku(p)
        for known, manual in PRODUCT_MANUALS.items():
            if known.lower() in sku:
                send_file(phone, MANUALS_BASE + manual, manual, "📖 מדריך הפעלה ותחזוקה למוצר שלך")
                time.sleep(2)
                if known in KAMADO_SKUS:
                    has_kamado = True
                break
    if has_kamado:
        send_whatsapp(phone, build_kamado_promo())
    send_whatsapp(OWNER_PHONE, "🔔 הזמנה חדשה!\nטלפון: " + str(phone) + "\nמספר: " + str(order_id))

# ============ סוכן AI ============
DELIVERY_TOOL = {
    "name": "check_delivery",
    "description": "בודק סטטוס ותאריך משלוח של הזמנה לפי מספר הזמנה. השתמש בזה כשלקוח שואל מתי ההזמנה שלו מגיעה, איפה ההזמנה, או על סטטוס משלוח, ונתן מספר הזמנה.",
    "input_schema": {
        "type": "object",
        "properties": {
            "order_id": {"type": "string", "description": "מספר ההזמנה שהלקוח נתן"}
        },
        "required": ["order_id"]
    }
}

def call_claude_api(messages):
    data = json.dumps({
        "model": CLAUDE_MODEL, "max_tokens": 600,
        "system": get_system_prompt(), "messages": messages,
        "tools": [DELIVERY_TOOL]
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("x-api-key", CLAUDE_API_KEY)
    req.add_header("anthropic-version", "2023-06-01")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def ask_claude(phone, msg):
    if not CLAUDE_API_KEY:
        return "שגיאה: אין מפתח Claude"
    if phone not in conversation_history:
        conversation_history[phone] = []
    conversation_history[phone].append({"role": "user", "content": msg})
    if len(conversation_history[phone]) > 20:
        conversation_history[phone] = conversation_history[phone][-20:]
    try:
        result = call_claude_api(conversation_history[phone])
        # בדיקה אם Claude רוצה להשתמש בכלי
        if result.get("stop_reason") == "tool_use":
            # שומר את בקשת הכלי
            conversation_history[phone].append({"role": "assistant", "content": result["content"]})
            tool_results = []
            for block in result["content"]:
                if block.get("type") == "tool_use" and block.get("name") == "check_delivery":
                    order_id = block["input"].get("order_id", "")
                    info = track_delivery(order_id)
                    if info and info.get("date"):
                        res_text = "תאריך משלוח מתוכנן: " + str(info["date"]) + ". ציין שזה מה שמופיע במערכת כרגע, ייתכנו שינויים, ושהלקוח יקבל הודעה מחברת המשלוחים יום לפני."
                    else:
                        res_text = "לא נמצאה הזמנה עם המספר הזה במערכת המשלוחים. בקש מהלקוח לוודא את המספר, או הצע להעביר לנציג."
                    tool_results.append({"type": "tool_result", "tool_use_id": block["id"], "content": res_text})
            conversation_history[phone].append({"role": "user", "content": tool_results})
            # קריאה שנייה לקבלת התשובה הסופית
            result = call_claude_api(conversation_history[phone])
        # מחלץ את הטקסט
        reply = ""
        for block in result.get("content", []):
            if block.get("type") == "text":
                reply += block["text"]
        if not reply:
            reply = "מצטערים, יש תקלה זמנית."
        conversation_history[phone].append({"role": "assistant", "content": reply})
        return reply
    except urllib.error.HTTPError as e:
        body = ""
        try: body = e.read().decode("utf-8")
        except: pass
        print("Claude HTTP error " + str(e.code) + ": " + body[:300])
        return "מצטערים, יש תקלה זמנית."
    except Exception as e:
        print("Claude error: " + str(e))
        return "מצטערים, יש תקלה זמנית."

# ============ שרת ============
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
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
            try: handle_new_order(data.get("order", data.get("data", data)))
            except Exception as e: print("Order error: " + str(e))
            self.send_response(200); self.end_headers(); self.wfile.write(b'{"success":true}'); return

        if data.get("typeWebhook") == "incomingMessageReceived":
            sender = data.get("senderData", {})
            phone = sender.get("sender", "").replace("@c.us", "")
            md = data.get("messageData", {})
            msg = md.get("textMessageData", {}).get("textMessage", "")
            # זיהוי מדיה (תמונה/סרטון/קול)
            mtype = md.get("typeMessage", "")
            if not msg and mtype in ["imageMessage", "videoMessage", "audioMessage", "documentMessage"]:
                media_names = {"imageMessage": "תמונה", "videoMessage": "סרטון",
                               "audioMessage": "הודעה קולית", "documentMessage": "קובץ"}
                msg = "[הלקוח שלח " + media_names.get(mtype, "מדיה") + "]"
            print("MSG from " + phone + ": " + str(msg))
            if msg and phone:
                is_owner = phone.replace("+", "").replace("-", "") in ["972527777927", "527777927"]
                if is_owner and ("סוכן ON" in msg or "סוכן on" in msg.lower()):
                    agent_active = True; send_whatsapp(phone, "✅ הסוכן הופעל!")
                elif is_owner and ("סוכן OFF" in msg or "סוכן off" in msg.lower()):
                    agent_active = False; send_whatsapp(phone, "⛔ הסוכן כובה.")
                elif is_owner and msg.strip().startswith("למד:"):
                    note = msg.split("למד:", 1)[1].strip()
                    if note:
                        learned_notes.append(note)
                        save_learned()
                        send_whatsapp(phone, "✅ למדתי! (סה\"כ " + str(len(learned_notes)) + " תיקונים)\nהתיקון: " + note)
                elif is_owner and msg.strip() == "רשימת תיקונים":
                    if learned_notes:
                        txt = "📚 התיקונים שלמדתי:\n\n"
                        for i, n in enumerate(learned_notes, 1):
                            txt += str(i) + ". " + n + "\n"
                        send_whatsapp(phone, txt)
                    else:
                        send_whatsapp(phone, "עדיין לא למדתי תיקונים. שלח 'למד: ...' כדי ללמד אותי.")
                elif is_owner and msg.strip().startswith("מחק תיקון"):
                    try:
                        num = int(msg.strip().split()[-1])
                        if 1 <= num <= len(learned_notes):
                            removed = learned_notes.pop(num-1)
                            save_learned()
                            send_whatsapp(phone, "🗑️ נמחק: " + removed)
                        else:
                            send_whatsapp(phone, "מספר לא תקין")
                    except:
                        send_whatsapp(phone, "שימוש: מחק תיקון [מספר]")
                elif is_owner and "סטטוס" in msg:
                    send_whatsapp(phone, "סטטוס: " + ("✅ פעיל" if agent_active else "⛔ כבוי") + "\nמוצרים: " + str(products_cache.count(chr(10))+1 if products_cache else 0) + "\nתיקונים שנלמדו: " + str(len(learned_notes)))
                elif agent_active:
                    reply = ask_claude(phone, msg)
                    time.sleep(1)
                    send_whatsapp(phone, reply)

        self.send_response(200); self.end_headers(); self.wfile.write(b'{"success":true}')

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    print("=" * 50)
    print("idobetz server starting on port " + str(PORT))
    print("CLAUDE_API_KEY set: " + str(bool(CLAUDE_API_KEY)))
    print("=" * 50)
    load_learned()
    print("Loaded " + str(len(learned_notes)) + " learned notes")
    # מתחיל משיכת מוצרים ברקע
    threading.Thread(target=product_updater, daemon=True).start()
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

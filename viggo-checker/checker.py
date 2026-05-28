import os
import json
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from html.parser import HTMLParser

VIGGO_BASE     = "https://gefriskole.viggo.dk"
GMAIL_SENDER   = os.environ["GMAIL_SENDER"]
GMAIL_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
GMAIL_RECEIVER = os.environ["GMAIL_RECEIVER"]
SEEN_FILE      = "seen_messages.json"


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen(ids):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(ids), f)


def send_mail(messages):
    subject = f"Ny besked på Viggo ({len(messages)} stk)"
    body_lines = ["Du har følgende nye beskeder på Viggo:\n"]
    for m in messages:
        body_lines.append(f"  Fra: {m['sender']}")
        body_lines.append(f"  Emne: {m['subject']}")
        body_lines.append(f"  Dato: {m['date']}")
        body_lines.append(f"  Besked: {m['preview']}\n")
    body_lines.append(f"\nLæs dem her: {VIGGO_BASE}/Basic/Message/Inbox")

    msg = MIMEMultipart()
    msg["From"]    = GMAIL_SENDER
    msg["To"]      = GMAIL_RECEIVER
    msg["Subject"] = subject
    msg.attach(MIMEText("\n".join(body_lines), "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_SENDER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_SENDER, GMAIL_RECEIVER, msg.as_string())
    print(f"Mail sendt: {subject}")


def get_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/148.0.0.0 Safari/537.36",
    })

    raw = os.environ.get("VIGGO_COOKIES")
    if not raw:
        raise Exception("VIGGO_COOKIES secret mangler")

    cookies = json.loads(raw)
    for c in cookies:
        session.cookies.set(c["name"], c["value"], domain=c.get("domain"), path=c.get("path"))

    r = session.get(f"{VIGGO_BASE}/Basic/Message/Inbox")
    if "/Account/Login" in r.url:
        raise Exception("Session udløbet — kør save_cookies.py igen og opdater VIGGO_COOKIES secret")

    print(f"Session OK — landet på: {r.url}")
    return session


def scrape_inbox(session):
    r = session.post(
        f"{VIGGO_BASE}/Basic/Message/Folder/7/?ajax=2",
        data={"searchText": "", "orderby": "recievedDESC"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    r.raise_for_status()

    messages = []

    class MessageParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.in_row = False
            self.current_id = None
            self.subject = None
            self.date = None
            self.preview = None
            self.in_small = False
            self.in_a = False
            self.div_depth = 0
            self.texts = []
            self.current_text = ""

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "li":
                drag_id = attrs.get("data-drag-id", "")
                if drag_id:
                    self.in_row = True
                    self.current_id = drag_id
                    self.subject = None
                    self.date = None
                    self.preview = None
                    self.texts = []
                    self.div_depth = 0
                    self.in_a = False
            if self.in_row:
                if tag == "div":
                    qa = attrs.get("data-qa", "")
                    if qa:
                        self.subject = qa
                    self.div_depth += 1
                if tag == "small":
                    self.in_small = True
                    self.current_text = ""
                if tag == "a" and "no-scroll" in attrs.get("class", ""):
                    self.in_a = True
                    self.texts = []

        def handle_endtag(self, tag):
            if self.in_row:
                if tag == "small" and self.in_small:
                    self.date = self.current_text.strip()
                    self.in_small = False
                if tag == "div":
                    self.div_depth -= 1
                if tag == "a" and self.in_a:
                    self.in_a = False
                if tag == "li":
                    self.in_row = False
                    sender = self.texts[0] if len(self.texts) > 0 else "Ukendt"
                    preview = self.texts[1] if len(self.texts) > 1 else ""
                    messages.append({
                        "id":      self.current_id,
                        "sender":  sender,
                        "subject": self.subject or "(intet emne)",
                        "date":    self.date or "Ukendt dato",
                        "preview": preview,
                    })

        def handle_data(self, data):
            if self.in_row and self.in_small:
                self.current_text += data
            if self.in_row and self.in_a and data.strip():
                self.texts.append(data.strip())

    parser = MessageParser()
    parser.feed(r.text)
    return messages


def main():
    print("Tjekker Viggo indbakke...")
    seen = load_seen()
    session = get_session()
    all_messages = scrape_inbox(session)
    print(f"Fandt {len(all_messages)} beskeder i alt")

    for m in all_messages:
        print(f"  ID:{m['id']} Fra:{m['sender']} Emne:{m['subject']} Dato:{m['date']}")

    new_messages = [m for m in all_messages if m["id"] not in seen]

    if new_messages:
        print(f"{len(new_messages)} nye — sender mail...")
        send_mail(new_messages)
        seen.update(m["id"] for m in new_messages)
        save_seen(seen)
    else:
        print("Ingen nye beskeder.")


if __name__ == "__main__":
    main()

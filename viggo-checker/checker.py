import os
import json
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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
        body_lines.append(f"  Dato: {m['date']}\n")
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
    from html.parser import HTMLParser

    r = session.get(f"{VIGGO_BASE}/Basic/Message/Inbox")
    r.raise_for_status()

    # DEBUG - prøv API endpoint
    r2 = session.get(f"{VIGGO_BASE}/Basic/Message/Inbox", headers={"Accept": "application/json, text/javascript, */*"})
    print("API STATUS:", r2.status_code)
    print("API CONTENT-TYPE:", r2.headers.get("content-type"))
    print("API SVAR:", r2.text[:2000])

    messages = []

    class InboxParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.in_row = False
            self.current_row_id = None
            self.cells = []
            self.current_cell = None

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "tr":
                row_id = attrs.get("data-id") or attrs.get("id") or ""
                if row_id or "message" in attrs.get("class", "").lower():
                    self.in_row = True
                    self.current_row_id = row_id
                    self.cells = []
            if self.in_row and tag == "td":
                self.current_cell = ""

        def handle_endtag(self, tag):
            if self.in_row and tag == "td" and self.current_cell is not None:
                self.cells.append(self.current_cell.strip())
                self.current_cell = None
            if tag == "tr" and self.in_row:
                self.in_row = False
                if len(self.cells) >= 2:
                    msg_id  = self.current_row_id or self.cells[1]
                    sender  = self.cells[0] if len(self.cells) > 0 else "Ukendt"
                    subject = self.cells[1] if len(self.cells) > 1 else "(intet emne)"
                    date    = self.cells[2] if len(self.cells) > 2 else "Ukendt dato"
                    if msg_id or subject:
                        messages.append({
                            "id":      msg_id,
                            "sender":  sender,
                            "subject": subject,
                            "date":    date,
                        })

        def handle_data(self, data):
            if self.current_cell is not None:
                self.current_cell += data

    parser = InboxParser()
    parser.feed(r.text)
    return messages


def main():
    print("Tjekker Viggo indbakke...")
    seen = load_seen()
    session = get_session()
    all_messages = scrape_inbox(session)
    print(f"Fandt {len(all_messages)} beskeder i alt")

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

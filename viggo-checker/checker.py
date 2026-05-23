import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

# --- Indstillinger (læses fra GitHub Secrets) ---
VIGGO_URL      = "https://gefriskole.viggo.dk"
VIGGO_USERNAME = os.environ["VIGGO_USERNAME"]
VIGGO_PASSWORD = os.environ["VIGGO_PASSWORD"]
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
    subject = f"📬 {len(messages)} ny besked(er) på Viggo"
    body_lines = ["Du har følgende nye beskeder på Viggo:\n"]
    for m in messages:
        body_lines.append(f"  • Fra: {m['sender']}")
        body_lines.append(f"    Emne: {m['subject']}")
        body_lines.append(f"    Modtaget: {m['date']}\n")
    body_lines.append(f"\nLæs dem her: {VIGGO_URL}/Basic/Message/Inbox")

    msg = MIMEMultipart()
    msg["From"]    = GMAIL_SENDER
    msg["To"]      = GMAIL_RECEIVER
    msg["Subject"] = subject
    msg.attach(MIMEText("\n".join(body_lines), "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_SENDER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_SENDER, GMAIL_RECEIVER, msg.as_string())
    print(f"Mail sendt: {subject}")


def scrape_inbox():
    messages = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Gå til login-siden
        page.goto(f"{VIGGO_URL}/Account/Login", wait_until="networkidle")

        # Udfyld login-formular
        page.fill('input[name="UserName"]', VIGGO_USERNAME)
        page.fill('input[name="Password"]', VIGGO_PASSWORD)
        page.click('button[type="submit"], input[type="submit"]')
        page.wait_for_load_state("networkidle")

        # Tjek at login lykkedes
        if "/Account/Login" in page.url:
            raise Exception("Login fejlede — tjek dine loginoplysninger i GitHub Secrets")

        # Gå til indbakken
        page.goto(f"{VIGGO_URL}/Basic/Message/Inbox", wait_until="networkidle")

        # Hent besked-rækker — Viggo bruger en tabel/liste med beskeder
        rows = page.query_selector_all("tr.message-row, .message-list-item, tr[data-id]")

        # Fallback: prøv bredere selektor
        if not rows:
            rows = page.query_selector_all("table tbody tr")

        for row in rows:
            msg_id  = row.get_attribute("data-id") or row.get_attribute("id") or ""
            sender  = ""
            subject = ""
            date    = ""

            # Prøv at finde afsender, emne og dato i kolonner
            cells = row.query_selector_all("td")
            if len(cells) >= 3:
                sender  = cells[0].inner_text().strip()
                subject = cells[1].inner_text().strip()
                date    = cells[2].inner_text().strip()
            elif len(cells) >= 2:
                sender  = cells[0].inner_text().strip()
                subject = cells[1].inner_text().strip()

            if msg_id or subject:
                messages.append({
                    "id":      msg_id or subject,
                    "sender":  sender  or "Ukendt",
                    "subject": subject or "(intet emne)",
                    "date":    date    or "Ukendt dato",
                })

        browser.close()
    return messages


def main():
    print("Tjekker Viggo indbakke...")
    seen = load_seen()
    all_messages = scrape_inbox()

    new_messages = [m for m in all_messages if m["id"] not in seen]

    if new_messages:
        print(f"Fandt {len(new_messages)} nye besked(er) — sender mail...")
        send_mail(new_messages)
        seen.update(m["id"] for m in new_messages)
        save_seen(seen)
    else:
        print("Ingen nye beskeder.")


if __name__ == "__main__":
    main()

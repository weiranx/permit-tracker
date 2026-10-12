"""Alert channels. Console always works; ntfy push needs no account."""
from __future__ import annotations

import os
import platform
import shutil
import smtplib
import subprocess
import urllib.request
from email.message import EmailMessage


def console(title: str, body: str, url: str) -> None:
    print(f"\n\a*** {title} ***\n{body}\n{url}\n", flush=True)


def ntfy(topic: str, title: str, body: str, url: str,
         server: str = "https://ntfy.sh") -> None:
    """Push to the ntfy phone/desktop app. Subscribe to the same topic there.
    Pick a long, unguessable topic name: anyone who knows it can read it."""
    req = urllib.request.Request(
        f"{server.rstrip('/')}/{topic}",
        data=body.encode(),
        headers={"Title": title, "Click": url, "Priority": "high", "Tags": "mountain"},
        method="POST",
    )
    urllib.request.urlopen(req, timeout=15).close()


def desktop(title: str, body: str) -> None:
    system = platform.system()
    if system == "Darwin":
        script = f'display notification {body!r} with title {title!r} sound name "Glass"'
        subprocess.run(["osascript", "-e", script], check=False)
    elif shutil.which("notify-send"):
        subprocess.run(["notify-send", "-u", "critical", title, body], check=False)


def email(to: str, title: str, body: str, url: str) -> None:
    """SMTP via env: SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD.
    For Gmail use an app password."""
    msg = EmailMessage()
    msg["Subject"] = title
    msg["From"] = os.environ.get("SMTP_FROM", os.environ["SMTP_USER"])
    msg["To"] = to
    msg.set_content(f"{body}\n\nBook: {url}")
    with smtplib.SMTP(os.environ.get("SMTP_HOST", "smtp.gmail.com"),
                      int(os.environ.get("SMTP_PORT", "587"))) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        s.send_message(msg)


def send_all(cfg: dict, title: str, body: str, url: str) -> None:
    # Env vars let CI keep the ntfy topic / email address out of the repo.
    cfg = {**cfg}
    cfg["ntfy_topic"] = cfg.get("ntfy_topic") or os.environ.get("NTFY_TOPIC")
    cfg["email_to"] = cfg.get("email_to") or os.environ.get("EMAIL_TO")
    console(title, body, url)
    for name, fn in (
        ("ntfy", lambda: ntfy(cfg["ntfy_topic"], title, body, url,
                              cfg.get("ntfy_server", "https://ntfy.sh"))),
        ("desktop", lambda: desktop(title, body)),
        ("email", lambda: email(cfg["email_to"], title, body, url)),
    ):
        enabled = {"ntfy": cfg.get("ntfy_topic"), "desktop": cfg.get("desktop"),
                   "email": cfg.get("email_to")}[name]
        if not enabled:
            continue
        try:
            fn()
        except Exception as e:  # never let a notifier kill the watcher
            print(f"[warn] {name} notification failed: {e}", flush=True)

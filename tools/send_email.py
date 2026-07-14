#!/usr/bin/env python3
"""
send_email.py — send an email (with attachments) via SMTP.

This is the agent's email-delivery tool. It lets a workflow deliver its output to
an inbox instead of (or in addition to) the ``output/`` folder — e.g. emailing the
traceability / compliance dashboards to a reviewer.

No third-party packages: uses the Python standard library (``smtplib`` +
``email.message``). Credentials are read from the environment / ``.env`` (loaded via
python-dotenv if available) and are NEVER printed or written to disk.

Configuration (put real values in .env, names only in .env.example):
    SMTP_HOST        e.g. smtp.gmail.com
    SMTP_PORT        default 587 (STARTTLS) — use 465 for implicit SSL
    SMTP_USER        the login username (usually the full email address)
    SMTP_PASSWORD    the password / app password  (Gmail: create an App Password)
    EMAIL_FROM       optional "From" address; defaults to SMTP_USER
    SMTP_SECURITY    optional: starttls (default) | ssl | none

Usage:
    python3 tools/send_email.py --to kiran@criodo.com \
        --subject "VDD reports" \
        --body-file body.txt \
        --attach output/VDD_traceability_dashboard.html \
        --attach output/VDD_compliance_dashboard.html

    # validate configuration + inputs without actually sending:
    python3 tools/send_email.py --to a@b.com --subject Hi --body Hi --dry-run
"""
import argparse
import mimetypes
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage

def _load_env(path=".env"):
    """Make SMTP_* available from a .env file without requiring any third-party package.

    Uses python-dotenv if it happens to be installed; otherwise falls back to a small
    stdlib parser (KEY=VALUE lines, '#' comments, optional surrounding quotes, and an
    optional leading 'export'). Values already set in the real environment win."""
    try:
        from dotenv import load_dotenv
        load_dotenv(path)
        return
    except Exception:
        pass
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.lower().startswith("export "):
                line = line[7:]
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


_load_env()


REQUIRED = ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD")


def _config():
    """Read SMTP settings from the environment; raise a clear error if incomplete."""
    missing = [k for k in REQUIRED if not os.environ.get(k)]
    if missing:
        raise SystemExit(
            "Missing SMTP configuration: " + ", ".join(missing) + ".\n"
            "Add them to your .env file (see .env.example). Secrets go ONLY in .env."
        )
    port = int(os.environ.get("SMTP_PORT", "587"))
    security = os.environ.get("SMTP_SECURITY", "").lower().strip()
    if not security:
        security = "ssl" if port == 465 else "starttls"
    return {
        "host": os.environ["SMTP_HOST"],
        "port": port,
        "user": os.environ["SMTP_USER"],
        "password": os.environ["SMTP_PASSWORD"],
        "from": os.environ.get("EMAIL_FROM") or os.environ["SMTP_USER"],
        "security": security,
    }


def _split(addrs):
    """Split a comma/semicolon separated recipient string into a clean list."""
    if not addrs:
        return []
    return [a.strip() for a in addrs.replace(";", ",").split(",") if a.strip()]


def build_message(cfg, to, cc, bcc, subject, body, html, attachments):
    msg = EmailMessage()
    msg["From"] = cfg["from"]
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg.set_content(body or "")
    if html:
        msg.add_alternative(html, subtype="html")

    for path in attachments:
        if not os.path.isfile(path):
            raise SystemExit(f"Attachment not found: {path}")
        ctype, encoding = mimetypes.guess_type(path)
        if ctype is None or encoding is not None:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        with open(path, "rb") as fh:
            msg.add_attachment(fh.read(), maintype=maintype, subtype=subtype,
                               filename=os.path.basename(path))
    return msg


def send(cfg, msg, recipients):
    """Open the SMTP connection per the configured security mode and send."""
    ctx = ssl.create_default_context()
    if cfg["security"] == "ssl":
        with smtplib.SMTP_SSL(cfg["host"], cfg["port"], context=ctx) as s:
            s.login(cfg["user"], cfg["password"])
            s.send_message(msg, from_addr=cfg["from"], to_addrs=recipients)
    else:
        with smtplib.SMTP(cfg["host"], cfg["port"]) as s:
            s.ehlo()
            if cfg["security"] == "starttls":
                s.starttls(context=ctx)
                s.ehlo()
            s.login(cfg["user"], cfg["password"])
            s.send_message(msg, from_addr=cfg["from"], to_addrs=recipients)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Send an email with attachments via SMTP")
    ap.add_argument("--to", required=True, help="recipient(s), comma-separated")
    ap.add_argument("--cc", default="")
    ap.add_argument("--bcc", default="")
    ap.add_argument("--subject", required=True)
    ap.add_argument("--body", help="plain-text body")
    ap.add_argument("--body-file", help="read plain-text body from a file")
    ap.add_argument("--html", help="HTML body")
    ap.add_argument("--html-file", help="read HTML body from a file")
    ap.add_argument("--attach", action="append", default=[], metavar="PATH",
                    help="file to attach (repeatable)")
    ap.add_argument("--dry-run", action="store_true",
                    help="validate config + inputs and print a summary; do not send")
    args = ap.parse_args(argv)

    body = args.body
    if args.body_file:
        with open(args.body_file, encoding="utf-8") as fh:
            body = fh.read()
    html = args.html
    if args.html_file:
        with open(args.html_file, encoding="utf-8") as fh:
            html = fh.read()

    to, cc, bcc = _split(args.to), _split(args.cc), _split(args.bcc)
    if not to:
        raise SystemExit("No valid --to recipient given.")

    cfg = _config()
    msg = build_message(cfg, to, cc, bcc, args.subject, body, html, args.attach)
    recipients = to + cc + bcc

    print(f"From:    {cfg['from']}")
    print(f"To:      {', '.join(to)}" + (f"  Cc: {', '.join(cc)}" if cc else "")
          + (f"  Bcc: {len(bcc)} hidden" if bcc else ""))
    print(f"Subject: {args.subject}")
    print(f"Server:  {cfg['host']}:{cfg['port']} ({cfg['security']})")
    if args.attach:
        print("Attachments:")
        for p in args.attach:
            print(f"  - {os.path.basename(p)} ({os.path.getsize(p):,} bytes)")

    if args.dry_run:
        print("\n[dry-run] configuration and inputs are valid; nothing sent.")
        return 0

    send(cfg, msg, recipients)
    print("\n✓ Email sent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

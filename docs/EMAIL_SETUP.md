# Sending reports by email — configuring `.env`

The agent can email its reports (the traceability and compliance dashboards) to a reviewer
using [`tools/send_email.py`](../tools/send_email.py). To do that it needs your mail-server
login. **These credentials live in a private file called `.env`** — never in any file that
gets shared or committed (`.env` is already listed in `.gitignore`).

## 1. Create your `.env` file
In the project folder, copy the template and open the copy:

```bash
cp .env.example .env
```

`.env.example` only lists the *names* of the settings (safe to share); your real values go
in `.env` (kept private). Fill in these lines:

| Setting | What it is | Example |
|---|---|---|
| `SMTP_HOST` | Your mail provider's outgoing (SMTP) server | `smtp.gmail.com` |
| `SMTP_PORT` | The port. `587` for STARTTLS (normal), `465` for SSL | `587` |
| `SMTP_USER` | The account you log in with — usually your full email address | `you@gmail.com` |
| `SMTP_PASSWORD` | The password / **app password** for that account (see below) | `abcd efgh ijkl mnop` |
| `EMAIL_FROM` | The "From" address recipients see (optional; defaults to `SMTP_USER`) | `you@gmail.com` |
| `SMTP_SECURITY` | Optional. `starttls` (default for 587), `ssl` (for 465), or `none` | `starttls` |

A filled-in `.env` looks like:

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=abcdefghijklmnop
EMAIL_FROM=you@gmail.com
```

## 2. Gmail users: use an **App Password**, not your normal password
Google blocks your everyday password for apps like this. Instead:

1. Turn on **2-Step Verification** on your Google account (required to create app passwords):
   <https://myaccount.google.com/security>.
2. Go to <https://myaccount.google.com/apppasswords>, create a new app password (name it
   e.g. "Requirements Validator"), and copy the **16-character** code it shows.
3. Paste that code as `SMTP_PASSWORD` (spaces don't matter).

> **Other providers.** Use your provider's SMTP host and port instead — e.g. Outlook/Office 365
> `smtp.office365.com` port `587`, Yahoo `smtp.mail.yahoo.com` port `465` (`SMTP_SECURITY=ssl`).
> Most providers also require an app password when 2-factor authentication is on.

## 3. Test it, then send
First do a dry run (checks your settings and the attachments **without sending**):

```bash
python3 tools/send_email.py --to you@example.com --subject "Test" --body "Hello" --dry-run
```

If that prints a valid summary, drop `--dry-run` to send for real. The full send workflow —
including the ready-to-run command that mails the VDD reports — is in
[`workflows/send-email.md`](../workflows/send-email.md). Or just ask your assistant in plain
English: *"email the VDD reports to someone@example.com."*

> **Prefer not to manage passwords?** You can instead authorize the **Gmail connector** once
> in an interactive session (claude.ai connector settings, or `/mcp` in interactive Claude
> Code) and skip `.env` entirely. See [`docs/CONNECTORS.md`](CONNECTORS.md).

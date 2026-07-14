# Workflow: Email a report to a reviewer

## Purpose
Deliver the agent's output (traceability dashboard, compliance dashboard, or the underlying
JSON) to someone's inbox — instead of, or in addition to, leaving it in `output/`.

## When to use
Any request like "email the VDD reports to <person>", "send the compliance dashboard to the
safety lead", "mail me the traceability matrix".

## Prerequisites (one-time setup)
Email sending needs credentials, which live **only in `.env`** (never in any other file).

**Option A — SMTP (works today, no interactive sign-in).** Add to `.env` (see `.env.example`):
- `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM`.
- For **Gmail**, `SMTP_PASSWORD` must be a Google **App Password** (create at
  https://myaccount.google.com/apppasswords — requires 2-Step Verification), *not* the normal
  account password.

**Option B — Gmail connector (MCP).** Cleaner, but authorizing it needs an **interactive**
session (claude.ai connector settings, or `/mcp` in interactive Claude Code). It cannot be
authorized in a non-interactive/automated run. Once authorized, prefer it over SMTP.

## Steps
1. Make sure the report(s) exist in `output/` — run the traceability / compliance workflow
   first if needed.
2. Confirm the recipient, subject, and which files to attach with the user before sending
   (sending email is outward-facing — always confirm).
3. Validate config without sending:
   ```
   python3 tools/send_email.py --to <addr> --subject "…" --body "…" --dry-run \
       --attach output/VDD_traceability_dashboard.html \
       --attach output/VDD_compliance_dashboard.html
   ```
4. Send for real by removing `--dry-run`. Use `--body-file` for a longer message.

## Example — send the VDD reports
```
python3 tools/send_email.py \
  --to kiran@criodo.com \
  --subject "VDD (Vehicle Direction Determination) — traceability & compliance reports" \
  --body-file output/VDD_email_body.txt \
  --attach output/VDD_traceability_dashboard.html \
  --attach output/VDD_compliance_dashboard.html
```

## Output
- An email delivered to the recipient. The tool prints a `✓ Email sent.` confirmation
  (or a clear error). It never prints the password.

## Validation
- Run with `--dry-run` first; confirm the From/To/Subject/attachments summary is correct.
- If the tool reports missing `SMTP_*` config, finish the one-time setup above — do **not**
  put credentials anywhere except `.env`.
- Confirm the attachments listed are the intended report files and that their byte sizes are
  non-zero.

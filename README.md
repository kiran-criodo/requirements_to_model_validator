# Requirements to Model Validator

An AI **agent** that validates a model against a set of requirements. Built in any
AI-enabled code editor — **no coding required**. You build and run it just by chatting
with an AI assistant.

> **Works with any IDE and any LLM.** Use whatever AI-enabled IDE you like — VSCode,
> Cursor, JetBrains, and others — with whatever LLM that IDE supports (Claude, GPT,
> Gemini, and more). This guide uses **Claude in VSCode** as the running example; wherever
> you see "Claude" or "VSCode," substitute your own assistant and editor. The agent's
> rulebook lives in `CLAUDE.md`; if your assistant reads a different filename (for example
> `AGENTS.md`), copy or point it at that file.

## Step 1 — Make your own copy from this template

This is a **GitHub template repository**, so you don't clone it directly — you stamp out
your own copy, already named after your agent:

1. On this repo's GitHub page, click the green **Use this template** button →
   **Create a new repository**.
2. Give the new repository **your agent's name** (e.g. `weekly-sales-bot`), pick
   public or private, and click **Create repository**. GitHub makes a brand-new repo with
   that name and a clean history — not a fork of the template.
3. **Clone** (download) your new repo to your computer — via your IDE's *Clone
   Repository* command (in VSCode: *Source Control → Clone Repository*), or run
   `git clone <your-new-repo-url>`.

Because you named the repo up front, your folder already carries your agent's name — no
renaming needed later.

> No GitHub account? You can instead run `git clone
> https://github.com/kiran-criodo/agent-builder-template.git your-agent-name` to download
> the starter into a folder named after your agent, and add an online home for it later.

## Step 2 — Start building

Open your new folder in your AI-enabled IDE (e.g. VSCode with the Claude extension),
make sure the AI assistant is connected, and type:

> **Let's start Building**

Your assistant will then interview you step by step and create everything for you.

> **Tip — you can schedule it.** Once a workflow works, your agent doesn't have to be run
> by hand every time. Most AI-enabled assistants can run a workflow **periodically** (e.g.
> every morning, or once an hour) — just ask yours in plain English. See *"Running Your
> Agent on a Schedule"* in [`CREATE_AGENT_PROCESS.md`](CREATE_AGENT_PROCESS.md).

## What's here

- **`CREATE_AGENT_PROCESS.md`** — the full, plain-English guide. Read it first if you
  like, or just say "Let's start Building" and follow along.
- **`CLAUDE.md`** — the agent's rulebook. It also contains the guided-build instructions
  your assistant follows while helping you. (If your assistant reads a different filename,
  such as `AGENTS.md`, copy or point it at this file.)
- **`docs/SETUP.md`** — how to set up your computer (one-time).
- **`docs/CONNECTORS.md`** — connecting your agent to outside services (cloud drive,
  email, databases, WhatsApp, MCP servers) for input *and* output.
- **`docs/GIT_GUIDE.md`** — sharing your agent with others, in plain language.
- Folders (`workflows/`, `tools/`, `memory/`, …) — the agent's parts, filled in as you
  build.

## Sending reports by email — configuring `.env`

The agent can email its reports (the traceability and compliance dashboards) to a reviewer
using [`tools/send_email.py`](tools/send_email.py). To do that it needs your mail-server
login. **These credentials live in a private file called `.env`** — never in any file that
gets shared or committed (`.env` is already listed in `.gitignore`).

### 1. Create your `.env` file
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

### 2. Gmail users: use an **App Password**, not your normal password
Google blocks your everyday password for apps like this. Instead:

1. Turn on **2-Step Verification** on your Google account (required to create app passwords):
   <https://myaccount.google.com/security>.
2. Go to <https://myaccount.google.com/apppasswords>, create a new app password (name it
   e.g. "Requirements Validator"), and copy the **16-character** code it shows.
3. Paste that code as `SMTP_PASSWORD` (spaces don't matter).

> **Other providers.** Use your provider's SMTP host and port instead — e.g. Outlook/Office 365
> `smtp.office365.com` port `587`, Yahoo `smtp.mail.yahoo.com` port `465` (`SMTP_SECURITY=ssl`).
> Most providers also require an app password when 2-factor authentication is on.

### 3. Test it, then send
First do a dry run (checks your settings and the attachments **without sending**):

```bash
python3 tools/send_email.py --to you@example.com --subject "Test" --body "Hello" --dry-run
```

If that prints a valid summary, drop `--dry-run` to send for real. The full send workflow —
including the ready-to-run command that mails the VDD reports — is in
[`workflows/send-email.md`](workflows/send-email.md). Or just ask your assistant in plain
English: *"email the VDD reports to someone@example.com."*

> **Prefer not to manage passwords?** You can instead authorize the **Gmail connector** once
> in an interactive session (claude.ai connector settings, or `/mcp` in interactive Claude
> Code) and skip `.env` entirely. See [`docs/CONNECTORS.md`](docs/CONNECTORS.md).

## New to this?

Start with [`CREATE_AGENT_PROCESS.md`](CREATE_AGENT_PROCESS.md). It explains what an
agent is and walks you through building one from scratch.

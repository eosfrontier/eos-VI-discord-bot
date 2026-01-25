# EOS VI Discord Bot (VI Manager)

A lightweight Discord bot that lets SLs speak as multiple in-universe VIs using a single bot process.

**How it works**
- The bot exposes a slash command: `/vi`
- Only users with the configured SL role can invoke it
- The bot posts messages appears as the selected VI (name + avatar)

---

## Features
- Slash command: `/vi`
- VI persona selection (name + avatar) via `personas.yaml`
- Role-based authorization (SL-only)
- Guild restriction

---

## Requirements
- Python 3.10+ (recommended)
- A Discord Application + Bot token
- Bot invited to the target server with the correct scopes and permissions

---

## Environment Variables

Create a `.env` file in the project root:

```env
DISCORD_TOKEN=
SL_ROLE_NAME=
GUILD_ID=

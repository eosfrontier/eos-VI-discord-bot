import os
import json
import yaml
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()


WEBHOOK_CACHE_FILE = "webhooks.json"
PERSONAS_FILE = "personas.yaml"

TOKEN = os.getenv("DISCORD_TOKEN")
SL_ROLE_NAME = os.getenv("SL_ROLE_NAME", "").strip()

GUILD_ID = os.getenv("GUILD_ID", "").strip()
ALLOWED_GUILD_ID: int | None = int(GUILD_ID) if GUILD_ID.isdigit() else None

def guild_allowed(guild_id: int | None) -> bool:
    return ALLOWED_GUILD_ID is not None and guild_id == ALLOWED_GUILD_ID


def load_personas():
    with open(PERSONAS_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    vis = data.get("vis", [])
    return {p["id"]: p for p in vis if "id" in p and "name" in p}


def load_webhook_cache():
    if not os.path.exists(WEBHOOK_CACHE_FILE):
        return {}
    with open(WEBHOOK_CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_webhook_cache(cache):
    with open(WEBHOOK_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

personas = load_personas()


async def ensure_channel_webhook_url(channel: discord.TextChannel) -> str:

    cache = load_webhook_cache()
    key = str(channel.id)

    if key in cache:
        return cache[key]

    webhook = await channel.create_webhook(name="VI Relay")
    cache[key] = webhook.url
    save_webhook_cache(cache)
    return webhook.url


def user_is_sl(member: discord.Member) -> bool:
    if not SL_ROLE_NAME:
        return True
    return any(r.name == SL_ROLE_NAME for r in getattr(member, "roles", []))


def hex_to_int(hex_str: str | None) -> int:
    if not hex_str:
        return 0x00E5FF
    return int(hex_str.lstrip("#"), 16)

def to_monospace_block(text: str) -> str:
    safe = (text or "").replace("```", "``\u200b`")
    return f"```text\n{safe}\n```"

async def post_via_webhook(
    webhook_url: str,
    content: str,
    username: str,
    avatar_url: str | None,
    thread_id: int | None,
    accent_color: str | None,
):
    params = ["wait=true"]
    if thread_id:
        params.append(f"thread_id={thread_id}")
    url = webhook_url + "?" + "&".join(params)

    payload = {
    "username": username,
    "avatar_url": avatar_url,
    "allowed_mentions": {"parse": []},
    "embeds": [
            {
            "description": content,
            "color": hex_to_int(accent_color),
            }
        ],
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            if resp.status not in (200, 204):
                body = await resp.text()
                raise RuntimeError(f"Webhook send failed: {resp.status} {body}")


@bot.event
async def setup_hook():
    if ALLOWED_GUILD_ID:
        guild = discord.Object(id=ALLOWED_GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        try:
            await bot.tree.sync(guild=guild)
        except discord.Forbidden:
            await bot.tree.sync()
    else:
        await bot.tree.sync()


@bot.tree.command(name="vi", description="Send a message as a configured VI.")
@app_commands.describe(vi="Which VI identity to use", message="What should the VI say?")
async def vi(interaction: discord.Interaction, vi: str, message: str):

    if not guild_allowed(interaction.guild_id):
        return await interaction.response.send_message(
            "This bot is not authorized for this server.",
            ephemeral=True,
        )
    
    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        return await interaction.response.send_message("Use this in a server channel.", ephemeral=True)

    if not user_is_sl(interaction.user):
        return await interaction.response.send_message(
            "You don’t have permission to use this command.",
            ephemeral=True,
        )

    if vi not in personas:
        return await interaction.response.send_message(
            "Unknown VI. Try again and pick a valid one.",
            ephemeral=True,
        )

    persona = personas[vi]

    thread_id = None
    channel = interaction.channel

    if isinstance(channel, discord.Thread):
        thread_id = channel.id
        base_channel = channel.parent
        if base_channel is None:
            return await interaction.response.send_message("This thread has no parent channel?", ephemeral=True)
    else:
        base_channel = channel

    if not isinstance(base_channel, discord.TextChannel):
        return await interaction.response.send_message("Unsupported channel type.", ephemeral=True)

    await interaction.response.defer(ephemeral=True)

    try:
        webhook_url = await ensure_channel_webhook_url(base_channel)
        await post_via_webhook(
        webhook_url=webhook_url,
        content=message,
        username=persona["name"],
        avatar_url=persona.get("avatarUrl"),
        thread_id=thread_id,
        accent_color=persona.get("accentColor"),
    )

        await interaction.followup.send(f"Sent as **{persona['name']}**.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Failed to send: {e}", ephemeral=True)


@vi.autocomplete("vi")
async def vi_autocomplete(interaction: discord.Interaction, current: str):
    current_lower = (current or "").lower()
    results = []

    for vid, p in personas.items():
        if p.get("hidden", False):
            continue

        if current_lower in p["name"].lower() or current_lower in vid.lower():
            results.append(app_commands.Choice(name=p["name"], value=vid))

        if len(results) >= 25:
            break

    return results


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN missing in .env")
    bot.run(TOKEN)

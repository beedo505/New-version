import os
import traceback
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv


load_dotenv()


# =========================
# Environment Variables
# =========================

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

if not DISCORD_TOKEN:
    raise RuntimeError(
        "❌ DISCORD_TOKEN is missing. "
        "Please add it to your .env file or hosting environment variables."
    )


# =========================
# Discord Intents
# =========================

intents = discord.Intents.default()

intents.members = True
intents.message_content = True
intents.guilds = True
intents.messages = True


# =========================
# Bot
# =========================

bot = commands.Bot(
    command_prefix="-",
    intents=intents
)


# =========================
# Load Cogs
# =========================

@bot.event
async def setup_hook():
    cogs_path = Path(__file__).resolve().parent / "cogs"

    if not cogs_path.exists():
        raise RuntimeError(
            f"❌ Cogs directory was not found: {cogs_path}"
        )

    cog_files = sorted(
        file for file in cogs_path.glob("*.py")
        if file.name != "__init__.py"
    )

    if not cog_files:
        raise RuntimeError(
            f"❌ No Cog files were found in: {cogs_path}"
        )

    for file in cog_files:
        extension = f"cogs.{file.stem}"

        try:
            await bot.load_extension(extension)
            print(f"✅ Loaded extension: {file.name}")

        except Exception:
            print(f"❌ Failed to load extension: {file.name}")
            traceback.print_exc()
            raise


# =========================
# Bot Ready
# =========================

@bot.event
async def on_ready():
    print(f"✅ Bot is ready! Logged in as {bot.user.name} (ID: {bot.user.id})")


# =========================
# Start Bot
# =========================

bot.run(DISCORD_TOKEN)

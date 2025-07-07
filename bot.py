import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.messages = True

bot = commands.Bot(command_prefix="-", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot is ready! Logged in as {bot.user.name}")

    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                print(f"✅ Loaded extension: {filename}")
            except Exception as e:
                print(f"❌ Failed to load extension {filename}: {e}")

bot.run(os.getenv("Your bot token here"))

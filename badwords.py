import discord
from discord.ext import commands
from discord.ui import View, Button
from pymongo import MongoClient
import os

client = MongoClient(os.getenv("MONGODB_URI"))
db = client["Prison"]
offensive_words_collection = db["offensive_words"]

class BadWordsView(View):
    def __init__(self):
        super().__init__()

    @discord.ui.button(label="Add Bad Words", style=discord.ButtonStyle.primary)
    async def add_words(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Use `-abad word1, word2, word3` to add bad words.", ephemeral=True)

    @discord.ui.button(label="Remove Bad Words", style=discord.ButtonStyle.danger)
    async def remove_words(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Use `-rbad word` to remove a bad word.", ephemeral=True)

    @discord.ui.button(label="List Bad Words", style=discord.ButtonStyle.secondary)
    async def list_words(self, interaction: discord.Interaction, button: discord.ui.Button):
        words = [word["word"] for word in offensive_words_collection.find({}, {"_id": 0, "word": 1})]
        if words:
            await interaction.response.send_message(f"📝 Offensive Words: {', '.join(words)}", ephemeral=True)
        else:
            await interaction.response.send_message("✅ No offensive words in the database!", ephemeral=True)

class BadWords(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def abad(self, ctx, *, words: str):
        word_list = [word.strip().lower() for word in words.split(",")]
        added_words = []
        for word in word_list:
            if not offensive_words_collection.find_one({"word": word, "server_id": ctx.guild.id}):
                offensive_words_collection.insert_one({"word": word, "server_id": ctx.guild.id})
                added_words.append(word)
        if added_words:
            await ctx.message.reply(f"✅ Added: {', '.join(added_words)} to the offensive words list!")
        else:
            await ctx.message.reply("⚠ All words are already saved!")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def rbad(self, ctx, *, words: str):
        word_list = [word.strip().lower() for word in words.split(",")]
        removed_words = []
        for word in word_list:
            if offensive_words_collection.find_one({"word": word, "server_id": ctx.guild.id}):
                offensive_words_collection.delete_one({"word": word, "server_id": ctx.guild.id})
                removed_words.append(word)
        if removed_words:
            await ctx.message.reply(f"✅ Removed: {', '.join(removed_words)} from the offensive words list!")
        else:
            await ctx.message.reply("⚠️ None of the provided words were found in the database!")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def lbad(self, ctx):
        words = [word["word"] for word in offensive_words_collection.find({"server_id": ctx.guild.id}, {"_id": 0, "word": 1})]
        if words:
            await ctx.message.reply(f"📝 Offensive Words: {', '.join(words)}")
        else:
            await ctx.message.reply("✅ No offensive words in the database!")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def pbad(self, ctx):
        await ctx.message.reply("🔧 Manage Offensive Words:", view=BadWordsView())

async def setup(bot):
    await bot.add_cog(BadWords(bot))

import discord
from discord.ext import commands
from discord.ui import View

from db import offensive_words_collection


# =========================
# Helper Functions
# =========================

def split_message(text: str, max_length: int = 1900) -> list[str]:
    """Split a long message into chunks that fit Discord's message limit."""
    return [
        text[i:i + max_length]
        for i in range(0, len(text), max_length)
    ]


# =========================
# Bad Words Management View
# =========================

class BadWordsView(View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.message = None

    async def interaction_check(
        self,
        interaction: discord.Interaction
    ) -> bool:

        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This menu can only be used inside a server.",
                ephemeral=True
            )
            return False

        if interaction.guild.id != self.guild_id:
            await interaction.response.send_message(
                "❌ This menu belongs to another server.",
                ephemeral=True
            )
            return False

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Only server administrators can use this menu.",
                ephemeral=True
            )
            return False

        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    @discord.ui.button(
        label="Add Bad Words",
        style=discord.ButtonStyle.primary
    )
    async def add_words(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_message(
            "Use `-abad word1, word2, word3` to add bad words.",
            ephemeral=True
        )

    @discord.ui.button(
        label="Remove Bad Words",
        style=discord.ButtonStyle.danger
    )
    async def remove_words(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_message(
            "Use `-rbad word1, word2, word3` to remove bad words.",
            ephemeral=True
        )

    @discord.ui.button(
        label="List Bad Words",
        style=discord.ButtonStyle.secondary
    )
    async def list_words(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        words = [
            word["word"]
            for word in offensive_words_collection.find(
                {"server_id": self.guild_id},
                {"_id": 0, "word": 1}
            )
        ]

        if not words:
            await interaction.response.send_message(
                "✅ No offensive words in the database!",
                ephemeral=True
            )
            return

        message = f"📝 Offensive Words:\n{', '.join(words)}"
        chunks = split_message(message)

        await interaction.response.send_message(
            chunks[0],
            ephemeral=True
        )

        for chunk in chunks[1:]:
            await interaction.followup.send(
                chunk,
                ephemeral=True
            )


# =========================
# Bad Words Cog
# =========================

class BadWords(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def abad(self, ctx, *, words: str):
        word_list = [
            word.strip().lower()
            for word in words.split(",")
            if word.strip()
        ]

        added_words = []

        for word in word_list:
            existing_word = offensive_words_collection.find_one(
                {
                    "word": word,
                    "server_id": ctx.guild.id
                }
            )

            if not existing_word:
                offensive_words_collection.insert_one(
                    {
                        "word": word,
                        "server_id": ctx.guild.id
                    }
                )

                added_words.append(word)

        if added_words:
            message = (
                f"✅ Added: {', '.join(added_words)} "
                f"to the offensive words list!"
            )
        else:
            message = "⚠️ All provided words are already saved!"

        for chunk in split_message(message):
            await ctx.message.reply(chunk)

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def rbad(self, ctx, *, words: str):
        word_list = [
            word.strip().lower()
            for word in words.split(",")
            if word.strip()
        ]

        removed_words = []

        for word in word_list:
            existing_word = offensive_words_collection.find_one(
                {
                    "word": word,
                    "server_id": ctx.guild.id
                }
            )

            if existing_word:
                offensive_words_collection.delete_one(
                    {
                        "word": word,
                        "server_id": ctx.guild.id
                    }
                )

                removed_words.append(word)

        if removed_words:
            message = (
                f"✅ Removed: {', '.join(removed_words)} "
                f"from the offensive words list!"
            )
        else:
            message = (
                "⚠️ None of the provided words were found "
                "in the database!"
            )

        for chunk in split_message(message):
            await ctx.message.reply(chunk)

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def lbad(self, ctx):
        words = [
            word["word"]
            for word in offensive_words_collection.find(
                {"server_id": ctx.guild.id},
                {"_id": 0, "word": 1}
            )
        ]

        if not words:
            await ctx.message.reply(
                "✅ No offensive words in the database!"
            )
            return

        message = f"📝 Offensive Words:\n{', '.join(words)}"

        for chunk in split_message(message):
            await ctx.message.reply(chunk)

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def pbad(self, ctx):
        view = BadWordsView(ctx.guild.id)

        message = await ctx.message.reply(
            "🔧 Manage Offensive Words:",
            view=view
        )

        view.message = message


# =========================
# Cog Setup
# =========================

async def setup(bot):
    await bot.add_cog(BadWords(bot))

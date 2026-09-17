import discord
from discord.ext import commands

from db import db


class ExceptionManager:
    def __init__(self, db):
        self.collection = db["guilds"]

    def get_exceptions(self, guild_id):
        server_data = self.collection.find_one(
            {"guild_id": guild_id},
            {"exception_channels": 1}
        )

        return (
            server_data.get("exception_channels", [])
            if server_data
            else []
        )

    def add_exception(self, guild_id, channel_id):
        result = self.collection.update_one(
            {"guild_id": guild_id},
            {
                "$addToSet": {
                    "exception_channels": channel_id
                }
            },
            upsert=True
        )

        return (
            result.modified_count > 0
            or result.upserted_id is not None
        )

    def remove_exception(self, guild_id, channel_id):
        result = self.collection.update_one(
            {"guild_id": guild_id},
            {
                "$pull": {
                    "exception_channels": channel_id
                }
            }
        )

        return result.modified_count > 0


class Exceptions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.manager = ExceptionManager(db)

    # =========================================================
    # Add Exception
    # =========================================================

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def add(self, ctx, *, channel=None):

        guild_id = str(ctx.guild.id)

        # Use the current channel if no channel was provided
        if not channel:
            channel_to_add = ctx.channel

        else:
            # Channel ID
            if channel.isdigit():
                channel_to_add = ctx.guild.get_channel(
                    int(channel)
                )

            # Channel mention
            else:
                channel_to_add = (
                    ctx.message.channel_mentions[0]
                    if ctx.message.channel_mentions
                    else None
                )

            if not channel_to_add:
                await ctx.message.reply(
                    "❌ Invalid channel ID or mention!"
                )
                return

        added = self.manager.add_exception(
            guild_id,
            str(channel_to_add.id)
        )

        if not added:
            await ctx.message.reply(
                f"⚠️ Channel {channel_to_add.mention} "
                "is already in the exceptions list."
            )
            return

        await ctx.message.reply(
            f"✅ Channel {channel_to_add.mention} "
            "has been added to exceptions."
        )

    # =========================================================
    # Remove Exception
    # =========================================================

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def rem(self, ctx, *, channel=None):

        guild_id = str(ctx.guild.id)

        # Use the current channel if no channel was provided
        if not channel:
            channel_to_remove = ctx.channel

        else:
            # Channel ID
            if channel.isdigit():
                channel_to_remove = ctx.guild.get_channel(
                    int(channel)
                )

            # Channel mention
            else:
                channel_to_remove = (
                    ctx.message.channel_mentions[0]
                    if ctx.message.channel_mentions
                    else None
                )

            if not channel_to_remove:
                await ctx.message.reply(
                    "❌ Invalid channel! "
                    "Provide a valid ID or mention a channel."
                )
                return

        removed = self.manager.remove_exception(
            guild_id,
            str(channel_to_remove.id)
        )

        if not removed:
            await ctx.message.reply(
                f"⚠️ Channel {channel_to_remove.mention} "
                "is not in the exceptions list."
            )
            return

        await ctx.message.reply(
            f"✅ Channel {channel_to_remove.mention} "
            "has been removed from exceptions."
        )

    # =========================================================
    # List Exceptions
    # =========================================================

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def list(self, ctx):

        guild_id = str(ctx.guild.id)

        exceptions = self.manager.get_exceptions(
            guild_id
        )

        if not exceptions:
            await ctx.message.reply(
                "⚠️ No exception channels found in this server."
            )
            return

        exception_channels = []

        for channel_id in exceptions:
            channel = ctx.guild.get_channel(
                int(channel_id)
            )

            if channel:
                if isinstance(channel, discord.VoiceChannel):
                    channel_type = "🔊 Voice"
                else:
                    channel_type = "💬 Text"

                exception_channels.append(
                    f"**{channel.mention}** ({channel_type})"
                )

        if not exception_channels:
            await ctx.message.reply(
                "⚠️ No valid exception channels found."
            )
            return

        embed = discord.Embed(
            title="📌 Exception Channels",
            color=0x2F3136
        )

        embed.add_field(
            name="📝 Channels:",
            value="\n".join(exception_channels),
            inline=False
        )

        await ctx.message.reply(embed=embed)


# =============================================================
# Extension Setup
# =============================================================

async def setup(bot):
    await bot.add_cog(Exceptions(bot))

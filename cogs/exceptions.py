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

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def add(
        self,
        ctx,
        channel: discord.abc.GuildChannel = None
    ):
        guild_id = str(ctx.guild.id)

        if channel is None:
            await ctx.message.reply(
                "❌ Please mention a valid channel.\n"
                "Example: `-add #prison`"
            )
            return

        if channel.guild.id != ctx.guild.id:
            await ctx.message.reply(
                "❌ You can only add channels from this server."
            )
            return

        added = self.manager.add_exception(
            guild_id,
            str(channel.id)
        )

        if not added:
            await ctx.message.reply(
                f"⚠️ Channel {channel.mention} is already "
                f"in the exceptions list."
            )
            return

        await ctx.message.reply(
            f"✅ Channel {channel.mention} has been added "
            f"to exceptions."
        )

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def rem(
        self,
        ctx,
        channel: discord.abc.GuildChannel = None
    ):
        guild_id = str(ctx.guild.id)

        if channel is None:
            await ctx.message.reply(
                "❌ Please mention a valid channel.\n"
                "Example: `-rem #prison`"
            )
            return

        if channel.guild.id != ctx.guild.id:
            await ctx.message.reply(
                "❌ You can only remove channels from this server."
            )
            return

        removed = self.manager.remove_exception(
            guild_id,
            str(channel.id)
        )

        if not removed:
            await ctx.message.reply(
                f"⚠️ Channel {channel.mention} is not "
                f"in the exceptions list."
            )
            return

        await ctx.message.reply(
            f"✅ Channel {channel.mention} has been "
            f"removed from exceptions."
        )

    @commands.command(name="list")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def list_exceptions(self, ctx):
        guild_id = str(ctx.guild.id)

        exceptions = self.manager.get_exceptions(guild_id)

        if not exceptions:
            await ctx.message.reply(
                "⚠️ No exception channels found in this server."
            )
            return

        exception_channels = []

        for channel_id in exceptions:
            try:
                channel = ctx.guild.get_channel(
                    int(channel_id)
                )
            except (TypeError, ValueError):
                channel = None

            if channel:
                if isinstance(channel, discord.VoiceChannel):
                    channel_type = "🔊 Voice"
                elif isinstance(channel, discord.CategoryChannel):
                    channel_type = "📁 Category"
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


async def setup(bot):
    await bot.add_cog(Exceptions(bot))

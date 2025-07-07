import discord
from discord.ext import commands
from db import collection, guilds_collection, settings_collection
from db import db
import os

class ExceptionManager:
    def __init__(self, db):
        self.db = db
        self.collection = self.db["guilds"]

    def get_exceptions(self, guild_id):
        server_data = self.collection.find_one({"guild_id": guild_id})
        return server_data.get("exception_channels", []) if server_data else []

    def add_exception(self, guild_id, channel_id):
        exceptions = self.get_exceptions(guild_id)
        if channel_id in exceptions:
            return False
        exceptions.append(channel_id)
        self.collection.update_one(
            {"guild_id": guild_id},
            {"$set": {"exception_channels": exceptions}},
            upsert=True
        )
        return True

    def remove_exception(self, guild_id, channel_id):
        exceptions = self.get_exceptions(guild_id)
        if channel_id not in exceptions:
            return False
        exceptions.remove(channel_id)
        self.collection.update_one(
            {"guild_id": guild_id},
            {"$set": {"exception_channels": exceptions}}
        )
        return True

class Exceptions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.manager = ExceptionManager(db)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def add(self, ctx, *, channel=None):
        guild_id = str(ctx.guild.id)
        channel_to_add = None

        if channel:
            if channel.isdigit():
                channel_to_add = ctx.guild.get_channel(int(channel))
            else:
                channel_to_add = ctx.message.channel_mentions[0] if ctx.message.channel_mentions else None
            if not channel_to_add:
                await ctx.message.reply("❌ Invalid channel ID or mention!")
                return
        else:
            channel_to_add = ctx.channel

        self.manager.add_exception(guild_id, str(channel_to_add.id))
        await ctx.message.reply(f"✅ Channel {channel_to_add.name} has been added to exceptions.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def rem(self, ctx, *, channel=None):
        guild_id = str(ctx.guild.id)
        channel_to_remove = None

        if channel:
            if channel.isdigit():
                channel_to_remove = ctx.guild.get_channel(int(channel))
            else:
                channel_to_remove = ctx.message.channel_mentions[0] if ctx.message.channel_mentions else None
            if not channel_to_remove:
                await ctx.message.reply("❌ Invalid channel! Provide a valid ID or mention a channel.")
                return
        else:
            channel_to_remove = ctx.channel

        self.manager.remove_exception(guild_id, str(channel_to_remove.id))
        await channel_to_remove.set_permissions(ctx.guild.default_role, view_channel=False)
        await ctx.message.reply(f"✅ Channel {channel_to_remove.mention} has been removed from exceptions.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def list(self, ctx):
        guild_id = str(ctx.guild.id)
        exceptions = self.manager.get_exceptions(guild_id)

        if exceptions:
            exception_channels = []
            for channel_id in exceptions:
                channel = ctx.guild.get_channel(int(channel_id))
                if channel:
                    channel_type = '🔊 Voice' if isinstance(channel, discord.VoiceChannel) else '💬 Text'
                    exception_channels.append(f"**{channel.mention}** ({channel_type})")

            if exception_channels:
                embed = discord.Embed(title="📌 Exception Channels", color=0x2f3136)
                embed.add_field(name="📝 Channels:", value="\n".join(exception_channels), inline=False)
                await ctx.message.reply(embed=embed)
            else:
                await ctx.message.reply("⚠ No valid exception channels found.")
        else:
            await ctx.message.reply("⚠ No exception channels found in this server.")


async def setup(bot):
    await bot.add_cog(Exceptions(bot))

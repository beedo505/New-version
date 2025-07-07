import discord
from discord.ext import commands
from db import collection, guilds_collection, settings_collection
import os

class Setup(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def set(self, ctx, role: discord.Role = None):
        guild_id = str(ctx.guild.id)
        guild = ctx.guild

        if role is None:
            await ctx.message.reply(
                "❌ You must mention a role or provide a valid role ID.")
            return

        server_data = guilds_collection.find_one({"guild_id": guild_id})
        current_role_id = server_data.get(
            "prisoner_role_id") if server_data else None
        exception_channels = server_data.get("exception_channels",
                                             []) if server_data else []

        if current_role_id == str(role.id):
            await ctx.message.reply(
                f"⚠️ The prisoner role is already set to: **{role.name}**.")
            return

        guilds_collection.update_one(
            {"guild_id": guild_id},
            {"$set": {
                "prisoner_role_id": str(role.id)
            }},
            upsert=True)

        for channel in guild.channels:
            if str(channel.id) not in exception_channels:
                await channel.set_permissions(role, view_channel=False)

        await ctx.message.reply(
            f"✅ The prisoner role has been set to: **{role.name}**.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def mod(self, ctx, channel: discord.TextChannel):
        server_data = settings_collection.find_one(
            {"guild_id": str(ctx.guild.id)})
        existing_channel_id = server_data.get(
            "mod_log_channel_id") if server_data else None

        if existing_channel_id and str(existing_channel_id) == str(channel.id):
            await ctx.message.reply(
                f"⚠️ The moderation log channel is already set to {channel.mention}."
            )
            return

        settings_collection.update_one(
            {"guild_id": str(ctx.guild.id)},
            {"$set": {
                "mod_log_channel_id": str(channel.id)
            }},
            upsert=True)
        await ctx.message.reply(
            f"✅ The moderation log channel has been set to {channel.mention}")


async def setup(bot):
    await bot.add_cog(Setup(bot))
    

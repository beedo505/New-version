import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import asyncio
from pymongo import MongoClient
import os

client = MongoClient(os.getenv("MONGODB_URI"))
db = client["Prison"]
collection = db["user"]
guilds_collection = db["guilds"]

class Jail(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=[# Define alternative names (aliases) for your commands here])
    @commands.has_permissions(administrator=True)
    async def jail(self, ctx, member: discord.Member = None, duration: str = None, *, reason: str = None):
        guild = ctx.guild
        server_data = guilds_collection.find_one({"guild_id": str(guild.id)})

        if member is None:
            await ctx.message.reply("❌ Please mention a member to jail.")
            return

        if not server_data:
            await ctx.message.reply("The bot is not properly set up for this server.")
            return

        prisoner_role_id = server_data.get('prisoner_role_id')
        if not prisoner_role_id:
            await ctx.message.reply("The 'Prisoner' role is not set.")
            return

        prisoner_role = ctx.guild.get_role(int(prisoner_role_id))
        if not prisoner_role:
            await ctx.message.reply("The 'Prisoner' role no longer exists.")
            return

        if prisoner_role in member.roles:
            await ctx.message.reply(f"❌ | {member.mention} is already in prison.")
            return

        if member == ctx.author:
            await ctx.message.reply("You cannot jail yourself.")
            return

        if member.top_role >= ctx.guild.me.top_role:
            await ctx.message.reply("I cannot jail this member because their role is equal to or higher than mine.")
            return

        if duration is None:
            duration = "8h"
        if reason is None:
            reason = "No reason provided"

        time_units = {"m": "minutes", "h": "hours", "d": "days", "o": "days"}

        if duration[-1] in time_units:
            try:
                time_value = int(duration[:-1])
            except ValueError:
                await ctx.message.reply("Invalid duration. Use numbers followed by m, h, d, or o.")
                return
        else:
            await ctx.message.reply("Invalid duration format. Use m, h, d, or o.")
            return

        delta = timedelta(days=time_value * 30) if duration[-1] == "o" else timedelta(**{time_units[duration[-1]]: time_value})
        saudi_tz = ZoneInfo("Asia/Riyadh")
        release_time = datetime.now(saudi_tz) + delta

        previous_roles = [role.id for role in member.roles if role != guild.default_role and not role.is_premium_subscriber()]

        await member.edit(roles=[prisoner_role])

        collection.update_one(
            {"user_id": member.id, "guild_id": ctx.guild.id, "channel_id": ctx.channel.id},
            {"$set": {
                "roles": previous_roles,
                "release_time": release_time.astimezone(timezone.utc).isoformat()
            }},
            upsert=True
        )

        embed = discord.Embed(
            title="**تم السجن بنجاح**",
            description=(
                f"الشخص: {member.mention}\n"
                f"المدة: {duration}\n"
                f"السبب: {reason}"
            ),
            color=0x2f3136
        )
        embed.set_footer(text=f"Action by: {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        embed.timestamp = datetime.utcnow()

        await ctx.message.reply(embed=embed)
        await asyncio.sleep(delta.total_seconds())
        await self.release_member(ctx, member)

    async def release_member(self, ctx, member):
        guild = member.guild
        server_data = guilds_collection.find_one({"guild_id": str(guild.id)})
        if not server_data:
            return

        prisoner_role_id = server_data.get('prisoner_role_id')
        if not prisoner_role_id:
            return

        prisoner_role = guild.get_role(int(prisoner_role_id))
        data = collection.find_one({"user_id": member.id, "guild_id": guild.id})

        if not data:
            return

        if prisoner_role and prisoner_role in member.roles:
            await member.remove_roles(prisoner_role)

        previous_roles = [guild.get_role(role_id) for role_id in data.get("roles", []) if guild.get_role(role_id)]
        if previous_roles:
            await member.edit(roles=previous_roles)
        else:
            await member.edit(roles=[guild.default_role])

        collection.delete_one({"user_id": member.id, "guild_id": guild.id})

        if ctx:
            await ctx.send(f"{member.mention} has been released from jail.")

async def setup(bot):
    await bot.add_cog(Jail(bot))

import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import asyncio
from db import collection, guilds_collection, settings_collection
import os

class Jail(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=[
        # ✨ Add your own aliases here
        # Example: "حبس", "احبس",
    ])
    @commands.has_permissions(administrator=True)
    async def سجن(self, ctx, member: discord.Member = None, duration: str = None, *, reason: str = None):
        guild = ctx.guild
        server_data = guilds_collection.find_one({"guild_id": str(guild.id)})

        if member is None:
            embed = discord.Embed(title="📝 أمر السجن", color=0x2f3136)
            usage_lines = [
                "•  الأمر        :  -سجن \n",
                "•  الوظيفة        :  سجن العضو \n"
            ]
            aliases_lines = ["•  -حبس \n", "•  -احبس \n", "•  -اشخط \n", "•  -ارمي \n", "•  -عدس \n", "•  -كوي \n"]
            embed.add_field(name="📌 معلومات الأمر", value=f"{''.join(usage_lines)}", inline=False)
            embed.add_field(name="💡 الاختصارات المتاحة", value=f"{''.join(aliases_lines)}", inline=False)
            await ctx.message.reply(embed=embed)
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

    async def release_member(self, ctx, member: discord.Member, silent=False):
        guild = member.guild if ctx is None else ctx.guild
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
        await member.edit(roles=previous_roles if previous_roles else [guild.default_role])
        collection.delete_one({"user_id": member.id, "guild_id": guild.id})
        if not silent and ctx:
            await ctx.send(f"{member.mention} has been released from jail.")

    @commands.command()
    async def كم(self, ctx):
        member = ctx.author
        data = collection.find_one({"user_id": member.id, "guild_id": ctx.guild.id})
        if not data or "release_time" not in data:
            await ctx.reply("❌ | You are not currently in jail.", delete_after=5)
            await ctx.message.delete(delay=5)
            return
        release_time = data["release_time"]
        if isinstance(release_time, str):
            release_time = datetime.fromisoformat(release_time).replace(tzinfo=timezone.utc)
        saudi_tz = ZoneInfo("Asia/Riyadh")
        release_time = release_time.astimezone(saudi_tz)
        now = datetime.now(saudi_tz)
        remaining = release_time - now
        if remaining.total_seconds() <= 0:
            await ctx.reply("✅ | Your jail time has expired, you should be released soon!", delete_after=5)
        else:
            hours, remainder = divmod(int(remaining.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            release_time_str = release_time.strftime("%I:%M %p")
            await ctx.reply(f"⏳ | Remaining jail time: `{hours}h {minutes}m {seconds}s`\n⏰ | Release time (Saudi): `{release_time_str}`", delete_after=5)
        await ctx.message.delete(delay=5)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def سجين(self, ctx):
        guild = ctx.guild
        prisoners_data = collection.find({"guild_id": guild.id})
        embed = discord.Embed(title="🔒 Currently Jailed Members", color=0x2f3136)
        saudi_tz = ZoneInfo("Asia/Riyadh")
        now = datetime.now(saudi_tz)
        jailed_list = []
        for prisoner in prisoners_data:
            member = guild.get_member(prisoner["user_id"])
            release_time = prisoner.get("release_time")
            if isinstance(release_time, str):
                release_time = datetime.fromisoformat(release_time)
            release_time = release_time.replace(tzinfo=timezone.utc).astimezone(saudi_tz)
            remaining = release_time - now
            if remaining.total_seconds() > 0:
                hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
                remaining_str = f"{hours}h {minutes}m remaining"
            else:
                remaining_str = "Time's up (release pending)"
            release_time_str = release_time.strftime("%Y-%m-%d %I:%M %p Saudi")
            if member:
                jailed_list.append(f"-{member.mention} — 📆 Release: {release_time_str} | ⏳ {remaining_str}")
        embed.description = "\n".join(jailed_list) if jailed_list else "There are no members currently jailed."
        await ctx.message.reply(embed=embed, delete_after=5)
        await ctx.message.delete(delay=5)

    @commands.command(aliases=[
        # ✨ Add your own aliases here
        # Example: "حبس", "احبس",
    ])
    @commands.has_permissions(administrator=True)
    async def عفو(self, ctx, *, member: str = None):
        guild = ctx.guild
        server_data = guilds_collection.find_one({"guild_id": str(guild.id)})
        if member is None or member.lower() in ['الكل', 'الجميع', 'all']:
            prisoners_data = collection.find({"guild_id": ctx.guild.id})
            pardoned_members = []
            for prisoner in prisoners_data:
                member_obj = ctx.guild.get_member(prisoner["user_id"])
                if member_obj:
                    await self.release_member(ctx, member_obj, silent=True)
                    pardoned_members.append(member_obj)
            if pardoned_members:
                mentions = ", ".join(member.mention for member in pardoned_members)
                await ctx.message.reply(f"✅ {len(pardoned_members)} prisoner(s) have been pardoned:\n{mentions}")
            else:
                await ctx.message.reply("⚠️ No prisoners found to pardon.")
            return
        if not server_data or "prisoner_role_id" not in server_data:
            await ctx.message.reply("⚠️ The 'Prisoner' role is not set up.")
            return
        prisoner_role = guild.get_role(int(server_data["prisoner_role_id"]))
        member_id = None
        if member.startswith("<@") and member.endswith(">"):
            member_id = member.replace("<@", "").replace("!", "").replace(">", "")
        elif member.isdigit():
            member_id = member
        else:
            target = discord.utils.find(lambda m: m.name == member or m.display_name == member, guild.members)
            if target:
                member = target
            else:
                await ctx.reply("❌ | Invalid member input.")
                return
        if member_id:
            member = guild.get_member(int(member_id))
            if not member:
                await ctx.reply("❌ | Member not found.")
                return
        if member == ctx.author:
            await ctx.message.reply("❌ You cannot pardon yourself!")
            return
        if member.top_role >= ctx.guild.me.top_role:
            await ctx.message.reply("❌ I cannot pardon this member because their role is equal to or higher than mine.")
            return
        data = collection.find_one({"user_id": member.id, "guild_id": guild.id})
        if not data:
            if prisoner_role in member.roles:
                await ctx.message.reply(f"⚠️ {member.mention} has the prisoner role but not in the DB! Fixing...")
                collection.insert_one({"user_id": member.id, "guild_id": guild.id, "roles": []})
            else:
                await ctx.message.reply(f"❌ {member.mention} is not in jail.")
                return
        if prisoner_role in member.roles:
            await member.remove_roles(prisoner_role)
        previous_roles = [guild.get_role(role_id) for role_id in (data.get("roles") or []) if guild.get_role(role_id)]
        await member.edit(roles=previous_roles if previous_roles else [guild.default_role])
        collection.delete_one({"user_id": member.id, "guild_id": guild.id})
        await ctx.message.reply(f"✅ {member.mention} has been pardoned!")

async def setup(bot):
    await bot.add_cog(Jail(bot))

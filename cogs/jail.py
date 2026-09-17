import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from db import collection, guilds_collection


class Jail(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.release_lock = asyncio.Lock()

        # Start the background task that releases expired jails.
        self.release_expired_jails.start()

    def cog_unload(self):
        self.release_expired_jails.cancel()

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def parse_release_time(value):
        """
        Convert a stored release_time into an aware UTC datetime.
        """
        if isinstance(value, datetime):
            release_time = value
        elif isinstance(value, str):
            release_time = datetime.fromisoformat(value)
        else:
            return None

        if release_time.tzinfo is None:
            release_time = release_time.replace(
                tzinfo=timezone.utc
            )

        return release_time.astimezone(timezone.utc)

    @staticmethod
    def format_remaining(seconds):
        """
        Convert seconds into a readable jail duration.
        """
        seconds = max(0, int(seconds))

        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        return f"{hours}h {minutes}m {seconds}s"

    def get_prisoner_role(self, guild, server_data):
        """
        Get the configured Prisoner role.
        """
        prisoner_role_id = server_data.get("prisoner_role_id")

        if not prisoner_role_id:
            return None

        return guild.get_role(int(prisoner_role_id))

    # =========================================================
    # Background Jail Release System
    # =========================================================

    @tasks.loop(seconds=30)
    async def release_expired_jails(self):
        """
        Periodically check MongoDB for expired jail records
        and release the corresponding members.
        """

        now = datetime.now(timezone.utc)

        prisoners = collection.find(
            {},
            {
                "_id": 0,
                "user_id": 1,
                "guild_id": 1,
                "release_time": 1,
                "roles": 1,
            }
        )

        for prisoner in prisoners:
            release_time = self.parse_release_time(
                prisoner.get("release_time")
            )

            if release_time is None:
                continue

            if release_time > now:
                continue

            guild_id = prisoner.get("guild_id")
            user_id = prisoner.get("user_id")

            if guild_id is None or user_id is None:
                continue

            guild = self.bot.get_guild(int(guild_id))

            if not guild:
                continue

            member = guild.get_member(int(user_id))

            if not member:
                continue

            await self.release_member(
                member,
                silent=True,
                expected_release_time=release_time
            )

    @release_expired_jails.before_loop
    async def before_release_expired_jails(self):
        await self.bot.wait_until_ready()

    # =========================================================
    # Jail Command
    # =========================================================

    @commands.command(
        aliases=[
            # Add your custom aliases here.
            # Example:
            # "حبس",
            # "احبس",
            # "اشخط",
            # "ارمي",
            # "عدس",
            # "كوي",
        ]
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def سجن(
        self,
        ctx,
        member: discord.Member = None,
        duration: str = None,
        *,
        reason: str = None
    ):
        guild = ctx.guild

        # -----------------------------------------------------
        # Show command information
        # -----------------------------------------------------

        if member is None:
            aliases = [
                f"`-{alias}`"
                for alias in ctx.command.aliases
            ]

            aliases_text = (
                " • ".join(aliases)
                if aliases
                else "لا توجد اختصارات مضافة حاليًا."
            )

            embed = discord.Embed(
                title="📝 أمر السجن",
                color=0x2F3136
            )

            embed.add_field(
                name="📌 معلومات الأمر",
                value=(
                    "• الأمر: `-سجن @username 8h`\n"
                    "• الوظيفة: سجن العضو لمدة محددة"
                ),
                inline=False
            )

            embed.add_field(
                name="💡 مثال",
                value="`-سجن @username 2h spam`",
                inline=False
            )

            embed.add_field(
                name="🔗 الاختصارات",
                value=aliases_text,
                inline=False
            )

            await ctx.message.reply(embed=embed)
            return

        # -----------------------------------------------------
        # Server setup
        # -----------------------------------------------------

        server_data = guilds_collection.find_one(
            {"guild_id": str(guild.id)}
        )

        if not server_data:
            await ctx.message.reply(
                "❌ The bot is not properly set up for this server."
            )
            return

        prisoner_role = self.get_prisoner_role(
            guild,
            server_data
        )

        if not prisoner_role:
            await ctx.message.reply(
                "❌ The 'Prisoner' role is not set or no longer exists."
            )
            return

        # -----------------------------------------------------
        # Basic validation
        # -----------------------------------------------------

        if member.id == ctx.author.id:
            await ctx.message.reply(
                "❌ You cannot jail yourself."
            )
            return

        if member.bot:
            await ctx.message.reply(
                "❌ You cannot jail a bot."
            )
            return

        if prisoner_role in member.roles:
            await ctx.message.reply(
                f"❌ | {member.mention} is already in prison."
            )
            return

        if member.top_role >= guild.me.top_role:
            await ctx.message.reply(
                "❌ I cannot jail this member because "
                "their role is equal to or higher than mine."
            )
            return

        # -----------------------------------------------------
        # Default values
        # -----------------------------------------------------

        if duration is None:
            duration = "8h"

        if reason is None:
            reason = "No reason provided"

        # -----------------------------------------------------
        # Parse duration
        # -----------------------------------------------------

        time_units = {
            "m": "minutes",
            "h": "hours",
            "d": "days",
            "o": "days",
        }

        duration = duration.strip().lower()

        if len(duration) < 2:
            await ctx.message.reply(
                "❌ Invalid duration. "
                "Use numbers followed by m, h, d, or o."
            )
            return

        unit = duration[-1]
        value_text = duration[:-1]

        if unit not in time_units:
            await ctx.message.reply(
                "❌ Invalid duration format. "
                "Use m, h, d, or o."
            )
            return

        try:
            time_value = int(value_text)
        except ValueError:
            await ctx.message.reply(
                "❌ Invalid duration. "
                "Use numbers followed by m, h, d, or o."
            )
            return

        if time_value <= 0:
            await ctx.message.reply(
                "❌ Jail duration must be greater than zero."
            )
            return

        # "o" = month (30 days)
        if unit == "o":
            delta = timedelta(
                days=time_value * 30
            )
        else:
            delta = timedelta(
                **{
                    time_units[unit]: time_value
                }
            )

        # -----------------------------------------------------
        # Calculate release time
        # -----------------------------------------------------

        now_utc = datetime.now(timezone.utc)

        release_time = now_utc + delta

        # -----------------------------------------------------
        # Prevent simultaneous jail/release operations
        # -----------------------------------------------------

        async with self.release_lock:

            # Save the member's previous roles.
            previous_roles = [
                role.id
                for role in member.roles
                if (
                    role != guild.default_role
                    and not role.is_premium_subscriber()
                    and not role.managed
                )
            ]

            # Give only the Prisoner role.
            await member.edit(
                roles=[prisoner_role]
            )

            # Save jail information.
            collection.update_one(
                {
                    "user_id": member.id,
                    "guild_id": guild.id,
                },
                {
                    "$set": {
                        "roles": previous_roles,
                        "release_time": release_time.isoformat(),
                        "channel_id": ctx.channel.id,
                    }
                },
                upsert=True
            )

        # -----------------------------------------------------
        # Success message
        # -----------------------------------------------------

        embed = discord.Embed(
            title="تم السجن بنجاح",
            description=(
                f"الشخص: {member.mention}\n"
                f"المدة: {duration}\n"
                f"السبب: {reason}"
            ),
            color=0x2F3136
        )

        embed.set_footer(
            text=f"Action by: {ctx.author}",
            icon_url=(
                ctx.author.avatar.url
                if ctx.author.avatar
                else None
            )
        )

        embed.timestamp = datetime.now(timezone.utc)

        await ctx.message.reply(
            embed=embed
        )

        # IMPORTANT:
        # There is intentionally NO asyncio.sleep() here.
        #
        # The background release task checks MongoDB every
        # 30 seconds, so jail survives bot/Railway restarts.

    # =========================================================
    # Release Member
    # =========================================================

    async def release_member(
        self,
        member,
        silent=False,
        expected_release_time=None
    ):
        guild = member.guild

        async with self.release_lock:

            # -------------------------------------------------
            # Get server configuration
            # -------------------------------------------------

            server_data = guilds_collection.find_one(
                {"guild_id": str(guild.id)}
            )

            if not server_data:
                return False

            prisoner_role = self.get_prisoner_role(
                guild,
                server_data
            )

            if not prisoner_role:
                return False

            # -------------------------------------------------
            # Get jail data
            # -------------------------------------------------

            data = collection.find_one(
                {
                    "user_id": member.id,
                    "guild_id": guild.id,
                }
            )

            if not data:
                return False

            current_release_time = self.parse_release_time(
                data.get("release_time")
            )

            if current_release_time is None:
                return False

            # -------------------------------------------------
            # Critical protection:
            #
            # If an old release operation is trying to release
            # a member, make sure it still matches the current
            # jail record.
            # -------------------------------------------------

            if expected_release_time is not None:
                if current_release_time != expected_release_time:
                    return False

            # -------------------------------------------------
            # Make sure the jail has actually expired
            # -------------------------------------------------

            now_utc = datetime.now(timezone.utc)

            if current_release_time > now_utc:
                return False

            # -------------------------------------------------
            # Restore previous roles
            # -------------------------------------------------

            previous_roles = []

            for role_id in data.get("roles", []):
                role = guild.get_role(int(role_id))

                if role and not role.managed:
                    previous_roles.append(role)

            # Remove Prisoner role if present.
            if prisoner_role in member.roles:
                await member.remove_roles(
                    prisoner_role
                )

            # Restore previous roles.
            await member.edit(
                roles=previous_roles
            )

            # Delete jail record only after the member's
            # roles have been successfully restored.
            collection.delete_one(
                {
                    "user_id": member.id,
                    "guild_id": guild.id,
                    "release_time": data["release_time"],
                }
            )

        # -----------------------------------------------------
        # Optional release message
        # -----------------------------------------------------

        if not silent:
            try:
                await member.send(
                    "✅ You have been released from jail."
                )
            except discord.HTTPException:
                pass

        return True

    # =========================================================
    # Remaining Jail Time
    # =========================================================

    @commands.command()
    @commands.guild_only()
    async def كم(self, ctx):

        member = ctx.author

        data = collection.find_one(
            {
                "user_id": member.id,
                "guild_id": ctx.guild.id,
            }
        )

        if not data or "release_time" not in data:
            await ctx.reply(
                "❌ | You are not currently in jail.",
                delete_after=5
            )

            try:
                await ctx.message.delete(
                    delay=5
                )
            except discord.HTTPException:
                pass

            return

        release_time = self.parse_release_time(
            data["release_time"]
        )

        if release_time is None:
            await ctx.reply(
                "❌ | Your jail record is invalid.",
                delete_after=5
            )
            return

        now_utc = datetime.now(timezone.utc)

        remaining = (
            release_time - now_utc
        )

        if remaining.total_seconds() <= 0:

            await ctx.reply(
                "✅ | Your jail time has expired. "
                "You should be released soon!",
                delete_after=5
            )

        else:
            saudi_tz = ZoneInfo(
                "Asia/Riyadh"
            )

            release_time_saudi = (
                release_time.astimezone(saudi_tz)
            )

            remaining_text = self.format_remaining(
                remaining.total_seconds()
            )

            release_time_str = (
                release_time_saudi.strftime(
                    "%I:%M %p"
                )
            )

            await ctx.reply(
                f"⏳ | Remaining jail time: "
                f"`{remaining_text}`\n"
                f"⏰ | Release time (Saudi): "
                f"`{release_time_str}`",
                delete_after=5
            )

        try:
            await ctx.message.delete(
                delay=5
            )
        except discord.HTTPException:
            pass

    # =========================================================
    # Currently Jailed Members
    # =========================================================

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def سجين(self, ctx):

        guild = ctx.guild

        prisoners_data = collection.find(
            {
                "guild_id": guild.id
            }
        )

        saudi_tz = ZoneInfo(
            "Asia/Riyadh"
        )

        now_utc = datetime.now(
            timezone.utc
        )

        jailed_list = []

        for prisoner in prisoners_data:

            member = guild.get_member(
                prisoner["user_id"]
            )

            release_time = self.parse_release_time(
                prisoner.get("release_time")
            )

            if release_time is None:
                continue

            remaining = (
                release_time - now_utc
            )

            if remaining.total_seconds() > 0:
                remaining_text = (
                    self.format_remaining(
                        remaining.total_seconds()
                    )
                    + " remaining"
                )
            else:
                remaining_text = (
                    "Time's up (release pending)"
                )

            release_time_str = (
                release_time
                .astimezone(saudi_tz)
                .strftime(
                    "%Y-%m-%d %I:%M %p Saudi"
                )
            )

            if member:
                jailed_list.append(
                    f"- {member.mention} — "
                    f"📆 Release: {release_time_str} | "
                    f"⏳ {remaining_text}"
                )

        embed = discord.Embed(
            title="🔒 Currently Jailed Members",
            color=0x2F3136
        )

        embed.description = (
            "\n".join(jailed_list)
            if jailed_list
            else "There are no members currently jailed."
        )

        await ctx.message.reply(
            embed=embed,
            delete_after=5
        )

        try:
            await ctx.message.delete(
                delay=5
            )
        except discord.HTTPException:
            pass

    # =========================================================
    # Pardon
    # =========================================================

    @commands.command(
        aliases=[
            # Add your custom aliases here.
            # Example:
            # "حبس",
            # "احبس",
        ]
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def عفو(
        self,
        ctx,
        *,
        member: str = None
    ):

        guild = ctx.guild

        server_data = guilds_collection.find_one(
            {
                "guild_id": str(guild.id)
            }
        )

        if not server_data:
            await ctx.message.reply(
                "⚠️ The server is not properly configured."
            )
            return

        prisoner_role = self.get_prisoner_role(
            guild,
            server_data
        )

        if not prisoner_role:
            await ctx.message.reply(
                "⚠️ The 'Prisoner' role is not set up."
            )
            return

        # =====================================================
        # Pardon Everyone
        # =====================================================

        if (
            member is None
            or member.lower() in [
                "الكل",
                "الجميع",
                "all"
            ]
        ):

            prisoners_data = collection.find(
                {
                    "guild_id": guild.id
                }
            )

            pardoned_members = []

            for prisoner in prisoners_data:

                member_obj = guild.get_member(
                    prisoner["user_id"]
                )

                if not member_obj:
                    continue

                released = await self.release_member(
                    member_obj,
                    silent=True
                )

                if released:
                    pardoned_members.append(
                        member_obj
                    )

            if pardoned_members:

                mentions = ", ".join(
                    member.mention
                    for member in pardoned_members
                )

                await ctx.message.reply(
                    f"✅ {len(pardoned_members)} "
                    f"prisoner(s) have been pardoned:\n"
                    f"{mentions}"
                )

            else:
                await ctx.message.reply(
                    "⚠️ No prisoners found to pardon."
                )

            return

        # =====================================================
        # Find Target Member
        # =====================================================

        member_id = None

        if (
            member.startswith("<@")
            and member.endswith(">")
        ):
            member_id = (
                member
                .replace("<@", "")
                .replace("!", "")
                .replace(">", "")
            )

        elif member.isdigit():
            member_id = member

        else:
            target = discord.utils.find(
                lambda m:
                    m.name == member
                    or m.display_name == member,
                guild.members
            )

            if target:
                member = target

            else:
                await ctx.reply(
                    "❌ | Invalid member input."
                )
                return

        # =====================================================
        # Convert ID to Member
        # =====================================================

        if member_id:

            member_obj = guild.get_member(
                int(member_id)
            )

            if not member_obj:
                await ctx.reply(
                    "❌ | Member not found."
                )
                return

            member = member_obj

        # =====================================================
        # Basic Validation
        # =====================================================

        if member.id == ctx.author.id:
            await ctx.message.reply(
                "❌ You cannot pardon yourself!"
            )
            return

        if member.top_role >= guild.me.top_role:
            await ctx.message.reply(
                "❌ I cannot pardon this member because "
                "their role is equal to or higher than mine."
            )
            return

        # =====================================================
        # Check Jail Record
        # =====================================================

        data = collection.find_one(
            {
                "user_id": member.id,
                "guild_id": guild.id,
            }
        )

        if not data:

            if prisoner_role in member.roles:

                await ctx.message.reply(
                    f"⚠️ {member.mention} has the prisoner role "
                    "but not in the DB! Fixing..."
                )

                # Remove prisoner role and leave all other
                # existing roles untouched.
                await member.remove_roles(
                    prisoner_role
                )

            else:
                await ctx.message.reply(
                    f"❌ {member.mention} is not in jail."
                )

            return

        # =====================================================
        # Pardon
        # =====================================================

        released = await self.release_member(
            member,
            silent=True,
            expected_release_time=None
        )

        if not released:
            await ctx.message.reply(
                "❌ Failed to pardon this member."
            )
            return

        await ctx.message.reply(
            f"✅ {member.mention} has been pardoned!"
        )


# =============================================================
# Extension Setup
# =============================================================

async def setup(bot):
    await bot.add_cog(Jail(bot))

import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from db import collection, guilds_collection


# =========================================================
# MongoDB helpers
# =========================================================

async def db_find_one(coll, query, projection=None):
    return await asyncio.to_thread(
        coll.find_one,
        query,
        projection
    )


async def db_find_many(coll, query, projection=None):
    return await asyncio.to_thread(
        lambda: list(coll.find(query, projection))
    )


async def db_update_one(coll, query, update, upsert=False):
    return await asyncio.to_thread(
        coll.update_one,
        query,
        update,
        upsert=upsert
    )


async def db_delete_one(coll, query):
    return await asyncio.to_thread(
        coll.delete_one,
        query
    )


# =========================================================
# Jail Cog
# =========================================================

class Jail(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.release_lock = asyncio.Lock()

        # Automatically release expired prisoners.
        self.release_expired_jails.start()

    def cog_unload(self):
        self.release_expired_jails.cancel()

    # =====================================================
    # Helpers
    # =====================================================

    @staticmethod
    def parse_release_time(value):
        """Convert a stored release_time into UTC datetime."""

        if isinstance(value, datetime):
            release_time = value

        elif isinstance(value, str):
            try:
                release_time = datetime.fromisoformat(value)
            except ValueError:
                return None

        else:
            return None

        if release_time.tzinfo is None:
            release_time = release_time.replace(
                tzinfo=timezone.utc
            )

        return release_time.astimezone(timezone.utc)

    @staticmethod
    def format_remaining(seconds):
        """Convert seconds into a readable duration."""

        seconds = max(0, int(seconds))

        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        return f"{hours}h {minutes}m {seconds}s"

    @staticmethod
    def get_prisoner_role(guild, server_data):
        """Get the configured Prisoner role safely."""

        prisoner_role_id = server_data.get("prisoner_role_id")

        if not prisoner_role_id:
            return None

        try:
            return guild.get_role(int(prisoner_role_id))
        except (TypeError, ValueError):
            return None

    # =====================================================
    # Background automatic release
    # =====================================================

    @tasks.loop(seconds=30)
    async def release_expired_jails(self):
        """Release prisoners whose jail time has expired."""

        now = datetime.now(timezone.utc)

        try:
            prisoners = await db_find_many(
                collection,
                {},
                {
                    "_id": 0,
                    "user_id": 1,
                    "guild_id": 1,
                    "release_time": 1,
                }
            )
        except Exception as e:
            print(
                f"❌ Failed to read jail records: {e}"
            )
            return

        for prisoner in prisoners:
            try:
                release_time = self.parse_release_time(
                    prisoner.get("release_time")
                )

                # Ignore invalid records.
                if release_time is None:
                    continue

                # Jail has not expired yet.
                if release_time > now:
                    continue

                guild_id = prisoner.get("guild_id")
                user_id = prisoner.get("user_id")

                if guild_id is None or user_id is None:
                    continue

                guild = self.bot.get_guild(
                    int(guild_id)
                )

                if guild is None:
                    continue

                # Try cache first.
                member = guild.get_member(
                    int(user_id)
                )

                # If not cached, fetch from Discord.
                if member is None:
                    try:
                        member = await guild.fetch_member(
                            int(user_id)
                        )
                    except (
                        discord.NotFound,
                        discord.HTTPException
                    ):
                        # Keep the DB record.
                        # The member may become available later.
                        continue

                await self.release_member(
                    member,
                    silent=True,
                    expected_release_time=release_time
                )

            except Exception as e:
                # One broken record must never stop the
                # entire background release system.
                print(
                    f"❌ Failed to process jail record: {e}"
                )

    @release_expired_jails.before_loop
    async def before_release_expired_jails(self):
        await self.bot.wait_until_ready()

    # =====================================================
    # Jail command
    # =====================================================

    @commands.command(
        aliases=[
            # Add your custom aliases here.
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

        # -------------------------------------------------
        # Command help
        # -------------------------------------------------

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

            await ctx.message.reply(
                embed=embed
            )
            return

        # -------------------------------------------------
        # Server configuration
        # -------------------------------------------------

        server_data = await db_find_one(
            guilds_collection,
            {
                "guild_id": str(guild.id)
            }
        )

        if not server_data:
            await ctx.message.reply(
                "⚠️ The Prisoner role has not been configured yet.\n"
                "Use `-set @Prisoner` first."
            )
            return

        prisoner_role = self.get_prisoner_role(
            guild,
            server_data
        )

        if not prisoner_role:
            await ctx.message.reply(
                "⚠️ The configured Prisoner role no longer exists.\n"
                "Please configure a new role using "
                "`-set @Prisoner`."
            )
            return

        # -------------------------------------------------
        # Bot member / role hierarchy
        # -------------------------------------------------

        bot_member = guild.me

        if bot_member is None:
            await ctx.message.reply(
                "❌ I could not get my member information."
            )
            return

        if prisoner_role >= bot_member.top_role:
            await ctx.message.reply(
                "❌ I cannot assign the Prisoner role because "
                "it is equal to or higher than my highest role."
            )
            return

        if not bot_member.guild_permissions.manage_roles:
            await ctx.message.reply(
                "❌ I need the **Manage Roles** permission "
                "to jail members."
            )
            return

        # -------------------------------------------------
        # Basic validation
        # -------------------------------------------------

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

        if member.top_role >= bot_member.top_role:
            await ctx.message.reply(
                "❌ I cannot jail this member because "
                "their role is equal to or higher than mine."
            )
            return

        # -------------------------------------------------
        # Default values
        # -------------------------------------------------

        if duration is None:
            duration = "8h"

        if reason is None:
            reason = "No reason provided"

        # -------------------------------------------------
        # Parse duration
        # -------------------------------------------------

        duration = duration.strip().lower()

        time_units = {
            "m": "minutes",
            "h": "hours",
            "d": "days",
        }

        # "o" means 30 days.
        if duration.endswith("o"):
            unit = "o"
            value_text = duration[:-1]
        else:
            unit = duration[-1] if duration else ""
            value_text = duration[:-1]

        if unit not in time_units and unit != "o":
            await ctx.message.reply(
                "❌ Invalid duration format.\n"
                "Use numbers followed by m, h, d, or o."
            )
            return

        try:
            time_value = int(value_text)
        except ValueError:
            await ctx.message.reply(
                "❌ Invalid duration.\n"
                "Use numbers followed by m, h, d, or o."
            )
            return

        if time_value <= 0:
            await ctx.message.reply(
                "❌ Jail duration must be greater than zero."
            )
            return

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

        # -------------------------------------------------
        # Calculate release time
        # -------------------------------------------------

        now_utc = datetime.now(timezone.utc)
        release_time = now_utc + delta

        # -------------------------------------------------
        # Jail operation lock
        # -------------------------------------------------

        async with self.release_lock:

            # Save previous roles.
            previous_roles = [
                role.id
                for role in member.roles
                if (
                    role != guild.default_role
                    and not role.is_premium_subscriber()
                    and not role.managed
                )
            ]

            # -------------------------------------------------
            # Save DB record FIRST.
            #
            # If Discord fails afterward, we delete the
            # record again.
            # -------------------------------------------------

            try:
                await db_update_one(
                    collection,
                    {
                        "user_id": member.id,
                        "guild_id": guild.id
                    },
                    {
                        "$set": {
                            "roles": previous_roles,
                            "release_time": (
                                release_time.isoformat()
                            ),
                            "channel_id": ctx.channel.id,
                        }
                    },
                    upsert=True
                )

            except Exception as e:
                await ctx.message.reply(
                    f"❌ Failed to save the jail record: `{e}`"
                )
                return

            # -------------------------------------------------
            # Give only the Prisoner role.
            # -------------------------------------------------

            try:
                await member.edit(
                    roles=[prisoner_role]
                )

            except discord.Forbidden:
                await db_delete_one(
                    collection,
                    {
                        "user_id": member.id,
                        "guild_id": guild.id,
                        "release_time": (
                            release_time.isoformat()
                        )
                    }
                )

                await ctx.message.reply(
                    "❌ I don't have permission to change "
                    "this member's roles."
                )
                return

            except discord.HTTPException as e:
                await db_delete_one(
                    collection,
                    {
                        "user_id": member.id,
                        "guild_id": guild.id,
                        "release_time": (
                            release_time.isoformat()
                        )
                    }
                )

                await ctx.message.reply(
                    f"❌ Discord returned an error while "
                    f"jailing the member: `{e}`"
                )
                return

        # -------------------------------------------------
        # Success message
        # -------------------------------------------------

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

        embed.timestamp = datetime.now(
            timezone.utc
        )

        await ctx.message.reply(
            embed=embed
        )

    # =====================================================
    # Release member
    # =====================================================

    async def release_member(
        self,
        member,
        silent=False,
        expected_release_time=None,
        force=False
    ):
        guild = member.guild

        async with self.release_lock:

            # -------------------------------------------------
            # Server configuration
            # -------------------------------------------------

            server_data = await db_find_one(
                guilds_collection,
                {
                    "guild_id": str(guild.id)
                }
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
            # Get jail record
            # -------------------------------------------------

            data = await db_find_one(
                collection,
                {
                    "user_id": member.id,
                    "guild_id": guild.id
                }
            )

            if not data:
                return False

            current_release_time = (
                self.parse_release_time(
                    data.get("release_time")
                )
            )

            if current_release_time is None:
                return False

            # -------------------------------------------------
            # Prevent an old background operation from
            # releasing a newer jail record.
            # -------------------------------------------------

            if expected_release_time is not None:
                if current_release_time != expected_release_time:
                    return False

            # -------------------------------------------------
            # Normal automatic release cannot happen early.
            #
            # force=True is used by -عفو.
            # -------------------------------------------------

            now_utc = datetime.now(
                timezone.utc
            )

            if (
                not force
                and current_release_time > now_utc
            ):
                return False

            # -------------------------------------------------
            # Restore previous roles
            # -------------------------------------------------

            previous_roles = []

            for role_id in data.get(
                "roles",
                []
            ):
                try:
                    role = guild.get_role(
                        int(role_id)
                    )
                except (TypeError, ValueError):
                    continue

                if (
                    role
                    and role != guild.default_role
                    and not role.managed
                ):
                    previous_roles.append(role)

            # -------------------------------------------------
            # Restore roles in ONE Discord operation.
            #
            # This removes Prisoner automatically because
            # Prisoner is not included in previous_roles.
            # -------------------------------------------------

            try:
                await member.edit(
                    roles=previous_roles
                )

            except discord.NotFound:
                return False

            except discord.Forbidden as e:
                print(
                    f"❌ Permission error releasing "
                    f"{member.id}: {e}"
                )
                return False

            except discord.HTTPException as e:
                print(
                    f"❌ Discord error releasing "
                    f"{member.id}: {e}"
                )
                return False

            # -------------------------------------------------
            # Delete DB record ONLY after Discord succeeds.
            # -------------------------------------------------

            try:
                await db_delete_one(
                    collection,
                    {
                        "user_id": member.id,
                        "guild_id": guild.id,
                        "release_time": data[
                            "release_time"
                        ]
                    }
                )

            except Exception as e:
                print(
                    f"❌ Failed to delete jail record "
                    f"for {member.id}: {e}"
                )

                # Member is already released.
                # Keep returning False so the DB issue is visible
                # in logs and the record can be retried.
                return False

        # -------------------------------------------------
        # Optional DM
        # -------------------------------------------------

        if not silent:
            try:
                await member.send(
                    "✅ You have been released from jail."
                )
            except discord.HTTPException:
                pass

        return True

    # =====================================================
    # Remaining jail time
    # =====================================================

    @commands.command()
    @commands.guild_only()
    async def كم(self, ctx):

        member = ctx.author

        data = await db_find_one(
            collection,
            {
                "user_id": member.id,
                "guild_id": ctx.guild.id
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

        now_utc = datetime.now(
            timezone.utc
        )

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
                release_time.astimezone(
                    saudi_tz
                )
            )

            remaining_text = (
                self.format_remaining(
                    remaining.total_seconds()
                )
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

    # =====================================================
    # List prisoners
    # =====================================================

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def سجين(self, ctx):

        guild = ctx.guild

        prisoners_data = await db_find_many(
            collection,
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

            try:
                member = guild.get_member(
                    int(prisoner["user_id"])
                )
            except (
                KeyError,
                TypeError,
                ValueError
            ):
                member = None

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

    # =====================================================
    # Pardon
    # =====================================================

    @commands.command(
        aliases=[
            # Add your custom aliases here.
            # "فك",
            # "اعفو",
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

        # -------------------------------------------------
        # Server configuration
        # -------------------------------------------------

        server_data = await db_find_one(
            guilds_collection,
            {
                "guild_id": str(guild.id)
            }
        )

        if not server_data:
            await ctx.message.reply(
                "⚠️ The Prisoner role has not been configured yet.\n"
                "Use `-set @Prisoner` first."
            )
            return

        prisoner_role = self.get_prisoner_role(
            guild,
            server_data
        )

        if not prisoner_role:
            await ctx.message.reply(
                "⚠️ The configured Prisoner role no longer exists.\n"
                "Please configure a new role using "
                "`-set @Prisoner`."
            )
            return

        # =================================================
        # Pardon everyone
        # =================================================

        if (
            member is None
            or member.lower() in [
                "الكل",
                "الجميع",
                "all"
            ]
        ):

            prisoners_data = await db_find_many(
                collection,
                {
                    "guild_id": guild.id
                }
            )

            pardoned_members = []

            for prisoner in prisoners_data:

                try:
                    user_id = int(
                        prisoner["user_id"]
                    )
                except (
                    KeyError,
                    TypeError,
                    ValueError
                ):
                    continue

                member_obj = guild.get_member(
                    user_id
                )

                if not member_obj:
                    try:
                        member_obj = (
                            await guild.fetch_member(
                                user_id
                            )
                        )
                    except (
                        discord.NotFound,
                        discord.HTTPException
                    ):
                        continue

                released = await self.release_member(
                    member_obj,
                    silent=True,
                    force=True
                )

                if released:
                    pardoned_members.append(
                        member_obj
                    )

            if pardoned_members:

                mentions = ", ".join(
                    member_obj.mention
                    for member_obj in pardoned_members
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

        # =================================================
        # Find target member
        # =================================================

        member_id = None

        # Mention
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

        # ID
        elif member.isdigit():
            member_id = member

        # Username / display name
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

        # =================================================
        # Convert ID to Member
        # =================================================

        if member_id:

            try:
                member_obj = guild.get_member(
                    int(member_id)
                )

                if not member_obj:
                    member_obj = (
                        await guild.fetch_member(
                            int(member_id)
                        )
                    )

            except (
                discord.NotFound,
                discord.HTTPException
            ):
                await ctx.reply(
                    "❌ | Member not found."
                )
                return

            member = member_obj

        # =================================================
        # Basic validation
        # =================================================

        bot_member = guild.me

        if bot_member is None:
            await ctx.message.reply(
                "❌ I could not get my member information."
            )
            return

        if member.id == ctx.author.id:
            await ctx.message.reply(
                "❌ You cannot pardon yourself!"
            )
            return

        if member.top_role >= bot_member.top_role:
            await ctx.message.reply(
                "❌ I cannot pardon this member because "
                "their role is equal to or higher than mine."
            )
            return

        # =================================================
        # Check jail record
        # =================================================

        data = await db_find_one(
            collection,
            {
                "user_id": member.id,
                "guild_id": guild.id
            }
        )

        # -------------------------------------------------
        # No DB record
        # -------------------------------------------------

        if not data:

            if prisoner_role in member.roles:

                await ctx.message.reply(
                    f"⚠️ {member.mention} has the prisoner role "
                    "but no jail record was found in the DB! "
                    "Fixing..."
                )

                try:
                    await member.remove_roles(
                        prisoner_role
                    )
                except discord.Forbidden:
                    await ctx.message.reply(
                        "❌ I don't have permission to remove "
                        "the Prisoner role."
                    )
                except discord.HTTPException as e:
                    await ctx.message.reply(
                        f"❌ Discord returned an error: `{e}`"
                    )

            else:
                await ctx.message.reply(
                    f"❌ {member.mention} is not in jail."
                )

            return

        # =================================================
        # Force pardon
        #
        # force=True allows -عفو to work before the
        # original release time.
        # =================================================

        released = await self.release_member(
            member,
            silent=True,
            expected_release_time=None,
            force=True
        )

        if not released:
            await ctx.message.reply(
                "❌ Failed to pardon this member."
            )
            return

        await ctx.message.reply(
            f"✅ {member.mention} has been pardoned!"
        )


# =========================================================
# Extension setup
# =========================================================

async def setup(bot):
    await bot.add_cog(Jail(bot))

import discord
from discord.ext import commands

from db import db


class ExceptionManager:
    def __init__(self, db):
        self.collection = db["guilds"]

    def get_exceptions(self, guild_id):
        server_data = self.collection.find_one(
            {"guild_id": str(guild_id)},
            {"exception_channels": 1}
        )

        return (
            server_data.get("exception_channels", [])
            if server_data
            else []
        )

    def add_exception(self, guild_id, channel_id):
        result = self.collection.update_one(
            {"guild_id": str(guild_id)},
            {
                "$addToSet": {
                    "exception_channels": str(channel_id)
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
            {"guild_id": str(guild_id)},
            {
                "$pull": {
                    "exception_channels": str(channel_id)
                }
            }
        )

        return result.modified_count > 0


class Exceptions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.manager = ExceptionManager(db)

    async def get_prisoner_role(self, guild):
        server_data = self.manager.collection.find_one(
            {"guild_id": str(guild.id)},
            {"prisoner_role_id": 1}
        )

        if not server_data:
            return None

        prisoner_role_id = server_data.get(
            "prisoner_role_id"
        )

        if not prisoner_role_id:
            return None

        try:
            return guild.get_role(
                int(prisoner_role_id)
            )
        except (TypeError, ValueError):
            return None

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def add(
        self,
        ctx,
        *,
        channel: discord.abc.GuildChannel = None
    ):
        guild = ctx.guild

        if channel is None:
            channel_to_add = ctx.channel
        else:
            channel_to_add = channel

        prisoner_role = await self.get_prisoner_role(
            guild
        )

        if prisoner_role is None:
            await ctx.message.reply(
                "⚠️ The Prisoner role has not been configured yet.\n"
                "Use `-set @Prisoner` first."
            )
            return

        if not guild.me.guild_permissions.manage_roles:
            await ctx.message.reply(
                "❌ I need the **Manage Roles** permission."
            )
            return

        if prisoner_role >= guild.me.top_role:
            await ctx.message.reply(
                "❌ I cannot modify the Prisoner role because "
                "it is equal to or higher than my highest role."
            )
            return

        exceptions = self.manager.get_exceptions(
            guild.id
        )

        if str(channel_to_add.id) in {
            str(channel_id)
            for channel_id in exceptions
        }:
            await ctx.message.reply(
                f"⚠️ {channel_to_add.mention} "
                "is already in the exceptions list."
            )
            return

        # Save to MongoDB first.
        added = self.manager.add_exception(
            guild.id,
            channel_to_add.id
        )

        if not added:
            await ctx.message.reply(
                f"⚠️ {channel_to_add.mention} "
                "is already in the exceptions list."
            )
            return

        # Make the channel visible to prisoners.
        try:
            await channel_to_add.set_permissions(
                prisoner_role,
                view_channel=True
            )

        except discord.Forbidden:
            # Roll back DB if Discord permission update fails.
            self.manager.remove_exception(
                guild.id,
                channel_to_add.id
            )

            await ctx.message.reply(
                "❌ I don't have permission to modify "
                f"{channel_to_add.mention}."
            )
            return

        except discord.HTTPException as e:
            # Roll back DB if Discord returns an error.
            self.manager.remove_exception(
                guild.id,
                channel_to_add.id
            )

            await ctx.message.reply(
                f"❌ Discord returned an error: `{e}`"
            )
            return

        await ctx.message.reply(
            f"✅ {channel_to_add.mention} "
            "has been added to the exceptions list.\n"
            "👁️ Prisoners can now see this channel."
        )

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def rem(
        self,
        ctx,
        *,
        channel: discord.abc.GuildChannel = None
    ):
        guild = ctx.guild

        if channel is None:
            channel_to_remove = ctx.channel
        else:
            channel_to_remove = channel

        prisoner_role = await self.get_prisoner_role(
            guild
        )

        if prisoner_role is None:
            await ctx.message.reply(
                "⚠️ The Prisoner role has not been configured yet.\n"
                "Use `-set @Prisoner` first."
            )
            return

        if not guild.me.guild_permissions.manage_roles:
            await ctx.message.reply(
                "❌ I need the **Manage Roles** permission."
            )
            return

        exceptions = self.manager.get_exceptions(
            guild.id
        )

        if str(channel_to_remove.id) not in {
            str(channel_id)
            for channel_id in exceptions
        }:
            await ctx.message.reply(
                f"⚠️ {channel_to_remove.mention} "
                "is not in the exceptions list."
            )
            return

        # Remove from MongoDB.
        removed = self.manager.remove_exception(
            guild.id,
            channel_to_remove.id
        )

        if not removed:
            await ctx.message.reply(
                "❌ Failed to remove the channel "
                "from the exceptions list."
            )
            return

        # Hide the channel from prisoners.
        try:
            await channel_to_remove.set_permissions(
                prisoner_role,
                view_channel=False
            )

        except discord.Forbidden:
            # Try to restore the DB entry.
            self.manager.add_exception(
                guild.id,
                channel_to_remove.id
            )

            await ctx.message.reply(
                "❌ I don't have permission to modify "
                f"{channel_to_remove.mention}."
            )
            return

        except discord.HTTPException as e:
            # Try to restore the DB entry.
            self.manager.add_exception(
                guild.id,
                channel_to_remove.id
            )

            await ctx.message.reply(
                f"❌ Discord returned an error: `{e}`"
            )
            return

        await ctx.message.reply(
            f"✅ {channel_to_remove.mention} "
            "has been removed from the exceptions list.\n"
            "🔒 Prisoners can no longer see this channel."
        )

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
                "⚠️ No exception channels found "
                "in this server."
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
                if isinstance(
                    channel,
                    discord.VoiceChannel
                ):
                    channel_type = "🔊 Voice"
                else:
                    channel_type = "💬 Text"

                exception_channels.append(
                    f"**{channel.mention}** "
                    f"({channel_type})"
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

        await ctx.message.reply(
            embed=embed
        )


async def setup(bot):
    await bot.add_cog(Exceptions(bot))

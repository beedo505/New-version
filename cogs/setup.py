import discord
from discord.ext import commands

from db import guilds_collection, settings_collection


class Setup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def set(self, ctx, role: discord.Role = None):
        guild = ctx.guild
        guild_id = str(guild.id)

        # Make sure the bot's member object is available.
        bot_member = guild.me
        if bot_member is None:
            await ctx.message.reply(
                "❌ I could not get my member information in this server."
            )
            return

        # Role is required.
        if role is None:
            await ctx.message.reply(
                "❌ You must mention a role or provide a valid role ID."
            )
            return

        # @everyone cannot be used as the Prisoner role.
        if role.is_default():
            await ctx.message.reply(
                "❌ You cannot use the @everyone role as the Prisoner role."
            )
            return

        # Managed roles cannot be manually assigned by the bot.
        if role.managed:
            await ctx.message.reply(
                "❌ You cannot use a managed/integration role as the Prisoner role."
            )
            return

        # The bot must be able to manage the selected role.
        if role >= bot_member.top_role:
            await ctx.message.reply(
                "❌ I cannot use this role because it is equal to or higher "
                "than my highest role."
            )
            return

        # The bot needs Manage Channels to change channel visibility.
        if not guild.me.guild_permissions.manage_channels:
            await ctx.message.reply(
                "❌ I need the **Manage Channels** permission to configure "
                "the Prisoner role."
            )
            return

        # Get the current server configuration.
        server_data = guilds_collection.find_one(
            {"guild_id": guild_id}
        )

        current_role_id = (
            server_data.get("prisoner_role_id")
            if server_data
            else None
        )

        exception_channels = (
            server_data.get("exception_channels", [])
            if server_data
            else []
        )

        # Normalize exception IDs to strings.
        exception_channels = {
            str(channel_id)
            for channel_id in exception_channels
        }

        # If this role is already configured, don't repeat the operation.
        if current_role_id == str(role.id):
            await ctx.message.reply(
                f"⚠️ The prisoner role is already set to: **{role.name}**."
            )
            return

        old_role = None

        # Try to get the previous Prisoner role.
        if current_role_id:
            try:
                old_role = guild.get_role(int(current_role_id))
            except (TypeError, ValueError):
                old_role = None

        try:
            # ---------------------------------------------------------
            # 1. Remove the old Prisoner role's explicit visibility deny.
            # ---------------------------------------------------------
            if old_role and old_role.id != role.id:
                for channel in guild.channels:
                    try:
                        await channel.set_permissions(
                            old_role,
                            view_channel=None
                        )
                    except discord.Forbidden:
                        await ctx.message.reply(
                            f"❌ I don't have permission to modify "
                            f"{channel.mention}."
                        )
                        return
                    except discord.HTTPException:
                        await ctx.message.reply(
                            f"❌ Discord returned an error while modifying "
                            f"{channel.mention}."
                        )
                        return

            # ---------------------------------------------------------
            # 2. Configure the NEW Prisoner role.
            #
            #    Exception channel  -> view_channel=True
            #    Normal channel     -> view_channel=False
            # ---------------------------------------------------------
            for channel in guild.channels:
                if str(channel.id) in exception_channels:
                    await channel.set_permissions(
                        role,
                        view_channel=True
                    )
                else:
                    await channel.set_permissions(
                        role,
                        view_channel=False
                    )

            # ---------------------------------------------------------
            # 3. Save the new Prisoner role in MongoDB.
            # ---------------------------------------------------------
            guilds_collection.update_one(
                {"guild_id": guild_id},
                {
                    "$set": {
                        "prisoner_role_id": str(role.id)
                    }
                },
                upsert=True
            )

        except discord.Forbidden:
            await ctx.message.reply(
                "❌ I don't have permission to modify one or more "
                "channels. Make sure I have **Manage Channels**."
            )
            return

        except discord.HTTPException as e:
            await ctx.message.reply(
                f"❌ Discord returned an error while configuring "
                f"the Prisoner role: `{e}`"
            )
            return

        except Exception as e:
            await ctx.message.reply(
                f"❌ An unexpected error occurred: `{e}`"
            )
            return

        await ctx.message.reply(
            f"✅ The prisoner role has been set to: **{role.name}**.\n"
            f"🔒 Prisoners can only see the configured exception channels."
        )

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def mod(self, ctx, channel: discord.TextChannel = None):
        guild_id = str(ctx.guild.id)

        # Channel is required.
        if channel is None:
            await ctx.message.reply(
                "❌ You must mention a text channel or provide a valid channel."
            )
            return

        server_data = settings_collection.find_one(
            {"guild_id": guild_id}
        )

        existing_channel_id = (
            server_data.get("mod_log_channel_id")
            if server_data
            else None
        )

        if (
            existing_channel_id
            and str(existing_channel_id) == str(channel.id)
        ):
            await ctx.message.reply(
                f"⚠️ The moderation log channel is already set to "
                f"{channel.mention}."
            )
            return

        settings_collection.update_one(
            {"guild_id": guild_id},
            {
                "$set": {
                    "mod_log_channel_id": str(channel.id)
                }
            },
            upsert=True
        )

        await ctx.message.reply(
            f"✅ The moderation log channel has been set to "
            f"{channel.mention}."
        )


async def setup(bot):
    await bot.add_cog(Setup(bot))

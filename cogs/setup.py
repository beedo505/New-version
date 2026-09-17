import asyncio

import discord
from discord.ext import commands

from db import guilds_collection, settings_collection


class Setup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # =========================================================
    # Set Prisoner Role
    # =========================================================

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def set(self, ctx, role: discord.Role = None):
        guild = ctx.guild
        guild_id = str(guild.id)

        bot_member = guild.me

        if bot_member is None:
            await ctx.message.reply(
                "❌ I could not get my member information in this server."
            )
            return

        if role is None:
            await ctx.message.reply(
                "❌ You must mention a role or provide a valid role ID."
            )
            return

        if role.is_default():
            await ctx.message.reply(
                "❌ You cannot use the @everyone role as the Prisoner role."
            )
            return

        if role.managed:
            await ctx.message.reply(
                "❌ You cannot use a managed/integration role as the Prisoner role."
            )
            return

        if role >= bot_member.top_role:
            await ctx.message.reply(
                "❌ I cannot use this role because it is equal to or higher "
                "than my highest role."
            )
            return

        if not bot_member.guild_permissions.manage_channels:
            await ctx.message.reply(
                "❌ I need the **Manage Channels** permission to configure "
                "the Prisoner role."
            )
            return

        server_data = await asyncio.to_thread(
            guilds_collection.find_one,
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

        exception_channels = {
            str(channel_id)
            for channel_id in exception_channels
        }

        if current_role_id == str(role.id):
            await ctx.message.reply(
                f"⚠️ The prisoner role is already set to: **{role.name}**."
            )
            return

        # ---------------------------------------------------------
        # If another Prisoner role was configured before,
        # restore its channel permissions first.
        # ---------------------------------------------------------

        old_role = None

        if current_role_id:
            try:
                old_role = guild.get_role(
                    int(current_role_id)
                )
            except (TypeError, ValueError):
                old_role = None

        try:
            if old_role and old_role.id != role.id:

                old_overwrites = (
                    server_data.get(
                        "prisoner_original_overwrites",
                        {}
                    )
                )

                for channel in guild.channels:

                    old_state = old_overwrites.get(
                        str(channel.id)
                    )

                    if old_state is not None:
                        overwrite = channel.overwrites_for(
                            old_role
                        )

                        original_view = old_state.get(
                            "view_channel"
                        )

                        if original_view is None:
                            overwrite.view_channel = None
                        else:
                            overwrite.view_channel = original_view

                        await channel.set_permissions(
                            old_role,
                            overwrite=overwrite
                        )

                    else:
                        # No saved state for this old role.
                        # Remove only the view_channel override.
                        overwrite = channel.overwrites_for(
                            old_role
                        )

                        overwrite.view_channel = None

                        await channel.set_permissions(
                            old_role,
                            overwrite=overwrite
                        )

            # ---------------------------------------------------------
            # Save the current role's original view_channel states
            # BEFORE changing anything.
            # ---------------------------------------------------------

            original_overwrites = {}

            for channel in guild.channels:
                overwrite = channel.overwrites_for(role)

                original_overwrites[
                    str(channel.id)
                ] = {
                    "view_channel": overwrite.view_channel
                }

            # ---------------------------------------------------------
            # Configure the new Prisoner role.
            # Exception channels = visible.
            # Everything else = hidden.
            # ---------------------------------------------------------

            for channel in guild.channels:

                overwrite = channel.overwrites_for(
                    role
                )

                if str(channel.id) in exception_channels:
                    overwrite.view_channel = True
                else:
                    overwrite.view_channel = False

                await channel.set_permissions(
                    role,
                    overwrite=overwrite
                )

            # ---------------------------------------------------------
            # Save configuration.
            # ---------------------------------------------------------

            await asyncio.to_thread(
                guilds_collection.update_one,
                {"guild_id": guild_id},
                {
                    "$set": {
                        "prisoner_role_id": str(role.id),
                        "prisoner_original_overwrites": (
                            original_overwrites
                        )
                    }
                },
                upsert=True
            )

        except discord.Forbidden:
            await ctx.message.reply(
                "❌ I don't have permission to modify one or more "
                "channels. Make sure I have **Manage Channels** "
                "and **Manage Roles**."
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

    # =========================================================
    # Unset Prisoner Role
    # =========================================================

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def unset(self, ctx):
        guild = ctx.guild
        guild_id = str(guild.id)

        bot_member = guild.me

        if bot_member is None:
            await ctx.message.reply(
                "❌ I could not get my member information in this server."
            )
            return

        if not bot_member.guild_permissions.manage_channels:
            await ctx.message.reply(
                "❌ I need the **Manage Channels** permission "
                "to remove the Prisoner configuration."
            )
            return

        server_data = await asyncio.to_thread(
            guilds_collection.find_one,
            {"guild_id": guild_id}
        )

        if not server_data:
            await ctx.message.reply(
                "⚠️ No Prisoner configuration was found for this server."
            )
            return

        prisoner_role_id = server_data.get(
            "prisoner_role_id"
        )

        if not prisoner_role_id:
            await ctx.message.reply(
                "⚠️ No Prisoner role is currently configured."
            )
            return

        try:
            prisoner_role = guild.get_role(
                int(prisoner_role_id)
            )
        except (TypeError, ValueError):
            prisoner_role = None

        try:
            # ---------------------------------------------------------
            # Restore the original channel permissions.
            # ---------------------------------------------------------

            original_overwrites = server_data.get(
                "prisoner_original_overwrites",
                {}
            )

            if prisoner_role:

                for channel in guild.channels:

                    saved_state = original_overwrites.get(
                        str(channel.id)
                    )

                    overwrite = channel.overwrites_for(
                        prisoner_role
                    )

                    if saved_state is not None:
                        original_view = saved_state.get(
                            "view_channel"
                        )

                        overwrite.view_channel = original_view

                    else:
                        # Older configuration that did not save
                        # the original state.
                        overwrite.view_channel = None

                    await channel.set_permissions(
                        prisoner_role,
                        overwrite=overwrite
                    )

            # ---------------------------------------------------------
            # Remove Prisoner configuration from MongoDB.
            # Exception channels remain untouched.
            # ---------------------------------------------------------

            await asyncio.to_thread(
                guilds_collection.update_one,
                {"guild_id": guild_id},
                {
                    "$unset": {
                        "prisoner_role_id": "",
                        "prisoner_original_overwrites": ""
                    }
                }
            )

        except discord.Forbidden:
            await ctx.message.reply(
                "❌ I don't have permission to restore one or more "
                "channel permissions."
            )
            return

        except discord.HTTPException as e:
            await ctx.message.reply(
                f"❌ Discord returned an error while removing "
                f"the Prisoner configuration: `{e}`"
            )
            return

        except Exception as e:
            await ctx.message.reply(
                f"❌ An unexpected error occurred: `{e}`"
            )
            return

        if prisoner_role:
            role_text = f"**{prisoner_role.name}**"
        else:
            role_text = "the deleted Prisoner role"

        await ctx.message.reply(
            f"✅ Prisoner configuration has been removed from {role_text}.\n"
            f"🔓 The original channel permissions have been restored."
        )

    # =========================================================
    # Moderation Log Channel
    # =========================================================

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def mod(
        self,
        ctx,
        channel: discord.TextChannel = None
    ):
        guild_id = str(ctx.guild.id)

        if channel is None:
            channel = ctx.channel

        server_data = await asyncio.to_thread(
            settings_collection.find_one,
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

        await asyncio.to_thread(
            settings_collection.update_one,
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


# =========================================================
# Extension Setup
# =========================================================

async def setup(bot):
    await bot.add_cog(Setup(bot))

import asyncio
from datetime import datetime, timezone

import discord

from db import settings_collection


async def send_log(
    guild: discord.Guild,
    *,
    title: str,
    description: str = None,
    color: discord.Color = discord.Color.blurple(),
    moderator: discord.Member = None,
    target: discord.Member = None,
    reason: str = None,
    fields: list[tuple[str, str, bool]] = None,
):
    """
    Send a moderation log to the channel configured with -mod.

    This function is intentionally independent from the actual
    moderation action. If logging fails, the main bot action
    should continue normally.
    """

    if guild is None:
        return False

    try:
        # ---------------------------------------------------------
        # Get configured log channel
        # ---------------------------------------------------------

        server_data = await asyncio.to_thread(
            settings_collection.find_one,
            {"guild_id": str(guild.id)},
            {"mod_log_channel_id": 1},
        )

        if not server_data:
            return False

        channel_id = server_data.get("mod_log_channel_id")

        if not channel_id:
            return False

        try:
            channel = guild.get_channel(int(channel_id))
        except (TypeError, ValueError):
            return False

        if channel is None:
            return False

        # ---------------------------------------------------------
        # Build Embed
        # ---------------------------------------------------------

        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now(timezone.utc),
        )

        # ---------------------------------------------------------
        # Target
        # ---------------------------------------------------------

        if target is not None:
            embed.add_field(
                name="👤 Target",
                value=f"{target.mention}\n`{target.id}`",
                inline=True,
            )

        # ---------------------------------------------------------
        # Moderator
        # ---------------------------------------------------------

        if moderator is not None:
            embed.add_field(
                name="🛡️ Moderator",
                value=f"{moderator.mention}\n`{moderator.id}`",
                inline=True,
            )

        # ---------------------------------------------------------
        # Reason
        # ---------------------------------------------------------

        if reason:
            embed.add_field(
                name="📝 Reason",
                value=reason,
                inline=False,
            )

        # ---------------------------------------------------------
        # Custom fields
        # ---------------------------------------------------------

        if fields:
            for name, value, inline in fields:
                embed.add_field(
                    name=name,
                    value=value,
                    inline=inline,
                )

        # ---------------------------------------------------------
        # Footer
        # ---------------------------------------------------------

        embed.set_footer(
            text=f"{guild.name} • Moderation Logs"
        )

        # ---------------------------------------------------------
        # Send Log
        # ---------------------------------------------------------

        await channel.send(embed=embed)

        return True

    except discord.Forbidden:
        print(
            f"⚠️ Cannot send moderation log in guild "
            f"{guild.id}: missing permissions."
        )
        return False

    except discord.NotFound:
        print(
            f"⚠️ Moderation log channel was not found "
            f"in guild {guild.id}."
        )
        return False

    except discord.HTTPException as e:
        print(
            f"⚠️ Discord error while sending moderation log "
            f"in guild {guild.id}: {e}"
        )
        return False

    except Exception as e:
        print(
            f"⚠️ Unexpected error in moderation logger "
            f"for guild {guild.id}: {e}"
        )
        return False

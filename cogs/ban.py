import discord
from discord.ext import commands


class ban(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # =========================================================
    # Ban
    # =========================================================

    @commands.command(
        aliases=[
            # Add your custom aliases here.
            # Example:
            # "اBan",
            # "اخرج",
            # "احظر",
        ]
    )
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    async def حظر(
        self,
        ctx,
        user: discord.User = None,
        *,
        reason="No reason"
    ):
        # Show command information when no user is provided
        if user is None:
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
                title="📝 أمر الحظر",
                color=0x2F3136
            )

            embed.add_field(
                name="📌 معلومات الأمر",
                value=(
                    "• الأمر: `-حظر @username` أو `-حظر USER_ID`\n"
                    "• الوظيفة: حظر العضو من السيرفر"
                ),
                inline=False
            )

            embed.add_field(
                name="💡 مثال",
                value="`-حظر @username spam`",
                inline=False
            )

            embed.add_field(
                name="🔗 الاختصارات",
                value=aliases_text,
                inline=False
            )

            await ctx.message.reply(embed=embed)
            return

        # Prevent self-ban
        if user.id == ctx.author.id:
            await ctx.message.reply(
                "❌ You cannot ban yourself!"
            )
            return

        try:
            await ctx.guild.ban(
                user,
                delete_message_seconds=0,
                reason=reason
            )

            embed = discord.Embed(
                title="✅ User Banned!",
                description=(
                    f"**User:** {user.mention} (`{user.id}`)\n"
                    f"**Reason:** {reason}"
                ),
                color=discord.Color.red()
            )

            embed.set_footer(
                text=f"Banned by {ctx.author}",
                icon_url=(
                    ctx.author.avatar.url
                    if ctx.author.avatar
                    else None
                )
            )

            await ctx.message.reply(embed=embed)

        except discord.NotFound:
            await ctx.message.reply(
                "❌ User not found. Make sure the ID is correct."
            )

        except discord.Forbidden:
            await ctx.message.reply(
                "❌ I don't have permission to ban this user."
            )

        except discord.HTTPException as e:
            await ctx.message.reply(
                f"❌ An error occurred while trying to ban the user: {e}"
            )

    # =========================================================
    # Unban
    # =========================================================

    @commands.command(
        aliases=[
            # Add your custom aliases here.
            # Example:
            # "فك_الحظر",
            # "ارجع",
            # "الغاء_الحظر",
        ]
    )
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    async def فك(
        self,
        ctx,
        *,
        user_input=None
    ):
        # Show usage information when no user is provided
        if user_input is None:
            await ctx.reply(
                "❌ Please mention the user or enter their ID to unban."
            )
            return

        # Convert mention / ID into a Discord user ID
        try:
            if user_input.startswith("<@") and user_input.endswith(">"):
                user_id = int(
                    user_input[2:-1].replace("!", "")
                )
            else:
                user_id = int(user_input)

        except ValueError:
            embed = discord.Embed(
                title="⚠️ Invalid Input",
                description=(
                    "Please mention a user (`@username`) "
                    "or enter their ID correctly."
                ),
                color=discord.Color.orange()
            )

            await ctx.reply(embed=embed)
            return

        try:
            # Fetch the ban directly instead of checking
            # every banned user in the server.
            ban_entry = await ctx.guild.fetch_ban(
                discord.Object(id=user_id)
            )

            await ctx.guild.unban(
                ban_entry.user,
                reason=f"Unbanned by {ctx.author}"
            )

            embed = discord.Embed(
                title="✅ Unban Successful",
                description=(
                    f"User {ban_entry.user.mention} "
                    f"(`{ban_entry.user.id}`) has been unbanned."
                ),
                color=discord.Color.green()
            )

            embed.set_footer(
                text=f"Action by: {ctx.author}",
                icon_url=(
                    ctx.author.avatar.url
                    if ctx.author.avatar
                    else None
                )
            )

            embed.timestamp = ctx.message.created_at

            await ctx.reply(embed=embed)

        except discord.NotFound:
            embed = discord.Embed(
                title="❌ Unban Failed",
                description=(
                    f"User with ID `{user_id}` is not banned."
                ),
                color=discord.Color.red()
            )

            embed.set_footer(
                text=f"Action by: {ctx.author}",
                icon_url=(
                    ctx.author.avatar.url
                    if ctx.author.avatar
                    else None
                )
            )

            embed.timestamp = ctx.message.created_at

            await ctx.reply(embed=embed)

        except discord.Forbidden:
            await ctx.reply(
                "❌ I don't have permission to unban this user."
            )

        except discord.HTTPException as e:
            embed = discord.Embed(
                title="❌ An Error Occurred",
                description=(
                    f"Failed to unban the user: `{e}`"
                ),
                color=discord.Color.red()
            )

            await ctx.reply(embed=embed)


# =============================================================
# Extension Setup
# =============================================================

async def setup(bot):
    await bot.add_cog(Ban(bot))

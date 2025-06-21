import discord
from discord.ext import commands
from pymongo import MongoClient
import os

client = MongoClient(os.getenv("MONGODB_URI"))
db = client["Prison"]

class Ban(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=['افتح', 'اغرق', 'برا', 'افتحك', 'اشخطك', 'انهي'])
    @commands.has_permissions(ban_members=True)
    async def زوطلي(self, ctx, user: discord.User = None, *, reason="No reason"):
        if user is None:
            embed = discord.Embed(title="📝 أمر الباند", color=0x2f3136)
            embed.add_field(name="📌 معلومات الأمر", value="• الأمر: -زوطلي\n• الوظيفة: باند للعضو", inline=False)
            embed.add_field(name="💡 الاختصارات المتاحة", value="• -افتح\n• -اغرق\n• -برا\n• -افتحك\n• -اشخطك\n• -انهي", inline=False)
            await ctx.message.reply(embed=embed)
            return

        if user == ctx.author:
            await ctx.message.reply("You cannot ban yourself!")
            return

        try:
            fetched_user = await self.bot.fetch_user(user.id)
            await ctx.guild.ban(fetched_user, delete_message_days=0, reason=reason)

            embed = discord.Embed(
                title="✅ User Banned!",
                description=f"**User:** {fetched_user.mention} (`{fetched_user.id}`)\n**Reason:** {reason}",
                color=discord.Color.red()
            )
            embed.set_footer(text=f"Banned by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)

            await ctx.message.reply(embed=embed)

        except discord.NotFound:
            await ctx.message.reply("❌ User not found. Make sure the ID is correct.")
        except discord.Forbidden:
            await ctx.message.reply("❌ I don't have permission to ban this user.")
        except discord.HTTPException as e:
            await ctx.message.reply(f"An error occurred while trying to ban the user: {e}")

    @commands.command(aliases=['unban', 'un'])
    @commands.has_permissions(ban_members=True)
    async def فك(self, ctx, *, user_input=None):
        if user_input is None:
            await ctx.reply("Please mention the user or their ID to unban.")
            return

        try:
            if user_input.startswith("<@") and user_input.endswith(">"):
                user_id = int(user_input[2:-1].replace("!", ""))
            else:
                user_id = int(user_input)

            async for ban_entry in ctx.guild.bans():
                if ban_entry.user.id == user_id:
                    await ctx.guild.unban(ban_entry.user)

                    embed = discord.Embed(
                        title="✅ Unban Successful",
                        description=f"User {ban_entry.user.mention} (`{ban_entry.user.id}`) has been unbanned.",
                        color=discord.Color.green()
                    )
                    embed.set_footer(text=f"Action by: {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
                    embed.timestamp = ctx.message.created_at
                    await ctx.reply(embed=embed)
                    return

            embed = discord.Embed(
                title="❌ Unban Failed",
                description=f"User with ID `{user_id}` is not banned.",
                color=discord.Color.red()
            )
            embed.set_footer(text=f"Action by: {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
            embed.timestamp = ctx.message.created_at
            await ctx.reply(embed=embed)

        except ValueError:
            embed = discord.Embed(
                title="⚠️ Invalid Input",
                description="Please mention a user (`@username`) or enter their ID correctly.",
                color=discord.Color.orange()
            )
            await ctx.reply(embed=embed)

        except discord.HTTPException as e:
            embed = discord.Embed(
                title="❌ An Error Occurred",
                description=f"Failed to unban the user: `{e}`",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(Ban(bot))

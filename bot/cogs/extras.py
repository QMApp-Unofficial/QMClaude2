import asyncio
import time
import random

import discord
from discord.ext import commands

from config import XP_PER_MESSAGE
from storage import load_data
from ui_utils import C, E, embed, error, info


class Extras(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()

    # ─────────────────────────────────────────
    # Utility
    # ─────────────────────────────────────────

    @commands.hybrid_command()
    async def ping(self, ctx):
        """Check bot latency."""
        latency = round(self.bot.latency * 1000)
        if latency < 100:
            tone, flavour = C.WIN, "Snappy."
        elif latency < 250:
            tone, flavour = C.ADMIN, "Healthy."
        else:
            tone, flavour = C.WARN, "Feeling sluggish."
        e = embed(
            f"🏓  Pong",
            f"Gateway latency: **`{latency} ms`**\n{flavour}",
            tone,
        )
        await ctx.send(embed=e)

    @commands.hybrid_command()
    async def uptime(self, ctx):
        """Show how long the bot has been running."""
        seconds = int(time.time() - self.start_time)
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes = remainder // 60
        parts = []
        if days:
            parts.append(f"{days}d")
        parts.append(f"{hours}h")
        parts.append(f"{minutes}m")
        e = embed(
            f"{E.CLOCK}  Uptime",
            f"Running for **`{' '.join(parts)}`**",
            C.ADMIN,
        )
        await ctx.send(embed=e)

    @commands.hybrid_command()
    async def botinfo(self, ctx):
        """Display general bot information."""
        e = embed(
            "🤖  Bot Info",
            "",
            C.ADMIN,
            thumbnail=self.bot.user.display_avatar.url if self.bot.user else None,
        )
        e.add_field(name="Servers", value=f"`{len(self.bot.guilds):,}`", inline=True)
        e.add_field(name="Users",   value=f"`{len(self.bot.users):,}`",  inline=True)
        e.add_field(name="Latency", value=f"`{round(self.bot.latency * 1000)} ms`", inline=True)
        await ctx.send(embed=e)

    @commands.hybrid_command()
    async def serverinfo(self, ctx):
        """Display information about this server."""
        guild = ctx.guild
        if not guild:
            return await ctx.send(embed=error("Server Info", "This command only works inside a server."))

        e = embed(
            f"🏠  {guild.name}",
            "",
            C.ADMIN,
            thumbnail=guild.icon.url if guild.icon else None,
        )
        e.add_field(name="Members",  value=f"`{guild.member_count:,}`",   inline=True)
        e.add_field(name="Channels", value=f"`{len(guild.channels)}`",    inline=True)
        e.add_field(name="Roles",    value=f"`{len(guild.roles)}`",       inline=True)
        e.add_field(name="Created",  value=f"<t:{int(guild.created_at.timestamp())}:D>", inline=True)
        if guild.owner:
            e.add_field(name="Owner", value=guild.owner.mention, inline=True)
        await ctx.send(embed=e)

    @commands.hybrid_command()
    async def userinfo(self, ctx, member: discord.Member = None):
        """Display information about a user."""
        member = member or ctx.author
        e = embed(
            f"👤  {member.display_name}",
            "",
            C.ADMIN,
            thumbnail=member.display_avatar.url,
        )
        e.add_field(name="Username", value=f"`{member}`", inline=True)
        e.add_field(name="ID",       value=f"`{member.id}`", inline=True)
        if member.joined_at:
            e.add_field(name="Joined Server", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
        e.add_field(name="Account Created", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
        roles = [r.mention for r in member.roles if r.name != "@everyone"]
        if roles:
            value = ", ".join(roles[:15])
            if len(roles) > 15:
                value += f" … (+{len(roles) - 15} more)"
            e.add_field(name=f"Roles ({len(roles)})", value=value, inline=False)
        await ctx.send(embed=e)

    @commands.hybrid_command()
    async def gif(self, ctx, *, query: str):
        """Send a random GIF."""
        gifs = [
            "https://media.giphy.com/media/ICOgUNjpvO0PC/giphy.gif",
            "https://media.giphy.com/media/l0HlQ7LRalQqdWfao/giphy.gif",
            "https://media.giphy.com/media/3o7aD2saalBwwftBIY/giphy.gif",
        ]
        e = embed(
            f"{E.SPARKLE}  GIF · {query}",
            "",
            C.SOCIAL,
        )
        e.set_image(url=random.choice(gifs))
        await ctx.send(embed=e)

    @commands.hybrid_command(name="messagecount")
    async def messagecount(self, ctx, member: discord.Member = None):
        """Show a user's message count since the last XP reset."""
        if not ctx.guild:
            return await ctx.send(embed=error("Message Count", "This command only works in a server."))

        target = member or ctx.author
        data = load_data()
        guild_data = data.get(str(ctx.guild.id), {})
        user_data = guild_data.get(str(target.id), {})

        xp = int(user_data.get("xp", 0))
        messages = xp // XP_PER_MESSAGE

        e = embed(
            f"💬  Message Count",
            f"**{target.display_name}** has sent **`{messages:,}`** messages since the last reset.",
            C.ADMIN,
            thumbnail=target.display_avatar.url,
        )
        await ctx.send(embed=e)

    @commands.hybrid_command()
    async def timer(self, ctx, seconds: int):
        """Start a countdown timer (max 300 seconds)."""
        if seconds <= 0:
            return await ctx.send(embed=error("Timer", "Timer must be greater than 0 seconds."))
        if seconds > 300:
            return await ctx.send(embed=error("Timer", "Maximum timer duration is **300 seconds**."))

        ends_at = int(time.time() + seconds)
        start = embed(
            f"⏳  Timer Started",
            f"Running for **`{seconds}`** seconds.\nEnds <t:{ends_at}:R>.",
            C.ADMIN,
            footer=f"Started by {ctx.author.display_name}",
        )
        await ctx.send(embed=start)
        await asyncio.sleep(seconds)
        done = embed(
            f"{E.CLOCK}  Time's Up",
            f"{ctx.author.mention} — your **`{seconds}s`** timer is complete.",
            C.WIN,
        )
        await ctx.send(embed=done)

# ─────────────────────────────────────────
# Setup
# ─────────────────────────────────────────

async def setup(bot):
    await bot.add_cog(Extras(bot))

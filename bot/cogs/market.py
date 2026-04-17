import io

import discord
import matplotlib.pyplot as plt
import numpy as np
from discord.ext import commands

from storage import load_coins, save_coins, load_stocks, save_stocks
from config import STOCKS


from ui_utils import C, E, embed as _embed, error, success, warn
EMBED_COLOR = C.MARKET


def make_embed(title: str, description: str):
    return _embed(title, description, EMBED_COLOR)


def ensure_user(coins, user_id):
    uid = str(user_id)

    if uid not in coins:
        coins[uid] = {
            "wallet": 100,
            "bank": 0,
            "portfolio": {}
        }

    coins[uid].setdefault("portfolio", {})

    return coins[uid]


def _render_stock_view(stock_name: str) -> tuple[discord.Embed, discord.File | None]:
    """Build the embed + optional chart file for a single stock. Shared by the
    /stockvalue command and the select-menu dropdown on /stocks."""
    stocks = load_stocks()
    data = stocks.get(stock_name)
    if not data:
        return make_embed("Market", "Unknown stock."), None

    price = int(data.get("price", 0))
    history = data.get("history", []) or []

    change = 0
    if len(history) > 1:
        change = price - int(history[-2])

    if len(history) < 2:
        em = discord.Embed(title=stock_name, color=EMBED_COLOR)
        em.add_field(name="Price", value=f"`{price}`", inline=True)
        em.add_field(name="Change", value=f"`{change:+}`", inline=True)
        em.add_field(name="Chart", value="Not enough history yet.", inline=False)
        return em, None

    x = np.arange(len(history))
    y = np.array(history, dtype=float)

    fig, ax = plt.subplots(figsize=(9, 4.8), dpi=150)
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")

    ax.plot(x, y, color="#4a90e2", linewidth=2.0, solid_capstyle="round")
    ax.fill_between(x, y, y.min(), color="#4a90e2", alpha=0.08)
    ax.grid(True, which="major", linestyle="-", linewidth=0.35, alpha=0.12, color="#ffffff")

    for spine in ax.spines.values():
        spine.set_color("#3a4250")
        spine.set_linewidth(0.8)

    ax.tick_params(axis="x", colors="#aeb6c2", labelsize=8)
    ax.tick_params(axis="y", colors="#aeb6c2", labelsize=8)

    ax.set_title(f"{stock_name} | Price History", color="#e6edf3", fontsize=13, pad=10)
    ax.set_xlabel("Updates", color="#aeb6c2", fontsize=9)
    ax.set_ylabel("Price", color="#aeb6c2", fontsize=9)

    ymin = float(y.min())
    ymax = float(y.max())
    pad = max(2.0, (ymax - ymin) * 0.10 if ymax > ymin else ymax * 0.06 + 2)
    ax.set_ylim(max(0, ymin - pad), ymax + pad)
    ax.scatter([x[-1]], [y[-1]], color="#4a90e2", s=18, zorder=3)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    sign = "+" if change > 0 else ""
    em = discord.Embed(title=stock_name, description="Current market snapshot", color=EMBED_COLOR)
    em.add_field(name="Price", value=f"`{price}`", inline=True)
    em.add_field(name="Change", value=f"`{sign}{change}`", inline=True)
    em.add_field(name="History", value=f"`{len(history)}`", inline=True)
    em.set_image(url="attachment://stock.png")
    em.set_footer(text="📈 Historical price chart")

    return em, discord.File(buf, filename="stock.png")


class _StockSelect(discord.ui.Select):
    def __init__(self, author_id: int):
        self.author_id = author_id
        stocks = load_stocks()
        options = []
        for name in STOCKS:
            price = int(stocks.get(name, {}).get("price", 0))
            history = stocks.get(name, {}).get("history", []) or []
            change = price - int(history[-2]) if len(history) > 1 else 0
            sign = "+" if change > 0 else ("" if change == 0 else "")
            emoji = "📈" if change > 0 else ("📉" if change < 0 else "➖")
            options.append(
                discord.SelectOption(
                    label=name[:100],
                    description=f"Price: {price}  ·  Change: {sign}{change}"[:100],
                    value=name,
                    emoji=emoji,
                )
            )
        super().__init__(
            placeholder="Pick a stock to chart…",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message(
                embed=error("Market", "Only the command author can pick here."),
                ephemeral=True,
            )
        stock_name = self.values[0]
        em, file = _render_stock_view(stock_name)
        if file is not None:
            await interaction.response.send_message(embed=em, file=file, ephemeral=True)
        else:
            await interaction.response.send_message(embed=em, ephemeral=True)


class StockSelectView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=120)
        self.add_item(_StockSelect(author_id))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True


class Stocks(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # -------------------------
    # STOCK LIST
    # -------------------------

    @commands.hybrid_command(
        name="stocks",
        description="View all stock prices."
    )
    async def stocks(self, ctx: commands.Context):

        stocks = load_stocks()

        rows = []

        for name in STOCKS:
            price = int(stocks.get(name, {}).get("price", 0))

            row = (
                f"{name[:16].ljust(16)} | "
                f"{str(price).rjust(6)}"
            )

            rows.append(row)

        table = (
            "```text\n"
            "Stock           |Price\n"
            "----------------------\n"
            f"{chr(10).join(rows)}\n"
            "```"
        )

        embed = discord.Embed(
            title="📈  Market",
            description=table,
            color=EMBED_COLOR
        )

        embed.set_footer(text="📊 Live prices  ·  Pick a stock below to see its chart")
        view = StockSelectView(ctx.author.id)
        await ctx.send(embed=embed, view=view)

    # -------------------------
    # STOCK VALUE
    # -------------------------

    @commands.hybrid_command(
        name="stockvalue",
        description="Show a stock's price and chart."
    )
    async def stockvalue(self, ctx: commands.Context, stock: str):

        stock_names = {s.lower(): s for s in STOCKS}
        key = stock.lower().strip()

        if key not in stock_names:
            return await ctx.send(embed=make_embed("Market", "Unknown stock."))

        stock_name = stock_names[key]
        em, file = _render_stock_view(stock_name)
        if file is not None:
            await ctx.send(embed=em, file=file)
        else:
            await ctx.send(embed=em)

    # -------------------------
    # PORTFOLIO
    # -------------------------

    @commands.hybrid_command(
        name="portfolio",
        description="View your stock portfolio."
    )
    async def portfolio(self, ctx: commands.Context, member: discord.Member = None):

        member = member or ctx.author

        coins = load_coins()
        user = ensure_user(coins, member.id)

        pf = user.get("portfolio", {})
        stocks = load_stocks()

        rows = []
        total = 0

        for s in STOCKS:

            qty = int(pf.get(s, 0))

            if qty > 0:

                price = int(stocks.get(s, {}).get("price", 0))
                value = qty * price
                total += value

                row = (
                    f"{s[:16].ljust(16)} | "
                    f"{str(qty).rjust(3)} | "
                    f"{str(value).rjust(6)}"
                )

                rows.append(row)

        if not rows:
            rows = ["No stocks."]

        table = (
            "```text\n"
            "Stock           |Qty |Value\n"
            "---------------------------\n"
            f"{chr(10).join(rows)}\n"
            "```"
        )

        embed = discord.Embed(
            title=f"📊  {member.display_name}'s Portfolio",
            description=table,
            color=EMBED_COLOR
        )

        embed.add_field(name="Total Value", value=f"`{total}`", inline=False)

        await ctx.send(embed=embed)

    # -------------------------
    # BUY STOCK
    # -------------------------

    @commands.hybrid_command(
        name="buy",
        description="Buy shares of a stock."
    )
    async def buy(self, ctx: commands.Context, stock: str, amount: str):

        stock_names = {s.lower(): s for s in STOCKS}
        key = stock.lower().strip()

        if key not in stock_names:
            return await ctx.send(embed=make_embed("Market", "Unknown stock."))

        stock_name = stock_names[key]
        stocks = load_stocks()
        price = int(stocks.get(stock_name, {}).get("price", 0))
        if price <= 0:
            return await ctx.send(embed=make_embed("Market", "That stock has no price data yet."))
        coins = load_coins()
        user = ensure_user(coins, ctx.author.id)
        if isinstance(amount, str) and amount.lower() == "all":
            qty = user["wallet"] // price
            if qty <= 0:
                return await ctx.send(embed=make_embed("Market", "Not enough coins to buy even 1 share."))
        else:
            try:
                qty = int(amount)
            except (ValueError, TypeError):
                return await ctx.send(embed=make_embed("Market", "Enter a number or `all`."))
        if qty <= 0:
            return await ctx.send(embed=make_embed("Market", "Invalid amount."))
        cost = price * qty
        if user["wallet"] < cost:
            afford = user["wallet"] // price
            return await ctx.send(embed=make_embed("Market", f"Not enough coins. You can afford **{afford}** share(s) at {price} each."))
        user["wallet"] -= cost
        pf = user["portfolio"]
        pf[stock_name] = int(pf.get(stock_name, 0)) + qty
        save_coins(coins)
        tasks = self.bot.get_cog("BackgroundTasks")
        if tasks:
            tasks.record_trade(stock_name, "buy", qty)
        embed = discord.Embed(
            title="✅  Order Filled",
            description=f"Bought **{qty}** shares of **{stock_name}**.",
            color=EMBED_COLOR
        )
        embed.add_field(name="Cost",  value=f"`{cost:,}`",       inline=True)
        embed.add_field(name="Price", value=f"`{price:,}` each", inline=True)
        await ctx.send(embed=embed)

    # -------------------------
    # SELL STOCK
    # -------------------------

    @commands.hybrid_command(
        name="sell",
        description="Sell shares of a stock."
    )
    async def sell(self, ctx: commands.Context, stock: str, amount: int):

        stock_names = {s.lower(): s for s in STOCKS}
        key = stock.lower().strip()

        if key not in stock_names:
            return await ctx.send(embed=make_embed("Market", "Unknown stock."))

        if amount <= 0:
            return await ctx.send(embed=make_embed("Market", "Invalid amount."))

        stock_name = stock_names[key]

        coins = load_coins()
        user = ensure_user(coins, ctx.author.id)

        pf = user["portfolio"]
        owned = int(pf.get(stock_name, 0))

        if owned < amount:
            return await ctx.send(embed=make_embed("Market", "Not enough shares."))

        stocks = load_stocks()
        price = int(stocks.get(stock_name, {}).get("price", 0))
        revenue = price * amount

        pf[stock_name] = owned - amount
        user["wallet"] += revenue

        save_coins(coins)

        tasks = self.bot.get_cog("BackgroundTasks")
        if tasks:
            tasks.record_trade(stock_name, "sell", amount)

        embed = discord.Embed(
            title="✅  Order Filled",
            description=f"Sold **{amount}** shares of **{stock_name}**.",
            color=EMBED_COLOR
        )

        embed.add_field(name="Revenue", value=f"`{revenue}`", inline=True)
        embed.add_field(name="Price", value=f"`{price}` each", inline=True)

        await ctx.send(embed=embed)

    # -------------------------
    # RESET MARKET
    # -------------------------

    @commands.hybrid_command(
        name="resetmarket",
        description="Reset all stock prices to 100."
    )
    @discord.app_commands.default_permissions(manage_guild=True)
    @commands.has_permissions(manage_guild=True)
    async def resetmarket(self, ctx: commands.Context):

        stocks = load_stocks()

        for name in STOCKS:
            stocks[name]["price"] = 100

        save_stocks(stocks)

        embed = discord.Embed(
            title="⚠️  Market Reset",
            description="All stock prices have been reset to **100 coins**.",
            color=EMBED_COLOR
        )

        embed.set_footer(text=f"Reset by {ctx.author}")

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Stocks(bot))

import discord
from discord.ext import commands
import asyncio
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from flask import Flask
from threading import Thread

# --- INTENTS ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

# --- BOT SETUP ---
bot = commands.Bot(command_prefix="!", intents=intents)

# --- CONFIG ---
BOT_OWNER_ID = 1205486600520343582
WELCOME_CHANNEL_ID = 1399679493823795234
MEME_CHANNEL_ID = 1399679494490427418
user_last_message = {}
WHITELIST = {}  # user_id: [commands] or ["all"]

# --- MEMES ---
async def fetch_memes():
    url = "https://meme-api.com/gimme/20"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return (await resp.json())['memes']
            return []

async def post_memes():
    channel = bot.get_channel(MEME_CHANNEL_ID)
    if not channel:
        print("❌ Meme channel not found.")
        return
    memes = await fetch_memes()
    for meme in memes:
        embed = discord.Embed(title=meme['title'], url=meme['postLink'])
        embed.set_image(url=meme['url'])
        await channel.send(embed=embed)

# --- EVENTS ---
@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    scheduler = AsyncIOScheduler()
    scheduler.add_job(post_memes, 'cron', hour=1, minute=30)  # 7AM IST
    scheduler.start()

@bot.event
async def on_member_join(member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        try:
            await channel.send(f"**ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴏᴜʀ sᴇʀᴠᴇʀ𓂃 ✞**\n{member.mention} !!")
        except Exception as e:
            print(f"❌ Failed to send welcome: {e}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.mentions and any(user.id == BOT_OWNER_ID for user in message.mentions):
        try:
            await message.reply(f"{message.author.mention} MALIK ABHI BUSY HAI !!")
        except Exception as e:
            print(f"❌ Could not reply: {e}")

    last_msg = user_last_message.get(message.author.id)
    if last_msg and last_msg == message.content:
        try:
            await message.delete()
            print(f"🧹 Deleted spam from {message.author}")
        except Exception as e:
            print(f"❌ Failed to delete spam: {e}")
    else:
        user_last_message[message.author.id] = message.content

    await bot.process_commands(message)

# --- WHITELIST SYSTEM ---
def is_whitelisted(user_id, command_name):
    if user_id == BOT_OWNER_ID:
        return True
    allowed = WHITELIST.get(user_id, [])
    return "all" in allowed or command_name in allowed

@bot.command()
async def whitelist(ctx, user: discord.User, command: str):
    if ctx.author.id != BOT_OWNER_ID:
        await ctx.send("🚫 Only the bot owner can whitelist users.")
        return

    command = command.lower()
    uid = user.id

    if uid not in WHITELIST:
        WHITELIST[uid] = []

    if command == "all":
        WHITELIST[uid] = ["all"]
        await ctx.send(f"✅ `{user.name}` is now whitelisted for **all commands**.")
    elif command in ["dm", "msg", "nuke", "ban", "mute", "warn"]:
        if "all" in WHITELIST[uid] or command in WHITELIST[uid]:
            await ctx.send("⚠️ User already has that command.")
        else:
            WHITELIST[uid].append(command)
            await ctx.send(f"✅ `{user.name}` is now whitelisted for `!{command}`.")
    else:
        await ctx.send("❌ Unknown command. Use one of: `dm`, `msg`, `nuke`, `ban`, `mute`, `warn`, or `all`.")

@bot.command()
async def unwhitelist(ctx, user: discord.User):
    if ctx.author.id != BOT_OWNER_ID:
        await ctx.send("🚫 Only the bot owner can unwhitelist users.")
        return

    if user.id in WHITELIST:
        del WHITELIST[user.id]
        await ctx.send(f"✅ `{user.name}` has been unwhitelisted.")
    else:
        await ctx.send("⚠️ That user is not whitelisted.")

@bot.command(name="whitelistlist")
async def show_whitelist(ctx):
    if ctx.author.id != BOT_OWNER_ID:
        await ctx.send("🚫 Only the bot owner can view the whitelist.")
        return

    if not WHITELIST:
        await ctx.send("📭 Whitelist is currently empty.")
        return

    lines = []
    for uid, cmds in WHITELIST.items():
        try:
            user = await bot.fetch_user(uid)
            command_text = ', '.join(cmds)
            lines.append(f"`{user}` → {command_text}")
        except:
            continue

    await ctx.send("**📝 Whitelisted Users:**\n" + "\n".join(lines))

# --- COMMANDS ---
@bot.command()
async def dm(ctx, user_id: int, *, message: str):
    if not is_whitelisted(ctx.author.id, "dm"):
        await ctx.send("🚫 You are not authorized.")
        return
    try:
        user = await bot.fetch_user(user_id)
        await user.send(message)
        confirm = await ctx.send(f"✅ DM sent to `{user.name}#{user.discriminator}`.")
        await confirm.delete(delay=5)
    except Exception as e:
        await ctx.send(f"⚠️ {str(e)}")

@bot.command()
async def msg(ctx, channel_id: int, *, message: str):
    if not is_whitelisted(ctx.author.id, "msg"):
        await ctx.send("🚫 You are not authorized.")
        return
    channel = bot.get_channel(channel_id)
    if not channel:
        await ctx.send("❌ Channel not found.")
        return
    try:
        boxed = f"`{message}`" if len(message) <= 50 else f"```\n{message}\n```"
        await channel.send(boxed)
        confirm = await ctx.send(f"✅ Sent to <#{channel_id}>.")
        await confirm.delete(delay=5)
    except Exception as e:
        await ctx.send(f"⚠️ {str(e)}")

@bot.command()
async def nuke(ctx, amount: str):
    if not is_whitelisted(ctx.author.id, "nuke"):
        await ctx.send("🚫 Not authorized.")
        return
    try:
        if amount.lower() == "all":
            deleted = await ctx.channel.purge()
        else:
            deleted = await ctx.channel.purge(limit=int(amount)+1)
        await ctx.send(f"`Nuked {len(deleted)-1} messages by {ctx.author}.`")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command()
async def warn(ctx, member: discord.Member, *, reason=None):
    if not is_whitelisted(ctx.author.id, "warn"):
        await ctx.send("🚫 Not authorized.")
        return
    reason = reason or "No reason provided."
    await ctx.send(f"⚠️ {member.mention} warned! Reason: `{reason}`")

@bot.command()
async def mute(ctx, member: discord.Member):
    if not is_whitelisted(ctx.author.id, "mute"):
        await ctx.send("🚫 You are not authorized.")
        return
    try:
        mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
        if not mute_role:
            mute_role = await ctx.guild.create_role(name="Muted")
            for ch in ctx.guild.channels:
                await ch.set_permissions(mute_role, send_messages=False)
        await member.add_roles(mute_role)
        await ctx.send(f" {member.mention} muted.")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command()
async def ban(ctx, member: discord.Member, *, reason=None):
    if not is_whitelisted(ctx.author.id, "ban"):
        await ctx.send("🚫 You are not authorized.")
        return
    reason = reason or "No reason provided."
    await member.ban(reason=reason)
    await ctx.send(f"🔨 {member.mention} banned. Reason: `{reason}`")

@bot.command(name="command")
async def show_commands(ctx):
    if ctx.author.id != BOT_OWNER_ID:
        await ctx.send("🚫 You are not authorized.")
        return
    await ctx.send("""
** BILLA BHAI BOT COMMANDS**

`!dm <user_id> <msg>`  
`!msg <channel_id> <msg>`  
`!nuke <amount|all>`  
`!warn @user <reason>`  
`!mute @user`  
`!ban @user <reason>`  
`!command` → Show this help  
`!whitelist @user <command|all>`  
`!unwhitelist @user`  
`!whitelistlist`
""")

# --- KEEP ALIVE ---
app = Flask('')

@app.route('/')
def home():
    return "Billa Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- RUN ---
keep_alive()
import os

# Bot start
bot.run(os.getenv("DISCORD_TOKEN"))

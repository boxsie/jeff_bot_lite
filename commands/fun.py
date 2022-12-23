import discord
import math
from utils.date_helpers import get_next_occurance
from discord.ext import commands
from datetime import datetime, date

@commands.command(name='friday', help='Its friday!')
async def friday(ctx):
    if datetime.today().weekday() == 4:
        await ctx.send(f'https://www.youtube.com/watch?v=1TewCPi92ro')
    else:
        await ctx.channel.send(file=discord.File('resources/nedry.gif'))
      
      
@commands.command(name='xmas', help='Xmas Countdown')
async def xmas(ctx):
    date_countdown = get_next_occurance(12, 25)
           
    if date_countdown.is_today:
        await ctx.send(f"🎄🎄🎄 Merry Xmas 🎄🎄🎄 \nhttps://youtu.be/pHMhEWyqj2g?t=75")
    else:    
        await ctx.send(f"🎄🎄🎄 It's {date_countdown.days} days, {date_countdown.hours} "\
            f"hours & {date_countdown.mins} minutes until Christmas !! 🎄🎄🎄")
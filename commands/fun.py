import discord
import math
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
    today = datetime.today()
    xmas_day = datetime(today.year, 12, 25)
    delta = xmas_day - today
    if delta.days < 0:
        await ctx.send(f"🎄🎄🎄 It's bin 'n gone mate 🎄🎄🎄")
    elif delta.days == 0: 
        await ctx.send(f"🎄🎄🎄 Merry Xmas 🎄🎄🎄 \nhttps://youtu.be/pHMhEWyqj2g?t=75")
    else:    
        hours = int(delta.seconds // (60 * 60))
        mins = int((delta.seconds // 60) % 60)  
        await ctx.send(f"🎄🎄🎄 It's {delta.days} days, {hours} hours & {mins} minutes until Xmas !! 🎄🎄🎄")
        

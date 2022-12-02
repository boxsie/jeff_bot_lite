import discord
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
        today = datetime.date.today()
        xmas_day = date(today.year, 12, 25)
        delta = xmas_day - today
        if delta < 0:
            await ctx.send(f"It's bin 'n gone mate :KEKWX:")
        elif delta == 0: 
            await ctx.send(f"Merry Xmas :KEKWX: \nhttps://youtu.be/pHMhEWyqj2g?t=75")
        else:    
            await ctx.send(f"It's {delta.days} until Xmas!!!!")
        

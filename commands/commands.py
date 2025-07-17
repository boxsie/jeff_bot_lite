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


@commands.command(name='tuesday', help='Its tuesday!')
async def tuesday(ctx):
    print(datetime.today().weekday())
    if datetime.today().weekday() == 1:
        await ctx.send(f'https://www.youtube.com/watch?v=Bk1J9ojjzUo')
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


@commands.command(name='jobs', help='Show scheduled jobs and their next run times')
async def jobs(ctx):
    """Display information about all scheduled jobs"""
    try:
        # Access the scheduler from the bot client
        if not hasattr(ctx.bot, 'scheduler') or not ctx.bot.scheduler:
            await ctx.send("❌ No scheduler found on this bot.")
            return
        
        scheduler = ctx.bot.scheduler
        
        if not scheduler.jobs:
            await ctx.send("📅 No scheduled jobs currently registered.")
            return
        
        # Create an embed for better formatting
        embed = discord.Embed(
            title="📅 Scheduled Jobs",
            description="Current scheduled jobs and their next run times",
            color=0x00ff00,
            timestamp=datetime.now()
        )
        
        # Add scheduler status
        status_emoji = "🟢" if scheduler.running else "🔴"
        embed.add_field(
            name="Scheduler Status",
            value=f"{status_emoji} {'Running' if scheduler.running else 'Stopped'}",
            inline=False
        )
        
        # Sort jobs by next run time
        sorted_jobs = sorted(scheduler.jobs, key=lambda job: job.next_run)
        
        for i, job in enumerate(sorted_jobs, 1):
            # Calculate time until next run
            now = datetime.now()
            time_until = job.next_run - now
            
            # Format the time difference nicely
            if time_until.total_seconds() > 0:
                days = time_until.days
                hours, remainder = divmod(time_until.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                
                if days > 0:
                    time_str = f"{days}d {hours}h {minutes}m"
                elif hours > 0:
                    time_str = f"{hours}h {minutes}m"
                else:
                    time_str = f"{minutes}m"
                    
                time_display = f"⏰ In {time_str}"
            else:
                time_display = "⚠️ Overdue"
            
            # Format the next run time
            next_run_str = job.next_run.strftime("%Y-%m-%d %H:%M:%S")
            
            embed.add_field(
                name=f"{i}. {job.name}",
                value=f"**Cron:** `{job.cron_expression}`\n"
                      f"**Next Run:** {next_run_str}\n"
                      f"{time_display}",
                inline=True
            )
        
        # Add footer with current time
        embed.set_footer(text=f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Error retrieving job information: {str(e)}")
        # Log the error for debugging
        import logging
        logger = logging.getLogger('discord.commands')
        logger.error(f"Error in jobs command: {e}", exc_info=True)
import asyncio
import logging
from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands

from utils.ollama_client import OllamaClient

logger = logging.getLogger('discord.ollama_manager')

def is_admin_or_owner():
    """Custom check: bot owner in DMs, administrator in guilds"""
    async def predicate(ctx):
        # In DMs, only allow bot owner
        if not ctx.guild:
            return await ctx.bot.is_owner(ctx.author)
        
        # In guilds, check for administrator permission
        return ctx.author.guild_permissions.administrator
    
    return commands.check(predicate)

class OllamaManager(commands.Cog):
    def __init__(self, bot, ollama_client: OllamaClient):
        self.bot = bot
        self.ollama = ollama_client
        
        logger.info("OllamaManager cog initialized")

    @commands.command(name='ollama_status', help='Show Ollama service status and health')
    @is_admin_or_owner()
    async def ollama_status(self, ctx):
        """Show comprehensive Ollama service status"""
        try:
            # Perform health check
            async with ctx.typing():
                is_healthy = await self.ollama.health_check()
                status = self.ollama.get_health_status()
                
                # Get available models
                models = await self.ollama.list_models()
                
            embed = discord.Embed(
                title="🤖 Ollama Service Status", 
                color=0x00ff00 if is_healthy else 0xff0000
            )
            
            # Basic status
            embed.add_field(
                name="Service Health", 
                value="✅ Healthy" if is_healthy else "❌ Unhealthy", 
                inline=True
            )
            embed.add_field(name="Base URL", value=status['base_url'], inline=True)
            embed.add_field(name="Current Model", value=f"`{status['current_model']}`", inline=True)
            
            # Last health check
            if status['last_check']:
                last_check = datetime.fromisoformat(status['last_check'])
                embed.add_field(
                    name="Last Health Check", 
                    value=f"<t:{int(last_check.timestamp())}:R>", 
                    inline=True
                )
            
            # Available models
            if models:
                model_list = []
                for model in models[:10]:  # Show first 10 models
                    name = model.get('name', 'Unknown')
                    size = model.get('size', 0)
                    size_gb = size / (1024**3) if size > 0 else 0
                    
                    # Mark current model
                    marker = " 🔷" if name == status['current_model'] else ""
                    model_list.append(f"• `{name}`{marker} ({size_gb:.1f}GB)")
                
                if len(models) > 10:
                    model_list.append(f"• ... and {len(models) - 10} more")
                    
                embed.add_field(
                    name=f"Available Models ({len(models)})",
                    value="\n".join(model_list) if model_list else "No models found",
                    inline=False
                )
            else:
                embed.add_field(name="Available Models", value="Unable to fetch models", inline=False)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in ollama_status command: {e}")
            await ctx.send(f"❌ Error checking Ollama status: {str(e)}")

    @commands.command(name='ollama_models', help='List all available Ollama models')
    @is_admin_or_owner()
    async def list_models(self, ctx):
        """List all available models with details"""
        try:
            async with ctx.typing():
                models = await self.ollama.list_models()
                
            if not models:
                await ctx.send("❌ No models found or unable to connect to Ollama service.")
                return
                
            embed = discord.Embed(title="🤖 Available Ollama Models", color=0x0099ff)
            
            current_model = self.ollama.get_current_model()
            
            for i, model in enumerate(models):
                if i >= 20:  # Limit to 20 models to avoid embed limits
                    embed.add_field(
                        name="Note", 
                        value=f"Showing first 20 of {len(models)} models", 
                        inline=False
                    )
                    break
                    
                name = model.get('name', 'Unknown')
                size = model.get('size', 0)
                modified = model.get('modified_at', '')
                
                size_gb = size / (1024**3) if size > 0 else 0
                status_marker = "🔷 **CURRENT**" if name == current_model else ""
                
                # Format modified date
                try:
                    if modified:
                        mod_date = datetime.fromisoformat(modified.replace('Z', '+00:00'))
                        mod_str = f"<t:{int(mod_date.timestamp())}:R>"
                    else:
                        mod_str = "Unknown"
                except:
                    mod_str = "Unknown"
                
                embed.add_field(
                    name=f"`{name}` {status_marker}",
                    value=f"Size: {size_gb:.1f}GB\nModified: {mod_str}",
                    inline=True
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            await ctx.send(f"❌ Error listing models: {str(e)}")

    @commands.command(name='ollama_model', help='Change the current Ollama model')
    @is_admin_or_owner()
    async def change_model(self, ctx, model_name: str = None):
        """Change the current model or show current model"""
        try:
            if model_name is None:
                current = self.ollama.get_current_model()
                embed = discord.Embed(title="🤖 Current Ollama Model", color=0x0099ff)
                embed.add_field(name="Active Model", value=f"`{current}`", inline=False)
                embed.set_footer(text="Usage: !ollama_model <model_name>")
                await ctx.send(embed=embed)
                return
            
            # Test the model first
            async with ctx.typing():
                is_available = await self.ollama.test_model(model_name)
                
            if not is_available:
                await ctx.send(f"❌ Model `{model_name}` is not available or failed testing.")
                return
            
            # Change the model
            old_model = self.ollama.get_current_model()
            success = self.ollama.set_model(model_name)
            
            if success:
                embed = discord.Embed(title="✅ Model Changed Successfully", color=0x00ff00)
                embed.add_field(name="Previous Model", value=f"`{old_model}`", inline=True)
                embed.add_field(name="New Model", value=f"`{model_name}`", inline=True)
                embed.set_footer(text="All Ollama-powered features will now use this model")
                await ctx.send(embed=embed)
                
                # Notify other cogs about model change
                logger.info(f"Model changed from {old_model} to {model_name} by {ctx.author}")
            else:
                await ctx.send(f"❌ Failed to change model to `{model_name}`.")
                
        except Exception as e:
            logger.error(f"Error changing model: {e}")
            await ctx.send(f"❌ Error changing model: {str(e)}")

    @commands.command(name='ollama_test', help='Test a specific model')
    @is_admin_or_owner()
    async def test_model(self, ctx, model_name: str):
        """Test if a specific model is working"""
        try:
            async with ctx.typing():
                is_working = await self.ollama.test_model(model_name)
                
            if is_working:
                embed = discord.Embed(title="✅ Model Test Successful", color=0x00ff00)
                embed.add_field(name="Model", value=f"`{model_name}`", inline=False)
                embed.add_field(name="Status", value="Model is available and responding", inline=False)
            else:
                embed = discord.Embed(title="❌ Model Test Failed", color=0xff0000)
                embed.add_field(name="Model", value=f"`{model_name}`", inline=False)
                embed.add_field(name="Status", value="Model is not available or not responding", inline=False)
                
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error testing model {model_name}: {e}")
            await ctx.send(f"❌ Error testing model: {str(e)}")

    @commands.command(name='ollama_chat', help='Direct chat with Ollama')
    @is_admin_or_owner()
    async def direct_chat(self, ctx, *, prompt: str):
        """Direct chat interface with Ollama for testing"""
        try:
            async with ctx.typing():
                response = await self.ollama.simple_chat(
                    prompt=prompt,
                    system_prompt="You are a helpful AI assistant. Keep responses concise and friendly."
                )
                
            if response:
                # Truncate long responses for Discord
                if len(response) > 1900:
                    response = response[:1900] + "..."
                    
                embed = discord.Embed(title="🤖 Ollama Response", color=0x0099ff)
                embed.add_field(name="Model", value=f"`{self.ollama.get_current_model()}`", inline=True)
                embed.add_field(name="Prompt", value=f"```{prompt[:100]}{'...' if len(prompt) > 100 else ''}```", inline=False)
                embed.add_field(name="Response", value=response, inline=False)
                
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ No response received from Ollama.")
                
        except Exception as e:
            logger.error(f"Error in direct chat: {e}")
            await ctx.send(f"❌ Error in direct chat: {str(e)}")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Handle errors specific to this cog"""
        if ctx.command and ctx.command.name.startswith('ollama_'):
            if isinstance(error, commands.CheckFailure):
                if not ctx.guild:
                    await ctx.send("❌ Only the bot owner can use Ollama management commands in DMs.")
                else:
                    await ctx.send("❌ You need Administrator permissions to use Ollama management commands.")
            else:
                logger.error(f"Error in Ollama command: {error}", exc_info=True) 
import discord
from discord.ext import commands # Still potentially useful for other bot structures, converters, etc.
from discord import app_commands # For slash commands
import os
import datetime
import asyncio # Keep for now, might be used by discord.py or other logic
import database
import blackjack_game

# 2. Configuration
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
# BOT_PREFIX is no longer needed for slash commands

if DISCORD_BOT_TOKEN is None:
    print("Error: DISCORD_BOT_TOKEN environment variable not set. Please set it and try again.")
    exit(1)

# 3. Bot Initialization
intents = discord.Intents.default()
# intents.message_content = True # Less critical for slash commands, but can be kept if other message handling is intended
intents.members = True          # Required to access member information (e.g., user profiles, roles)

# We use Client instead of commands.Bot if we are ONLY using slash commands and no prefix commands.
# However, commands.Bot is fine and provides more flexibility if we mix or add other features later.
# For this refactor, sticking with commands.Bot and adding a CommandTree.
bot = commands.Bot(command_prefix="UNUSED_PREFIX_SLASH_COMMANDS_ONLY", intents=intents) # command_prefix is not strictly needed but Bot requires it.

# Ensure a CommandTree is only created and assigned if one doesn't already exist.
# This can help prevent errors if the module is reloaded or parts are re-initialized,
# especially in some testing or plugin scenarios.
if not hasattr(bot, 'tree') or bot.tree is None:
    tree = app_commands.CommandTree(bot)
else:
    tree = bot.tree # Use the existing tree

# 4. Global Variables/State
active_games = {}  # Stores active blackjack games, mapping user_id to BlackjackGame instance

# 5. on_ready Event
@bot.event
async def on_ready():
    """Called when the bot is successfully connected to Discord and ready."""
    print(f"Bot '{bot.user.name}' is ready and connected to Discord.")
    print(f"User ID: {bot.user.id}")
    try:
        database.init_db()
        print("Database initialized successfully.")
        # Sync the command tree
        await tree.sync()
        print("Slash commands synced globally.")
    except Exception as e:
        print(f"Error during on_ready: {e}")


# 6. Commands
# Refactor existing commands to use @tree.command decorator

# Example of how 'daily' command will be refactored (actual change will be in a subsequent step)
# @tree.command(name="daily", description="Claim your daily currency reward.")
# async def daily_slash(interaction: discord.Interaction):
#     user_id = str(interaction.user.id)
#     # ... rest of the logic using interaction.response.send_message ...

# 6. Commands (Now App Commands)

@tree.command(name="daily", description="Claim your daily currency reward.")
async def daily_slash(interaction: discord.Interaction):
    """Allows users to claim a daily currency reward."""
    user_id = str(interaction.user.id)
    try:
        database.create_user_if_not_exists(user_id)

        daily_cooldown_minutes_str = database.get_setting('daily_cooldown_minutes')
        try:
            daily_cooldown_minutes = int(daily_cooldown_minutes_str)
        except (TypeError, ValueError):
            daily_cooldown_minutes = 120 # Default cooldown
            print(f"Warning: Could not parse 'daily_cooldown_minutes' ('{daily_cooldown_minutes_str}'). Using default {daily_cooldown_minutes} minutes.")

        last_claim_timestamp = database.get_last_daily_claim(user_id)

        if last_claim_timestamp:
            cooldown_duration = datetime.timedelta(minutes=daily_cooldown_minutes)
            current_time_utc = datetime.datetime.now(datetime.timezone.utc)

            if last_claim_timestamp.tzinfo is None: # Should be UTC from DB, but ensure awareness
                last_claim_timestamp = last_claim_timestamp.replace(tzinfo=datetime.timezone.utc)

            time_since_last_claim = current_time_utc - last_claim_timestamp

            if time_since_last_claim < cooldown_duration:
                remaining_time = cooldown_duration - time_since_last_claim
                total_seconds = int(remaining_time.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                
                remaining_time_str = ""
                if hours > 0: remaining_time_str += f"{hours} hour(s) "
                if minutes > 0: remaining_time_str += f"{minutes} minute(s) "
                if hours == 0 and minutes == 0: remaining_time_str += f"{seconds} second(s)"
                remaining_time_str = remaining_time_str.strip()

                await interaction.response.send_message(f"You have already claimed your daily reward. Try again in {remaining_time_str}.")
                return

        reward_amount = 200
        new_balance = database.update_user_currency(user_id, reward_amount)
        database.set_last_daily_claim(user_id, datetime.datetime.now(datetime.timezone.utc))

        await interaction.response.send_message(f"You claimed your daily {reward_amount} currency! Your new balance is {new_balance}.")
    except Exception as e:
        print(f"Error in /daily command: {e}")
        # Check if interaction is already responded to, otherwise send ephemeral
        if not interaction.response.is_done():
            await interaction.response.send_message("An error occurred while processing your daily claim. Please try again later.", ephemeral=True)
        else: # If already responded (e.g. defer), follow up
            await interaction.followup.send("An error occurred while processing your daily claim. Please try again later.", ephemeral=True)


@tree.command(name="set", description="Admin: Change bot settings (e.g., daily_cooldown).")
@app_commands.describe(
    key="The setting key to change (e.g., 'daily_cooldown').",
    value="The new value for the setting."
)
@app_commands.default_permissions(administrator=True) # Only admins can see/use by default
async def set_config_slash(interaction: discord.Interaction, key: str, value: str):
    """Allows administrators to change bot settings."""
    normalized_key = key.lower()

    if normalized_key == 'daily_cooldown':
        try:
            cooldown_minutes = int(value)
            if cooldown_minutes <= 0:
                await interaction.response.send_message("Invalid value. Cooldown must be a positive number of minutes.", ephemeral=True)
                return
            
            database.set_setting('daily_cooldown_minutes', str(cooldown_minutes))
            await interaction.response.send_message(f"Daily cooldown has been updated to {cooldown_minutes} minutes.")
        except ValueError:
            await interaction.response.send_message("Invalid value. Cooldown must be a number of minutes (e.g., '120').", ephemeral=True)
    else:
        await interaction.response.send_message("Invalid setting key. Currently supported: `daily_cooldown`", ephemeral=True)

# Old error handlers will be removed and replaced by a global app_command error handler later.
# @set_config.error ... (remove)

@tree.command(name="blackjack", description="Start a game of Blackjack with a specified bet.")
@app_commands.describe(bet_amount="The amount of currency to bet.")
async def blackjack_slash(interaction: discord.Interaction, bet_amount: int):
    """Starts a game of Blackjack with the specified bet amount."""
    user_id = str(interaction.user.id)
    database.create_user_if_not_exists(user_id)

    if user_id in active_games:
        await interaction.response.send_message("You already have an active game. Finish it before starting a new one.", ephemeral=True)
        return

    if bet_amount <= 0:
        await interaction.response.send_message("Bet amount must be a positive number.", ephemeral=True)
        return

    current_currency = database.get_user_currency(user_id)
    if current_currency < bet_amount:
        await interaction.response.send_message(f"You don't have enough currency. Your balance is {current_currency}.", ephemeral=True)
        return

    game = blackjack_game.BlackjackGame(bet_amount=bet_amount)
    active_games[user_id] = game
    database.update_user_currency(user_id, -bet_amount)

    game.start_deal()

    player_details = game.get_player_hand_details()
    dealer_details = game.get_dealer_hand_details(reveal_all=False)

    embed_color = discord.Color.green()
    embed = discord.Embed(title=f"Blackjack Game - Bet: {bet_amount}", color=embed_color)
    
    player_cards_str = ", ".join(player_details['cards'])
    embed.add_field(name=f"{interaction.user.display_name}'s Hand", value=f"{player_cards_str} (Value: {player_details['value']})", inline=False)

    if dealer_details['cards']:
        dealer_shown_card_str = dealer_details['cards'][0]
        dealer_value_str = f"(Showing: {dealer_details.get('value_one_card', 'N/A')})" if len(dealer_details['cards']) > 1 else ""
        embed.add_field(name="Dealer Shows", value=f"{dealer_shown_card_str} {dealer_value_str}", inline=False)
    else:
        embed.add_field(name="Dealer Shows", value="Error: No cards dealt to dealer?", inline=False)

    if game.outcome == 'player_blackjack':
        total_payout = bet_amount + (bet_amount * 1.5)
        database.update_user_currency(user_id, total_payout)
        embed.add_field(name="Result", value=f"Blackjack! You win {bet_amount * 1.5}!", inline=False)
        embed.description = f"Game Over. Your new balance: {database.get_user_currency(user_id)}"
        embed.color = discord.Color.gold()
        del active_games[user_id]
    elif game.outcome == 'push':
        database.update_user_currency(user_id, bet_amount)
        embed.add_field(name="Result", value="Push! Both you and the dealer have Blackjack.", inline=False)
        embed.description = f"Game Over. Your bet of {bet_amount} has been returned. Your balance: {database.get_user_currency(user_id)}"
        embed.color = discord.Color.light_grey()
        del active_games[user_id]
    elif game.is_game_over and game.status_message:
        if "Not enough cards" in game.status_message:
            database.update_user_currency(user_id, bet_amount)
            embed.description = f"Game could not start: {game.status_message}. Your bet was returned."
        else:
            embed.description = f"Game Over: {game.status_message}"
        embed.color = discord.Color.orange()
        if user_id in active_games: del active_games[user_id]
    else:
        embed.add_field(name="Your Turn", value="Use `/hit` or `/stand`", inline=False)

    await interaction.response.send_message(embed=embed)

# @blackjack.error ... (remove)

@tree.command(name="hit", description="Request another card in your Blackjack game.")
async def hit_slash(interaction: discord.Interaction):
    """Player requests another card in their active Blackjack game."""
    user_id = str(interaction.user.id)

    if user_id not in active_games or active_games[user_id] is None:
        await interaction.response.send_message("You don't have an active blackjack game. Start one with `/blackjack <bet_amount>`.", ephemeral=True)
        return

    game = active_games[user_id]

    if game.is_game_over:
        await interaction.response.send_message("This game is already over. Start a new one with `/blackjack <bet_amount>`.", ephemeral=True)
        return

    game.player_hit()

    player_details = game.get_player_hand_details()
    dealer_details = game.get_dealer_hand_details(reveal_all=game.is_game_over)

    embed = discord.Embed(title=f"Blackjack Game - Bet: {game.bet_amount}", color=discord.Color.blue())
    player_cards_str = ", ".join(player_details['cards'])
    embed.add_field(name=f"{interaction.user.display_name}'s Hand", value=f"{player_cards_str} (Value: {player_details['value']})", inline=False)

    if game.player_hand.is_busted():
        dealer_cards_str = ", ".join(dealer_details['cards'])
        embed.add_field(name="Dealer's Hand", value=f"{dealer_cards_str} (Value: {dealer_details['value']})", inline=False)
        embed.add_field(name="Result", value=f"You busted with {player_details['value']}! {game.status_message}", inline=False)
        embed.description = f"Game Over. Your new balance: {database.get_user_currency(user_id)}"
        embed.color = discord.Color.red()
        del active_games[user_id]
    else:
        if dealer_details['cards'] and not game.is_game_over:
            dealer_shown_card_str = dealer_details['cards'][0]
            dealer_value_str = f"(Showing: {dealer_details.get('value_one_card', 'N/A')})" if len(dealer_details['cards']) > 1 else ""
            embed.add_field(name="Dealer Shows", value=f"{dealer_shown_card_str} {dealer_value_str}", inline=False)
        else:
            embed.add_field(name="Dealer Shows", value="Waiting for player stand...", inline=False)
        embed.add_field(name="Your Turn", value="Use `/hit` or `/stand`", inline=False)

    await interaction.response.send_message(embed=embed)

@tree.command(name="stand", description="Stand with your current hand in Blackjack.")
async def stand_slash(interaction: discord.Interaction):
    """Player stands, dealer plays, and game concludes."""
    user_id = str(interaction.user.id)

    if user_id not in active_games or active_games[user_id] is None:
        await interaction.response.send_message("You don't have an active blackjack game. Start one with `/blackjack <bet_amount>`.", ephemeral=True)
        return

    game = active_games[user_id]

    if game.is_game_over: # Check if game already ended (e.g. player hit Stand multiple times)
        await interaction.response.send_message("This game is already over. Start a new one with `/blackjack <bet_amount>`.", ephemeral=True)
        return
    
    # Defer the response if dealer's play might take time, though it should be quick here.
    # await interaction.response.defer() # Optional, can use if processing takes >3s

    game.player_stand()

    bet_amount = game.bet_amount
    final_balance_message_part = ""
    embed_color = discord.Color.dark_gold()

    if game.outcome == 'player_wins':
        winnings = bet_amount * 2
        new_balance = database.update_user_currency(user_id, winnings)
        final_balance_message_part = f" Your new balance is {new_balance}."
        embed_color = discord.Color.green()
    elif game.outcome == 'push':
        new_balance = database.update_user_currency(user_id, bet_amount)
        final_balance_message_part = f" Your bet was returned. Your balance is {new_balance}."
        embed_color = discord.Color.light_grey()
    elif game.outcome == 'dealer_wins':
        current_balance = database.get_user_currency(user_id)
        final_balance_message_part = f" Your balance remains {current_balance}."
        embed_color = discord.Color.red()

    player_cards_info = game.get_player_hand_details()
    dealer_cards_info = game.get_dealer_hand_details(reveal_all=True)

    embed = discord.Embed(
        title=f"Blackjack Game Over - Bet: {bet_amount}",
        description=game.status_message,
        color=embed_color
    )
    
    player_cards_str = ", ".join(player_cards_info['cards'])
    embed.add_field(name=f"{interaction.user.display_name}'s Hand", value=f"{player_cards_str} (Value: {player_cards_info['value']})", inline=False)

    dealer_cards_str = ", ".join(dealer_cards_info['cards'])
    embed.add_field(name="Dealer's Hand", value=f"{dealer_cards_str} (Value: {dealer_cards_info['value']})", inline=False)
    
    result_message = game.status_message + final_balance_message_part
    embed.add_field(name="Result", value=result_message, inline=False)

    del active_games[user_id]
    
    # If deferred, use followup.send. Otherwise, response.send_message
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed)
    else:
        await interaction.response.send_message(embed=embed)

@tree.command(name="top", description="Displays the top 10 users with the most currency.")
async def top_users_slash(interaction: discord.Interaction):
    """Displays the top 10 users by currency."""
    try:
        top_users_data = database.get_top_users_by_currency(limit=10)

        if not top_users_data:
            await interaction.response.send_message("The leaderboard is currently empty or no users have currency.", ephemeral=True)
            return

        embed = discord.Embed(title="🏆 Top 10 Richest Users 🏆", color=discord.Color.gold())
        
        leaderboard_description = []
        for rank, (user_id_str, currency) in enumerate(top_users_data, start=1):
            display_name = f"User ID: {user_id_str}" # Default to User ID
            try:
                user_id_int = int(user_id_str)
                user = interaction.client.get_user(user_id_int) # More general than guild.get_member for global users
                if user:
                    display_name = user.display_name
                # else: user might not be cached or share a server. Fallback to ID is fine.
            except ValueError:
                # user_id_str is not a valid integer, should not happen with current DB schema
                print(f"Warning: Could not parse user_id '{user_id_str}' to int for leaderboard.")
            
            leaderboard_description.append(f"**{rank}.** {display_name} - `{currency}` currency")

        embed.description = "\n".join(leaderboard_description)
        
        # Add a footer (optional)
        embed.set_footer(text="See who's making bank!")

        await interaction.response.send_message(embed=embed)

    except Exception as e:
        print(f"Error in /top command: {e}")
        # Use the global error handler's logic for sending messages if possible, or send a generic one.
        if not interaction.response.is_done():
            await interaction.response.send_message("An error occurred while fetching the leaderboard.", ephemeral=True)
        else:
            await interaction.followup.send("An error occurred while fetching the leaderboard.", ephemeral=True)

# Global Error Handler for App Commands
@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Handles errors for all slash commands."""
    user_facing_error_message = "An unexpected error occurred. Please try again later."
    ephemeral_response = True # Most errors should be ephemeral to avoid clutter

    if isinstance(error, app_commands.CommandNotFound):
        user_facing_error_message = "Sorry, I don't recognize that command."
    elif isinstance(error, app_commands.MissingPermissions):
        user_facing_error_message = "You don't have the required permissions to use this command."
    # Removed problematic MissingRequiredArgument check due to AttributeErrors in test environment
    # It will fall into the more generic app_commands.AppCommandError or the final else block.
    elif isinstance(error, app_commands.CommandOnCooldown):
        user_facing_error_message = f"This command is on cooldown. Try again in {error.retry_after:.2f} seconds."
    elif isinstance(error, app_commands.CheckFailure): # General check failure
        user_facing_error_message = "You cannot use this command right now." # Or a more specific message if available from error
    elif isinstance(error, app_commands.CommandInvokeError):
        # This wraps the original error raised within the command
        original_error = error.original
        print(f"CommandInvokeError for command '{interaction.command.name if interaction.command else 'unknown'}': {original_error}")
        # You could have more specific handling for original_error types here
        # For example, if original_error is a custom exception you define for expected issues
        user_facing_error_message = f"An error occurred while executing the command: {original_error}"
        # For critical errors, you might want to log more details or make the response non-ephemeral
        # ephemeral_response = False 
    else:
        # For other app_commands errors or unhandled discord.py errors that get wrapped
        print(f"Unhandled AppCommandError for command '{interaction.command.name if interaction.command else 'unknown'}': {error}")

    # Try to send the error message
    try:
        if interaction.response.is_done():
            await interaction.followup.send(user_facing_error_message, ephemeral=ephemeral_response)
        else:
            await interaction.response.send_message(user_facing_error_message, ephemeral=ephemeral_response)
    except discord.errors.InteractionResponded:
        # If the interaction was already responded to (e.g. by a quick followup or an earlier error)
        # We can try to send a followup, but it might also fail if the initial response was ephemeral and this is too late.
        try:
            await interaction.followup.send(user_facing_error_message, ephemeral=True)
        except Exception as e:
            print(f"Failed to send followup error message after InteractionResponded: {e}")
    except Exception as e:
        print(f"Failed to send error message: {e}")

# 7. Main Execution Block
if __name__ == '__main__':
    # Optional: Initialize DB here as well for safety, though on_ready should handle it.
    # This ensures DB is ready even if commands are registered at import time and somehow access DB.
    try:
        print("Initializing database from main block...")
        database.init_db()
        print("Database initialized from main block.")
    except Exception as e:
        print(f"Error initializing database from main block: {e}")

    print(f"Starting bot with prefix '{BOT_PREFIX}'...")
    try:
        bot.run(DISCORD_BOT_TOKEN)
    except discord.LoginFailure:
        print("Error: Failed to log in to Discord. Please check your bot token.")
        exit(1)
    except Exception as e:
        print(f"An unexpected error occurred while running the bot: {e}")
        exit(1)

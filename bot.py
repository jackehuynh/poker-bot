import discord
from discord.ext import commands
import os
import datetime
import asyncio
import database
import blackjack_game

# 2. Configuration
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
BOT_PREFIX = "!"

if DISCORD_BOT_TOKEN is None:
    print("Error: DISCORD_BOT_TOKEN environment variable not set. Please set it and try again.")
    exit(1)

# 3. Bot Initialization
intents = discord.Intents.default()
intents.message_content = True  # Required to read message content for commands and potentially other features
intents.members = True          # Required to access member information (e.g., user profiles, roles)

bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)

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
    except Exception as e:
        print(f"Error initializing database: {e}")

# 6. Commands
@bot.command(name='daily')
async def daily(ctx):
    """Allows users to claim a daily currency reward."""
    print(f"[DAILY COMMAND DEBUG] ctx.author: {repr(ctx.author)}, ctx.author.id: {ctx.author.id}")
    user_id = str(ctx.author.id) # Ensure user_id is a string for database consistency
    try:
        database.create_user_if_not_exists(user_id)

        daily_cooldown_minutes_str = database.get_setting('daily_cooldown_minutes')
        try:
            daily_cooldown_minutes = int(daily_cooldown_minutes_str)
        except (TypeError, ValueError):
            daily_cooldown_minutes = 120 # Default cooldown if setting is invalid or not found
            print(f"Warning: Could not parse 'daily_cooldown_minutes' setting ('{daily_cooldown_minutes_str}'). Using default {daily_cooldown_minutes} minutes.")

        last_claim_timestamp = database.get_last_daily_claim(user_id) # Expected to be datetime object or None

        if last_claim_timestamp:
            # Ensure last_claim_timestamp is offset-aware (UTC) if it's naive, for correct comparison
            # Assuming database stores it as UTC directly from datetime.utcnow()
            # If it were naive, it would need: last_claim_timestamp = last_claim_timestamp.replace(tzinfo=datetime.timezone.utc)
            
            cooldown_duration = datetime.timedelta(minutes=daily_cooldown_minutes)
            current_time_utc = datetime.datetime.now(datetime.timezone.utc) # Use timezone-aware current time

            # If last_claim_timestamp is naive, make it aware (assuming it's UTC)
            if last_claim_timestamp.tzinfo is None:
                last_claim_timestamp = last_claim_timestamp.replace(tzinfo=datetime.timezone.utc)

            time_since_last_claim = current_time_utc - last_claim_timestamp

            if time_since_last_claim < cooldown_duration:
                remaining_time = cooldown_duration - time_since_last_claim
                
                # Formatting remaining_time
                total_seconds = int(remaining_time.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                
                remaining_time_str = ""
                if hours > 0:
                    remaining_time_str += f"{hours} hour(s) "
                if minutes > 0:
                    remaining_time_str += f"{minutes} minute(s) "
                if hours == 0 and minutes == 0 : # Show seconds only if less than a minute remaining
                     remaining_time_str += f"{seconds} second(s)"
                remaining_time_str = remaining_time_str.strip()

                await ctx.send(f"You have already claimed your daily reward. Try again in {remaining_time_str}.")
                return

        # Reward logic
        reward_amount = 200  # Define the reward amount
        new_balance = database.update_user_currency(user_id, reward_amount)
        database.set_last_daily_claim(user_id, datetime.datetime.now(datetime.timezone.utc)) # Store as UTC

        await ctx.send(f"You claimed your daily {reward_amount} currency! Your new balance is {new_balance}.")
    except Exception as e:
        print(f"Error in !daily command during database operation: {e}")
        await ctx.send("An error occurred while processing your daily claim. Please try again later.")

@bot.command(name='set')
@commands.has_permissions(administrator=True)
async def set_config(ctx, key: str, value: str):
    """Allows administrators to change bot settings. Currently supports 'daily_cooldown'."""
    key = key.lower() # Case-insensitive key matching

    if key == 'daily_cooldown':
        try:
            cooldown_minutes = int(value)
            if cooldown_minutes <= 0:
                await ctx.send("Invalid value. Cooldown must be a positive number of minutes.")
                return
            
            database.set_setting('daily_cooldown_minutes', str(cooldown_minutes)) # Store as string
            await ctx.send(f"Daily cooldown has been updated to {cooldown_minutes} minutes.")
        except ValueError:
            await ctx.send("Invalid value. Cooldown must be a number of minutes (e.g., '120').")
    else:
        await ctx.send("Invalid setting key. Usage: `!set daily_cooldown <minutes>`")

@set_config.error
async def set_config_error(ctx, error):
    """Error handler for the !set command."""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You do not have permission to use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing argument: {error.param.name}. Usage: `!set <key> <value>` (e.g., `!set daily_cooldown 120`)")
    else:
        await ctx.send(f"An error occurred with the set command: {error}")
        print(f"Error in !set command: {error}") # Log other errors to console

@bot.command(name='blackjack', aliases=['bj'])
async def blackjack(ctx, bet_amount_str: str):
    """Starts a game of Blackjack with the specified bet amount."""
    user_id = str(ctx.author.id) # Ensure user_id is a string
    database.create_user_if_not_exists(user_id)

    if user_id in active_games:
        await ctx.send("You already have an active game. Finish it before starting a new one.")
        return

    try:
        bet_amount = int(bet_amount_str)
    except ValueError:
        await ctx.send("Invalid bet amount. Please enter a number.")
        return

    if bet_amount <= 0:
        await ctx.send("Bet amount must be a positive number.")
        return

    current_currency = database.get_user_currency(user_id)
    if current_currency < bet_amount:
        await ctx.send(f"You don't have enough currency. Your balance is {current_currency}.")
        return

    # Start game
    game = blackjack_game.BlackjackGame(bet_amount=bet_amount)
    active_games[user_id] = game
    database.update_user_currency(user_id, -bet_amount) # Deduct bet

    game.start_deal() # Deals cards

    player_details = game.get_player_hand_details()
    dealer_details = game.get_dealer_hand_details(reveal_all=False)

    embed_color = discord.Color.green()
    embed = discord.Embed(title=f"Blackjack Game - Bet: {bet_amount}", color=embed_color)
    
    player_cards_str = ", ".join(player_details['cards'])
    embed.add_field(name=f"{ctx.author.display_name}'s Hand", value=f"{player_cards_str} (Value: {player_details['value']})", inline=False)

    if dealer_details['cards']: # Ensure dealer has cards to show
        dealer_shown_card_str = dealer_details['cards'][0] # First card is visible
        dealer_value_str = f"(Showing: {dealer_details.get('value_one_card', 'N/A')})" if len(dealer_details['cards']) > 1 else "" # Value of shown card
        embed.add_field(name="Dealer Shows", value=f"{dealer_shown_card_str} {dealer_value_str}", inline=False)
    else:
        embed.add_field(name="Dealer Shows", value="Error: No cards dealt to dealer?", inline=False)


    # Check for Blackjack on deal (natural 21)
    # game.outcome is set to 'player_blackjack' in game.start_deal() if player has blackjack
    if game.outcome == 'player_blackjack':
        # Payout for Blackjack is typically 3:2, meaning player gets 1.5x their bet IN ADDITION to their original bet back.
        # So, total received is original_bet + 1.5 * original_bet = 2.5 * original_bet
        # Or, winnings are 1.5 * bet_amount. The bet is already deducted. So add bet_amount (to return it) + 1.5 * bet_amount (winnings)
        # Let's simplify to: bet is already taken. If win, player gets 2*bet. If BJ, player gets 2.5*bet.
        # For BJ, player should receive their original bet back + 1.5 times their bet as winnings.
        # Original bet was already deducted. So, refund bet + add 1.5 * bet. Total added to balance = 2.5 * bet_amount.
        # Standard Blackjack payout: Player wins 1.5 times their bet. The bet is returned.
        # Total received by player = bet + 1.5 * bet = 2.5 * bet.
        # Since bet was already deducted, we need to add back (bet + 1.5 * bet) = 2.5 * bet to their balance.
        
        # If game rules are simple "win double on BJ":
        # winnings_on_blackjack = bet_amount * 2 # Player wins their bet amount (total 2*bet in pot)
        # database.update_user_currency(user_id, bet_amount + winnings_on_blackjack) # Return original bet + winnings

        # Let's use the common 3:2 payout for Blackjack. The player wins 1.5x their bet.
        # The original bet is already deducted. So, we give back the original bet + 1.5x the bet.
        total_payout = bet_amount + (bet_amount * 1.5) # bet_amount * 2.5
        database.update_user_currency(user_id, total_payout)
        
        embed.add_field(name="Result", value=f"Blackjack! You win {bet_amount * 1.5}!", inline=False)
        embed.description = f"Game Over. Your new balance: {database.get_user_currency(user_id)}"
        embed.color = discord.Color.gold()
        del active_games[user_id]
    elif game.outcome == 'push': # Both player and dealer have Blackjack
        database.update_user_currency(user_id, bet_amount) # Return original bet
        embed.add_field(name="Result", value="Push! Both you and the dealer have Blackjack.", inline=False)
        embed.description = f"Game Over. Your bet of {bet_amount} has been returned. Your balance: {database.get_user_currency(user_id)}"
        embed.color = discord.Color.light_grey()
        del active_games[user_id]
    elif game.is_game_over and game.status_message: # Other game ending conditions from start_deal (e.g. not enough cards)
        # Bet should be returned if game couldn't start properly
        if "Not enough cards" in game.status_message:
            database.update_user_currency(user_id, bet_amount) # Return bet
            embed.description = f"Game could not start: {game.status_message}. Your bet was returned."
        else: # Unspecified game over from start_deal
            embed.description = f"Game Over: {game.status_message}"
        embed.color = discord.Color.orange()
        if user_id in active_games: # only delete if it was added
             del active_games[user_id]
    else:
        embed.add_field(name="Your Turn", value="Type `!hit` or `!stand`", inline=False)

    await ctx.send(embed=embed)

@blackjack.error
async def blackjack_error(ctx, error):
    """Error handler for the !blackjack command."""
    if isinstance(error, commands.MissingRequiredArgument):
        if error.param.name == 'bet_amount_str':
            await ctx.send("Usage: `!blackjack <bet_amount>` (e.g., `!blackjack 100`)")
    elif isinstance(error, commands.CommandInvokeError):
        await ctx.send(f"An error occurred while processing the blackjack command: {error.original}")
        print(f"Error in !blackjack command: {error.original}") # Log original error
    else:
        await ctx.send(f"An error occurred with the blackjack command: {error}")
        print(f"Error in !blackjack command: {error}")

@bot.command(name='hit')
async def hit(ctx):
    """Player requests another card in their active Blackjack game."""
    user_id = str(ctx.author.id)

    if user_id not in active_games or active_games[user_id] is None:
        await ctx.send("You don't have an active blackjack game. Start one with `!blackjack <bet_amount>`.")
        return

    game = active_games[user_id]

    if game.is_game_over:
        await ctx.send("This game is already over. Start a new one with `!blackjack <bet_amount>`.")
        return

    # Player Hit Logic
    game.player_hit() # This method updates game.is_game_over and game.outcome if player busts

    player_details = game.get_player_hand_details()
    # If game is over (e.g. player busted), reveal all dealer cards. Otherwise, don't.
    dealer_details = game.get_dealer_hand_details(reveal_all=game.is_game_over)

    embed = discord.Embed(title=f"Blackjack Game - Bet: {game.bet_amount}", color=discord.Color.blue())
    
    player_cards_str = ", ".join(player_details['cards'])
    embed.add_field(name=f"{ctx.author.display_name}'s Hand", value=f"{player_cards_str} (Value: {player_details['value']})", inline=False)

    # Outcome Processing
    if game.player_hand.is_busted(): # Equivalent to checking if game.outcome == 'dealer_wins' and game.status_message contains "bust"
        # game.player_hit() should have set outcome to 'dealer_wins' and status_message
        dealer_cards_str = ", ".join(dealer_details['cards'])
        embed.add_field(name="Dealer's Hand", value=f"{dealer_cards_str} (Value: {dealer_details['value']})", inline=False)
        embed.add_field(name="Result", value=f"You busted with {player_details['value']}! {game.status_message}", inline=False)
        embed.description = f"Game Over. Your new balance: {database.get_user_currency(user_id)}"
        embed.color = discord.Color.red()
        del active_games[user_id]
    else: # Player not busted
        # Dealer details should be for one card shown if game is not over
        if dealer_details['cards'] and not game.is_game_over : # Check if cards exist and game not over
             dealer_shown_card_str = dealer_details['cards'][0]
             dealer_value_str = f"(Showing: {dealer_details.get('value_one_card', 'N/A')})" if len(dealer_details['cards']) > 1 else ""
             embed.add_field(name="Dealer Shows", value=f"{dealer_shown_card_str} {dealer_value_str}", inline=False)
        else: # Should not happen if game.is_game_over is false, but as a fallback
             embed.add_field(name="Dealer Shows", value="Waiting for player stand...", inline=False)
        embed.add_field(name="Your Turn", value="Type `!hit` or `!stand`", inline=False)

    await ctx.send(embed=embed)

@bot.command(name='stand', aliases=['hold'])
async def stand(ctx):
    """Player stands, dealer plays, and game concludes."""
    user_id = str(ctx.author.id)

    if user_id not in active_games or active_games[user_id] is None:
        await ctx.send("You don't have an active blackjack game. Start one with `!blackjack <bet_amount>`.")
        return

    game = active_games[user_id]

    if game.is_game_over:
        await ctx.send("This game is already over or stand has been called. Start a new one with `!blackjack <bet_amount>`.")
        return

    # Player Stand Logic
    game.player_stand() # This method triggers dealer's play and sets game.outcome, game.status_message, game.is_game_over

    bet_amount = game.bet_amount
    final_balance_message_part = ""
    embed_color = discord.Color.dark_gold() # Default color as per spec

    if game.outcome == 'player_wins':
        winnings = bet_amount * 2  # Player receives their original bet back + an equal amount as winnings
        new_balance = database.update_user_currency(user_id, winnings)
        final_balance_message_part = f" Your new balance is {new_balance}."
        embed_color = discord.Color.green()
    elif game.outcome == 'push':
        new_balance = database.update_user_currency(user_id, bet_amount) # Return original bet
        final_balance_message_part = f" Your bet was returned. Your balance is {new_balance}."
        embed_color = discord.Color.light_grey() # Or discord.Color.greyple()
    elif game.outcome == 'dealer_wins':
        # No currency change needed, bet was already taken.
        current_balance = database.get_user_currency(user_id)
        final_balance_message_part = f" Your balance remains {current_balance}."
        embed_color = discord.Color.red()
    # Note: 'player_blackjack' outcome is handled in !blackjack command itself.

    player_cards_info = game.get_player_hand_details()
    dealer_cards_info = game.get_dealer_hand_details(reveal_all=True) # Game is over, reveal all

    # Construct embed message
    embed = discord.Embed(
        title=f"Blackjack Game Over - Bet: {bet_amount}",
        description=game.status_message, # Initial description from game logic
        color=embed_color
    )
    
    player_cards_str = ", ".join(player_cards_info['cards'])
    embed.add_field(name="Your Hand", value=f"{player_cards_str} (Value: {player_cards_info['value']})", inline=False)

    dealer_cards_str = ", ".join(dealer_cards_info['cards'])
    embed.add_field(name="Dealer's Hand", value=f"{dealer_cards_str} (Value: {dealer_cards_info['value']})", inline=False)
    
    result_message = game.status_message + final_balance_message_part
    # Overwrite description if we want it combined, or use a specific field for result.
    # Current spec: embed.add_field(name="Result", value=result_message, inline=False)
    # This means game.status_message in the initial embed description is fine.
    # Let's use the Result field for the combined message.
    embed.add_field(name="Result", value=result_message, inline=False)


    # Finalize Game
    del active_games[user_id]

    await ctx.send(embed=embed)


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

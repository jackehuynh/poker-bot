import unittest
from unittest.mock import Mock, patch, AsyncMock, call
import asyncio
import datetime
import os

# Modules to be tested or used in testing
import sys
# Ensure the bot's directory is in the path to import bot and database
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import bot
import database
import blackjack_game # Added for blackjack tests
import discord # Added for discord.Color

from discord.ext import commands

# Helper to run async functions in tests
def async_test(coro):
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro(*args, **kwargs))
        finally:
            loop.close()
    return wrapper

class TestBotCommands(unittest.TestCase):

    @patch('discord.client.Client.login', return_value=None)
    @patch('discord.ext.commands.Bot.run', return_value=None)
    def setUp(self, mock_bot_run, mock_client_login):
        # Initialize the bot. Bot initialization might try to log in or run.
        self.bot_instance = bot.bot
        
        # Mock bot.user which is used in on_ready
        self.bot_instance.user = Mock()
        self.bot_instance.user.name = "TestBot"
        self.bot_instance.user.id = "123456789"

        # Initialize the database to use an in-memory SQLite database for tests
        # This ensures that each test run starts with a clean database
        database.init_db(db_name_override=":memory:")
        
        # It's good practice to also run on_ready if it does setup like DB init,
        # but our bot's on_ready also prints, so we might want to control that.
        # For now, init_db is called directly. If on_ready had more logic,
        # we might call it: asyncio.run(self.bot_instance.on_ready())
        # but it also prints, so we might need to patch 'print' for on_ready specifically.

    def tearDown(self):
        # If we were using a file-based database, we'd clean it up here.
        # e.g., if database.init_db("test_bot.db") was used:
        # if os.path.exists("test_bot.db"):
        #     os.remove("test_bot.db")
        # For ":memory:", SQLite handles cleanup automatically when the connection is closed.
        # We might want to explicitly close the connection if database module exposes it.
        database.close_db_connection() # Ensure connection is closed and reset for next test

    @async_test
    @patch('builtins.print') # To capture debug prints
    async def test_daily_command_multiple_calls(self, mock_print):
        ctx = AsyncMock(spec=commands.Context)
        ctx.author = Mock(spec=discord.User)
        ctx.author.id = "test_user_1"
        ctx.author.display_name = "Test User 1"
        ctx.send = AsyncMock()

        # --- First call ---
        await self.bot_instance.get_command('daily').invoke(ctx)
        ctx.send.assert_called_once_with("You claimed your daily 200 currency! Your new balance is 200.")
        
        # Check debug log for first call
        # The print statement is: print(f"[DAILY COMMAND DEBUG] ctx.author: {repr(ctx.author)}, ctx.author.id: {ctx.author.id}")
        # So we expect a call containing `ctx.author.id` which is "test_user_1"
        found_debug_log_first_call = False
        for print_call in mock_print.call_args_list:
            args, _ = print_call
            if args and "[DAILY COMMAND DEBUG]" in args[0] and "test_user_1" in args[0]:
                found_debug_log_first_call = True
                break
        self.assertTrue(found_debug_log_first_call, "Debug log for first call not found or incorrect.")
        mock_print.reset_mock() # Reset for next part of the test

        # --- Second call (cooldown) ---
        ctx.send.reset_mock()
        await self.bot_instance.get_command('daily').invoke(ctx)
        # Default cooldown is 120 minutes.
        self.assertTrue("You have already claimed your daily reward. Try again in" in ctx.send.call_args[0][0])
        self.assertTrue("1 hour(s) 59 minute(s)" in ctx.send.call_args[0][0] or "2 hour(s)" in ctx.send.call_args[0][0]) # Check for ~2hrs

        # --- Simulate time passing ---
        # Default cooldown is 120 minutes (2 hours)
        # We need to mock datetime.datetime.now for this.
        # The bot uses datetime.datetime.now(datetime.timezone.utc)
        # and database.get_last_daily_claim returns a timezone-aware datetime object.
        
        # Get the current time as stored by the first daily claim.
        # This will be timezone-aware (UTC) as set by set_last_daily_claim.
        user_id_str = str(ctx.author.id)
        last_claim_time = database.get_last_daily_claim(user_id_str)
        self.assertIsNotNone(last_claim_time)

        # Mock datetime.now() to return a time that is past the cooldown.
        # Cooldown is 120 minutes. Add 121 minutes to be safe.
        future_time = last_claim_time + datetime.timedelta(minutes=121)
        
        with patch('datetime.datetime') as mock_date:
            mock_date.now.return_value = future_time
            mock_date.side_effect = lambda *args, **kw: datetime.datetime(*args, **kw) # Allow other datetime uses
            mock_date.timedelta = datetime.timedelta # Ensure timedelta still works

            # --- Third call (after cooldown) ---
            ctx.send.reset_mock()
            await self.bot_instance.get_command('daily').invoke(ctx)
            # Balance should be 200 (from first claim) + 200 (from this claim) = 400
            ctx.send.assert_called_once_with("You claimed your daily 200 currency! Your new balance is 400.")

            # Check debug log for third call
            found_debug_log_third_call = False
            for print_call in mock_print.call_args_list:
                args, _ = print_call
                if args and "[DAILY COMMAND DEBUG]" in args[0] and "test_user_1" in args[0]:
                    found_debug_log_third_call = True
                    break
            self.assertTrue(found_debug_log_third_call, "Debug log for third call not found or incorrect.")

    @async_test
    @patch('builtins.print') # To capture debug prints
    async def test_daily_command_ten_times_sequential(self, mock_print):
        ctx = AsyncMock(spec=commands.Context)
        ctx.author = Mock(spec=discord.User)
        ctx.author.id = "test_user_sequential"
        ctx.author.display_name = "Test User Sequential"
        ctx.send = AsyncMock()

        # Set cooldown to 0 minutes for this test.
        # We need an admin context to do this.
        admin_ctx = AsyncMock(spec=commands.Context)
        admin_ctx.author = Mock(spec=discord.Member) # Use Member for guild_permissions
        admin_ctx.author.id = "admin_user"
        admin_ctx.author.guild_permissions = Mock(spec=discord.Permissions)
        admin_ctx.author.guild_permissions.administrator = True
        admin_ctx.send = AsyncMock()
        
        set_command = self.bot_instance.get_command('set')
        await set_command.invoke(admin_ctx, key='daily_cooldown', value='0')
        admin_ctx.send.assert_called_with("Daily cooldown has been updated to 0 minutes.")

        expected_balance = 0
        for i in range(10):
            ctx.send.reset_mock()
            mock_print.reset_mock() # Reset print mock for each call to check specific debug log
            
            await self.bot_instance.get_command('daily').invoke(ctx)
            
            expected_balance += 200
            ctx.send.assert_called_once_with(f"You claimed your daily 200 currency! Your new balance is {expected_balance}.")
            
            # Verify debug log for this specific call
            found_debug_log_this_call = False
            # The call_args_list might have other prints if not reset properly or if other things print
            # We are interested in the latest calls to print for the current invoke
            for print_call in mock_print.call_args_list:
                args, _ = print_call
                if args and "[DAILY COMMAND DEBUG]" in args[0] and str(ctx.author.id) in args[0]:
                    # Check that the repr(ctx.author) part is also present
                    self.assertTrue(f"repr({ctx.author})" in args[0] or f"'{ctx.author.display_name}'" in args[0] or str(ctx.author) in args[0])
                    found_debug_log_this_call = True
                    break
            self.assertTrue(found_debug_log_this_call, f"Debug log for call {i+1} not found or incorrect.")

    @async_test
    async def test_set_daily_cooldown_command(self):
        ctx_admin = AsyncMock(spec=commands.Context)
        ctx_admin.author = Mock(spec=discord.Member) # Use Member for guild_permissions
        ctx_admin.author.id = "admin_user_set_test"
        ctx_admin.author.guild_permissions = Mock(spec=discord.Permissions)
        ctx_admin.author.guild_permissions.administrator = True
        ctx_admin.send = AsyncMock()

        set_command = self.bot_instance.get_command('set')

        # Test setting a valid cooldown
        await set_command.invoke(ctx_admin, key='daily_cooldown', value='60')
        ctx_admin.send.assert_called_once_with("Daily cooldown has been updated to 60 minutes.")
        self.assertEqual(database.get_setting('daily_cooldown_minutes'), '60')

        # Test setting an invalid value (non-numeric)
        ctx_admin.send.reset_mock()
        await set_command.invoke(ctx_admin, key='daily_cooldown', value='abc')
        ctx_admin.send.assert_called_once_with("Invalid value. Cooldown must be a number of minutes (e.g., '120').")

        # Test setting an invalid value (non-positive)
        ctx_admin.send.reset_mock()
        await set_command.invoke(ctx_admin, key='daily_cooldown', value='-10')
        ctx_admin.send.assert_called_once_with("Invalid value. Cooldown must be a positive number of minutes.")
        
        # Test setting an invalid value (zero)
        ctx_admin.send.reset_mock()
        await set_command.invoke(ctx_admin, key='daily_cooldown', value='0')
        ctx_admin.send.assert_called_once_with("Invalid value. Cooldown must be a positive number of minutes.")


        # Test with a non-admin user (should fail due to check)
        ctx_non_admin = AsyncMock(spec=commands.Context)
        ctx_non_admin.author = Mock(spec=discord.Member)
        ctx_non_admin.author.id = "non_admin_user"
        ctx_non_admin.author.guild_permissions = Mock(spec=discord.Permissions)
        ctx_non_admin.author.guild_permissions.administrator = False # Not an admin
        ctx_non_admin.send = AsyncMock()
        
        # We need to ensure the check itself is tested, not just the error handler.
        # The @commands.has_permissions decorator raises commands.MissingPermissions.
        # The test framework should invoke the command's error handler.
        # Let's register the error handler for the test bot instance.
        if not self.bot_instance.get_command('set').__cog_has_error_handler__(): # Check if error handler is present
             # Manually assign the error handler if not automatically picked up by test runner context
             # This is tricky as the decorator auto-assigns it.
             # Usually, invoking the command on the bot instance that has the handler registered is enough.
             pass


        # Check if the error handler is invoked
        # The actual check for permissions is done by discord.py before the command logic.
        # If MissingPermissions is raised, the set_config_error handler should be called.
        # We can test this by trying to invoke and expecting MissingPermissions to be handled.
        
        # Create a dummy error to simulate what the handler receives
        class MockMissingPermissions(commands.MissingPermissions):
            def __init__(self, missing_permissions):
                super().__init__(missing_permissions)

        # Patch the actual command logic to raise MissingPermissions to test the error handler path
        # This is a bit indirect. A better way is to invoke and let discord.py's machinery work.
        # The bot's error handler for set_config should be automatically wired up.
        # So, invoking the command with a non-admin context should trigger it.
        
        # Make sure the error handler is attached to the bot instance.
        # In normal operation, @command.error attaches it.
        # For testing, we might need to manually register or rely on bot instance.
        # Let's assume the bot instance is correctly set up with its error handlers.
        
        # The `invoke` method on a Command object bypasses some of the check dispatching
        # that `Bot.process_commands` would do.
        # To properly test permission checks handled by decorators and their error handlers,
        # it's often better to simulate a message event if possible, or to directly
        # call the error handler with a mocked error.

        # For now, let's check the behavior if the check was hypothetically bypassed and command was entered:
        # await set_command.invoke(ctx_non_admin, key='daily_cooldown', value='30')
        # This would try to run the command. But the decorator should prevent this.
        
        # Instead, let's test the error handler directly for coverage.
        error_handler = self.bot_instance.get_command('set').__dict__.get('_error_handler', None)
        if error_handler is None: # Try to get it from the bot's global error handlers if not on command
            for listener_name, funcs in self.bot_instance.extra_events.items():
                if listener_name == "on_command_error":
                    # This is more complex; set_config_error is specific to set_config
                    pass 
        # The error handler is set_config_error, which is a method on the cog (or global in this case)
        # Let's get the error handler directly from the bot object if it's registered there.
        # It seems the test runner or bot setup doesn't automatically connect command-specific error handlers
        # in the same way as a running bot.
        # So, we will call the error handler function directly.
        
        # If bot.py defines `async def set_config_error(ctx, error):` and it's correctly
        # associated with `set_config` command by `@set_config.error` decorator,
        # then `self.bot_instance.on_command_error` might eventually call it, or it's directly bound.
        # Let's assume it is directly bound for now.
        
        # Test the error handler for MissingPermissions
        mock_error_missing_perms = commands.MissingPermissions(['administrator'])
        # The error handler is `bot.set_config_error`
        await bot.set_config_error(ctx_non_admin, mock_error_missing_perms) # Call the actual error handler
        ctx_non_admin.send.assert_called_with("You do not have permission to use this command.")


        # Test error handler for MissingRequiredArgument
        ctx_admin.send.reset_mock() # Reset for admin context
        mock_error_missing_arg = commands.MissingRequiredArgument(Mock(name='value'))
        await bot.set_config_error(ctx_admin, mock_error_missing_arg) # Call the actual error handler
        ctx_admin.send.assert_called_once_with("Missing argument: value. Usage: `!set <key> <value>` (e.g., `!set daily_cooldown 120`)")

    # --- Blackjack Command Tests ---

    @async_test
    @patch('bot.blackjack_game.BlackjackGame')
    @patch('bot.database')
    async def test_blackjack_start_success(self, mock_db_bj, mock_blackjack_game_class):
        ctx = AsyncMock(spec=commands.Context)
        ctx.author = Mock(spec=discord.User)
        ctx.author.id = "bj_user_1"
        ctx.author.display_name = "BJ User 1"
        ctx.send = AsyncMock()

        mock_db_bj.get_user_currency.return_value = 500 # Has enough currency
        mock_db_bj.create_user_if_not_exists.return_value = None
        mock_db_bj.update_user_currency.return_value = 400 # After bet

        mock_game_instance = mock_blackjack_game_class.return_value
        mock_game_instance.bet_amount = 100
        mock_game_instance.outcome = None # Game ongoing
        mock_game_instance.is_game_over = False
        mock_game_instance.start_deal = Mock()
        mock_game_instance.get_player_hand_details.return_value = {'cards': ['A', '10'], 'value': 21}
        mock_game_instance.get_dealer_hand_details.return_value = {'cards': ['7', 'X'], 'value_one_card': 7}


        await self.bot_instance.get_command('blackjack').invoke(ctx, bet_amount_str="100")

        mock_db_bj.create_user_if_not_exists.assert_called_with(str(ctx.author.id))
        mock_db_bj.get_user_currency.assert_called_with(str(ctx.author.id))
        mock_blackjack_game_class.assert_called_with(bet_amount=100)
        mock_db_bj.update_user_currency.assert_called_with(str(ctx.author.id), -100)
        mock_game_instance.start_deal.assert_called_once()
        
        self.assertIn(str(ctx.author.id), bot.active_games)
        self.assertEqual(bot.active_games[str(ctx.author.id)], mock_game_instance)

        ctx.send.assert_called_once()
        embed_sent = ctx.send.call_args[1]['embed']
        self.assertEqual(embed_sent.title, "Blackjack Game - Bet: 100")
        self.assertTrue("BJ User 1's Hand" in embed_sent.fields[0].name)
        self.assertTrue("Dealer Shows" in embed_sent.fields[1].name)
        self.assertTrue("Type `!hit` or `!stand`" in embed_sent.fields[2].value)
        
        # Clean up active game for other tests
        del bot.active_games[str(ctx.author.id)]

    @async_test
    async def test_blackjack_already_active(self):
        ctx = AsyncMock(spec=commands.Context)
        ctx.author = Mock(spec=discord.User)
        ctx.author.id = "bj_user_active"
        ctx.send = AsyncMock()

        # Simulate an active game
        bot.active_games[str(ctx.author.id)] = Mock(spec=blackjack_game.BlackjackGame)

        await self.bot_instance.get_command('blackjack').invoke(ctx, bet_amount_str="50")
        ctx.send.assert_called_once_with("You already have an active game. Finish it before starting a new one.")
        
        # Clean up
        del bot.active_games[str(ctx.author.id)]

    @async_test
    @patch('bot.database')
    async def test_blackjack_insufficient_currency(self, mock_db_bj):
        ctx = AsyncMock(spec=commands.Context)
        ctx.author = Mock(spec=discord.User)
        ctx.author.id = "bj_user_poor"
        ctx.send = AsyncMock()

        mock_db_bj.get_user_currency.return_value = 20 # Not enough for bet of 100
        mock_db_bj.create_user_if_not_exists.return_value = None

        await self.bot_instance.get_command('blackjack').invoke(ctx, bet_amount_str="100")
        ctx.send.assert_called_once_with("You don't have enough currency. Your balance is 20.")
        self.assertNotIn(str(ctx.author.id), bot.active_games)

    @async_test
    async def test_blackjack_invalid_bet(self):
        ctx = AsyncMock(spec=commands.Context)
        ctx.author = Mock(spec=discord.User)
        ctx.author.id = "bj_user_invalid_bet"
        ctx.send = AsyncMock()

        # Test non-numeric bet
        await self.bot_instance.get_command('blackjack').invoke(ctx, bet_amount_str="abc")
        ctx.send.assert_called_once_with("Invalid bet amount. Please enter a number.")
        self.assertNotIn(str(ctx.author.id), bot.active_games)
        ctx.send.reset_mock()

        # Test non-positive bet (zero)
        await self.bot_instance.get_command('blackjack').invoke(ctx, bet_amount_str="0")
        ctx.send.assert_called_once_with("Bet amount must be a positive number.")
        self.assertNotIn(str(ctx.author.id), bot.active_games)
        ctx.send.reset_mock()

        # Test non-positive bet (negative)
        await self.bot_instance.get_command('blackjack').invoke(ctx, bet_amount_str="-50")
        ctx.send.assert_called_once_with("Bet amount must be a positive number.")
        self.assertNotIn(str(ctx.author.id), bot.active_games)

    @async_test
    @patch('bot.blackjack_game.BlackjackGame')
    @patch('bot.database')
    async def test_hit_success(self, mock_db_bj, mock_blackjack_game_class):
        ctx = AsyncMock(spec=commands.Context)
        user_id_str = "bj_user_hit"
        ctx.author = Mock(spec=discord.User, id=user_id_str, display_name="BJ Hit User")
        ctx.send = AsyncMock()

        mock_game_instance = Mock(spec=blackjack_game.BlackjackGame)
        mock_game_instance.is_game_over = False
        mock_game_instance.bet_amount = 50
        mock_game_instance.player_hand = Mock() # Mock player_hand to have is_busted
        mock_game_instance.player_hand.is_busted.return_value = False
        
        mock_game_instance.get_player_hand_details.return_value = {'cards': ['5', '6', '7'], 'value': 18}
        mock_game_instance.get_dealer_hand_details.return_value = {'cards': ['K', 'X'], 'value_one_card': 10}

        bot.active_games[user_id_str] = mock_game_instance

        await self.bot_instance.get_command('hit').invoke(ctx)

        mock_game_instance.player_hit.assert_called_once()
        ctx.send.assert_called_once()
        embed_sent = ctx.send.call_args[1]['embed']
        self.assertTrue("BJ Hit User's Hand" in embed_sent.fields[0].name)
        self.assertTrue("(Value: 18)" in embed_sent.fields[0].value)
        self.assertTrue("Type `!hit` or `!stand`" in embed_sent.fields[2].value) # Assuming not busted

        del bot.active_games[user_id_str] # Cleanup

    @async_test
    async def test_hit_no_active_game(self):
        ctx = AsyncMock(spec=commands.Context)
        ctx.author = Mock(spec=discord.User, id="bj_user_no_game_hit")
        ctx.send = AsyncMock()

        await self.bot_instance.get_command('hit').invoke(ctx)
        ctx.send.assert_called_once_with("You don't have an active blackjack game. Start one with `!blackjack <bet_amount>`.")

    @async_test
    async def test_hit_game_over(self):
        ctx = AsyncMock(spec=commands.Context)
        user_id_str = "bj_user_game_over_hit"
        ctx.author = Mock(spec=discord.User, id=user_id_str)
        ctx.send = AsyncMock()

        mock_game_instance = Mock(spec=blackjack_game.BlackjackGame)
        mock_game_instance.is_game_over = True # Game is already over
        bot.active_games[user_id_str] = mock_game_instance

        await self.bot_instance.get_command('hit').invoke(ctx)
        ctx.send.assert_called_once_with("This game is already over. Start a new one with `!blackjack <bet_amount>`.")
        del bot.active_games[user_id_str]

    @async_test
    @patch('bot.database') # Mock database for get_user_currency on bust
    @patch('bot.blackjack_game.BlackjackGame') # To control game instance behavior
    async def test_hit_player_busts(self, mock_blackjack_game_class, mock_db_bj_bust):
        ctx = AsyncMock(spec=commands.Context)
        user_id_str = "bj_user_bust"
        ctx.author = Mock(spec=discord.User, id=user_id_str, display_name="BJ Bust User")
        ctx.send = AsyncMock()

        mock_game_instance = Mock(spec=blackjack_game.BlackjackGame)
        mock_game_instance.is_game_over = False # Initially false
        mock_game_instance.bet_amount = 25
        
        # Simulate player_hit leading to bust
        def simulate_bust_on_hit():
            mock_game_instance.is_game_over = True
            mock_game_instance.outcome = 'dealer_wins' # Or similar, based on game logic
            mock_game_instance.status_message = "You busted!"
            mock_game_instance.player_hand.is_busted.return_value = True # Make sure this is true

        mock_game_instance.player_hit = Mock(side_effect=simulate_bust_on_hit)
        mock_game_instance.player_hand = Mock()
        mock_game_instance.player_hand.is_busted.return_value = False # Before hit
        
        mock_game_instance.get_player_hand_details.return_value = {'cards': ['10', '8', '7'], 'value': 25} # Busted hand
        mock_game_instance.get_dealer_hand_details.return_value = {'cards': ['Q', 'X'], 'value': 0} # Dealer hand irrelevant or simple

        mock_db_bj_bust.get_user_currency.return_value = 100 # For final balance message

        bot.active_games[user_id_str] = mock_game_instance

        await self.bot_instance.get_command('hit').invoke(ctx)

        mock_game_instance.player_hit.assert_called_once()
        ctx.send.assert_called_once()
        embed_sent = ctx.send.call_args[1]['embed']
        
        self.assertTrue("You busted with 25!" in embed_sent.fields[2].value) # Check result field
        self.assertTrue(f"Game Over. Your new balance: 100" in embed_sent.description)
        self.assertNotIn(user_id_str, bot.active_games) # Game should be removed


    @async_test
    async def test_stand_no_active_game(self):
        ctx = AsyncMock(spec=commands.Context)
        ctx.author = Mock(spec=discord.User, id="bj_user_no_game_stand")
        ctx.send = AsyncMock()

        await self.bot_instance.get_command('stand').invoke(ctx)
        ctx.send.assert_called_once_with("You don't have an active blackjack game. Start one with `!blackjack <bet_amount>`.")

    @async_test
    async def test_stand_game_already_over(self):
        ctx = AsyncMock(spec=commands.Context)
        user_id_str = "bj_user_game_over_stand"
        ctx.author = Mock(spec=discord.User, id=user_id_str)
        ctx.send = AsyncMock()

        mock_game_instance = Mock(spec=blackjack_game.BlackjackGame)
        mock_game_instance.is_game_over = True # Game is already over
        bot.active_games[user_id_str] = mock_game_instance

        await self.bot_instance.get_command('stand').invoke(ctx)
        # The message for stand when game is_game_over is slightly different in bot.py:
        # "This game is already over or stand has been called."
        self.assertIn("This game is already over", ctx.send.call_args[0][0])
        del bot.active_games[user_id_str]

    @async_test
    @patch('bot.database')
    @patch('bot.blackjack_game.BlackjackGame') # Mock the class to control instance
    async def test_stand_outcomes(self, mock_blackjack_game_class, mock_db_bj_stand):
        ctx = AsyncMock(spec=commands.Context)
        user_id_str = "bj_user_stand_outcomes"
        ctx.author = Mock(spec=discord.User, id=user_id_str, display_name="BJ Stand User")
        ctx.send = AsyncMock()

        outcomes_to_test = {
            'player_wins': {'winnings_factor': 2, 'db_balance_after_win': 200, 'color': discord.Color.green()},
            'dealer_wins': {'winnings_factor': 0, 'db_balance_after_win': 0, 'color': discord.Color.red()}, # Bet already deducted
            'push': {'winnings_factor': 1, 'db_balance_after_win': 100, 'color': discord.Color.light_grey()}
        }
        initial_bet = 100
        
        for outcome_name, outcome_details in outcomes_to_test.items():
            with self.subTest(outcome=outcome_name):
                # Reset mocks for each sub-test
                mock_db_bj_stand.reset_mock()
                ctx.send.reset_mock()
                
                # Setup active game
                # We need a fresh mock instance for each subtest to reset its state
                mock_game_instance = Mock(spec=blackjack_game.BlackjackGame)
                mock_game_instance.bet_amount = initial_bet
                mock_game_instance.is_game_over = False # Game is active

                # Configure database mocks
                # update_user_currency is called with (user_id, winnings_amount)
                # get_user_currency is called if dealer wins to show final balance
                if outcome_name == 'player_wins':
                    mock_db_bj_stand.update_user_currency.return_value = outcome_details['db_balance_after_win'] # New balance
                elif outcome_name == 'push':
                    mock_db_bj_stand.update_user_currency.return_value = outcome_details['db_balance_after_win'] # New balance
                elif outcome_name == 'dealer_wins':
                    mock_db_bj_stand.get_user_currency.return_value = outcome_details['db_balance_after_win'] # Current balance (no change)


                # Mock player_stand behavior
                def simulate_stand():
                    mock_game_instance.is_game_over = True
                    mock_game_instance.outcome = outcome_name
                    mock_game_instance.status_message = f"Game result: {outcome_name}"
                
                mock_game_instance.player_stand = Mock(side_effect=simulate_stand)
                mock_game_instance.get_player_hand_details.return_value = {'cards': ['10', '9'], 'value': 19}
                mock_game_instance.get_dealer_hand_details.return_value = {'cards': ['10', '8'], 'value': 18}

                bot.active_games[user_id_str] = mock_game_instance

                await self.bot_instance.get_command('stand').invoke(ctx)

                mock_game_instance.player_stand.assert_called_once()
                
                if outcome_name == 'player_wins':
                    mock_db_bj_stand.update_user_currency.assert_called_with(user_id_str, initial_bet * 2)
                elif outcome_name == 'push':
                    mock_db_bj_stand.update_user_currency.assert_called_with(user_id_str, initial_bet)
                elif outcome_name == 'dealer_wins':
                    mock_db_bj_stand.get_user_currency.assert_called_with(user_id_str)
                    mock_db_bj_stand.update_user_currency.assert_not_called() # No update for dealer win after bet deduction

                ctx.send.assert_called_once()
                embed_sent = ctx.send.call_args[1]['embed']
                self.assertEqual(embed_sent.color, outcome_details['color'])
                self.assertTrue(f"Game result: {outcome_name}" in embed_sent.fields[2].value or f"Game result: {outcome_name}" in embed_sent.description)
                
                # Balance message check
                if outcome_name == 'player_wins':
                     self.assertTrue(f"Your new balance is {outcome_details['db_balance_after_win']}" in embed_sent.fields[2].value)
                elif outcome_name == 'push':
                    self.assertTrue(f"Your bet was returned. Your balance is {outcome_details['db_balance_after_win']}" in embed_sent.fields[2].value)
                elif outcome_name == 'dealer_wins':
                    self.assertTrue(f"Your balance remains {outcome_details['db_balance_after_win']}" in embed_sent.fields[2].value)

                self.assertNotIn(user_id_str, bot.active_games) # Game should be removed

    @async_test
    @patch('bot.blackjack_game.BlackjackGame')
    @patch('bot.database')
    async def test_blackjack_ten_games_sequential(self, mock_db_bj, mock_blackjack_game_class):
        ctx = AsyncMock(spec=commands.Context)
        user_id_str = "bj_user_10_games"
        ctx.author = Mock(spec=discord.User, id=user_id_str, display_name="BJ Ten Gamer")
        ctx.send = AsyncMock()

        initial_currency = 1000
        bet_amount = 50

        for i in range(10):
            with self.subTest(game_number=i + 1):
                ctx.send.reset_mock() # Reset send mock for each game
                mock_db_bj.reset_mock() # Reset DB mock for each game
                
                # Ensure no active game from previous iteration if something failed to clean up
                if str(ctx.author.id) in bot.active_games:
                    del bot.active_games[str(ctx.author.id)]

                # --- !blackjack ---
                current_currency_for_check = initial_currency if i == 0 else mock_db_bj.get_user_currency.return_value
                mock_db_bj.get_user_currency.return_value = current_currency_for_check
                mock_db_bj.create_user_if_not_exists.return_value = None
                
                # Mock BlackjackGame instance for this game
                mock_game_instance_loop = mock_blackjack_game_class.return_value
                mock_game_instance_loop.bet_amount = bet_amount
                mock_game_instance_loop.outcome = None # Game ongoing
                mock_game_instance_loop.is_game_over = False
                mock_game_instance_loop.start_deal = Mock()
                mock_game_instance_loop.get_player_hand_details.return_value = {'cards': ['A', '7'], 'value': 18} # Player starts with 18
                mock_game_instance_loop.get_dealer_hand_details.return_value = {'cards': ['8', 'X'], 'value_one_card': 8} # Dealer shows 8

                await self.bot_instance.get_command('blackjack').invoke(ctx, bet_amount_str=str(bet_amount))
                
                mock_db_bj.create_user_if_not_exists.assert_called_with(user_id_str)
                mock_db_bj.get_user_currency.assert_called_with(user_id_str)
                mock_blackjack_game_class.assert_called_with(bet_amount=bet_amount)
                mock_db_bj.update_user_currency.assert_called_with(user_id_str, -bet_amount) # Bet deducted
                
                self.assertIn(user_id_str, bot.active_games)
                self.assertEqual(bot.active_games[user_id_str], mock_game_instance_loop)
                # Basic check for embed, more detailed in specific blackjack_start test
                ctx.send.assert_called_once() 
                sent_embed_bj = ctx.send.call_args[1]['embed']
                self.assertTrue("Type `!hit` or `!stand`" in sent_embed_bj.fields[2].value)
                ctx.send.reset_mock() # Reset for hit/stand

                # --- !stand (simplifying: player always stands with initial hand) ---
                # Configure outcome for this stand: cycle through win, lose, push for variety
                game_outcome_this_round = ['player_wins', 'dealer_wins', 'push'][i % 3]
                
                def simulate_stand_loop():
                    mock_game_instance_loop.is_game_over = True
                    mock_game_instance_loop.outcome = game_outcome_this_round
                    mock_game_instance_loop.status_message = f"Game {i+1} result: {game_outcome_this_round}"
                
                mock_game_instance_loop.player_stand = Mock(side_effect=simulate_stand_loop)
                # Update hand details for stand if necessary, though player stands on initial 18
                mock_game_instance_loop.get_player_hand_details.return_value = {'cards': ['A', '7'], 'value': 18} 
                # Dealer's final hand (e.g. dealer gets 17 or busts, depending on desired outcome)
                if game_outcome_this_round == 'player_wins': # e.g. dealer busts or has less
                    mock_game_instance_loop.get_dealer_hand_details.return_value = {'cards': ['8', 'K', 'J'], 'value': 28} # Dealer busts
                elif game_outcome_this_round == 'dealer_wins': # e.g. dealer has 20
                    mock_game_instance_loop.get_dealer_hand_details.return_value = {'cards': ['8', 'Q'], 'value': 18} # Dealer has 18, player has 18. This should be a push. Let's adjust.
                    # if player has 18, dealer gets 19 for dealer_wins
                    mock_game_instance_loop.get_dealer_hand_details.return_value = {'cards': ['8', 'A'], 'value': 19}
                else: # push, dealer also has 18
                    mock_game_instance_loop.get_dealer_hand_details.return_value = {'cards': ['8', 'K'], 'value': 18}


                # Mock database for stand outcome
                if game_outcome_this_round == 'player_wins':
                    # Previous balance was current_currency_for_check - bet_amount. New balance is that + 2*bet_amount
                    new_bal = current_currency_for_check - bet_amount + (2 * bet_amount)
                    mock_db_bj.update_user_currency.return_value = new_bal 
                elif game_outcome_this_round == 'push':
                     new_bal = current_currency_for_check # Bet returned
                     mock_db_bj.update_user_currency.return_value = new_bal
                else: # dealer_wins
                    new_bal = current_currency_for_check - bet_amount # Bet lost
                    mock_db_bj.get_user_currency.return_value = new_bal # For final balance message

                await self.bot_instance.get_command('stand').invoke(ctx)
                
                mock_game_instance_loop.player_stand.assert_called_once()
                ctx.send.assert_called_once() # Check stand embed
                sent_embed_stand = ctx.send.call_args[1]['embed']
                self.assertTrue(f"Game {i+1} result: {game_outcome_this_round}" in sent_embed_stand.fields[2].value)

                if game_outcome_this_round == 'player_wins':
                    mock_db_bj.update_user_currency.assert_called_with(user_id_str, bet_amount * 2)
                elif game_outcome_this_round == 'push':
                    mock_db_bj.update_user_currency.assert_called_with(user_id_str, bet_amount)
                
                self.assertNotIn(user_id_str, bot.active_games, f"Game {i+1} was not removed from active_games.")
                
                # Update currency for the next loop's check
                if game_outcome_this_round == 'player_wins':
                    initial_currency = initial_currency + bet_amount 
                elif game_outcome_this_round == 'dealer_wins':
                    initial_currency = initial_currency - bet_amount
                # For push, initial_currency remains same as bet is returned (after initial deduction)
                
                # Update mock for next get_user_currency call at start of loop
                mock_db_bj.get_user_currency.return_value = initial_currency


if __name__ == '__main__':
    unittest.main()
```

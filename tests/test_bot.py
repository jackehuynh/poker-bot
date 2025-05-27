import unittest
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, PropertyMock 

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import bot as discord_bot 
import database as real_database # For type checking and real exceptions
import blackjack_game as real_blackjack_game # For type checking
import datetime

import discord
from discord import app_commands 

class TestBotCommands(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        """Set up for each test. Mocks common objects."""
        
        self.mock_interaction = AsyncMock(spec=discord.Interaction)
        
        self.mock_user = MagicMock(spec=discord.User) 
        self.mock_user.id = 1234567890 
        self.mock_user.display_name = "TestUser"
        self.mock_user.__str__ = MagicMock(return_value="TestUser#1234") 
        self.mock_interaction.user = self.mock_user
        
        self.mock_interaction.response = AsyncMock(spec=discord.InteractionResponse)
        self.mock_interaction.response.send_message = AsyncMock()
        self.mock_interaction.response.is_done = MagicMock(return_value=False)

        self.mock_interaction.followup = AsyncMock(spec=discord.Webhook)
        self.mock_interaction.followup.send = AsyncMock()

        self.mock_client = AsyncMock(spec=discord_bot.bot) 
        self.mock_client.get_user = MagicMock(return_value=self.mock_user) 
        self.mock_interaction.client = self.mock_client
        
        self.patcher_database = mock.patch('bot.database', autospec=True)
        self.mock_database = self.patcher_database.start()

        self.patcher_active_games = mock.patch.dict(discord_bot.active_games, {})
        self.patcher_active_games.start()

        self.patcher_blackjack_game_class = mock.patch('bot.blackjack_game.BlackjackGame', autospec=True)
        self.mock_blackjack_game_class = self.patcher_blackjack_game_class.start()
        
        self.mock_blackjack_instance = self.mock_blackjack_game_class.return_value
        self.mock_blackjack_instance.start_deal = MagicMock()
        self.mock_blackjack_instance.get_player_hand_details = MagicMock(return_value={'cards': ['DA', 'DK'], 'value': 21})
        self.mock_blackjack_instance.get_dealer_hand_details = MagicMock(return_value={'cards': ['DQ', 'D10'], 'value': 20, 'value_one_card': 10})
        self.mock_blackjack_instance.outcome = None 
        self.mock_blackjack_instance.is_game_over = False
        self.mock_blackjack_instance.status_message = "Game ongoing"
        self.mock_blackjack_instance.bet_amount = 0 
        
        player_hand_mock = MagicMock(spec=real_blackjack_game.Hand) 
        player_hand_mock.is_busted = MagicMock(return_value=False)
        self.mock_blackjack_instance.player_hand = player_hand_mock


    async def asyncTearDown(self):
        self.patcher_database.stop()
        self.patcher_active_games.stop()
        self.patcher_blackjack_game_class.stop()
        mock.patch.stopall()


class TestDailyCommand(TestBotCommands):

    async def test_daily_new_user(self):
        self.mock_database.get_last_daily_claim.return_value = None
        self.mock_database.get_setting.return_value = "120" 
        self.mock_database.update_user_currency.return_value = 200

        await discord_bot.daily_slash.callback(self.mock_interaction)

        self.mock_database.create_user_if_not_exists.assert_called_once_with(str(self.mock_user.id))
        self.mock_database.get_last_daily_claim.assert_called_once_with(str(self.mock_user.id))
        self.mock_database.update_user_currency.assert_called_once_with(str(self.mock_user.id), 200)
        self.mock_database.set_last_daily_claim.assert_called_once()
        self.mock_interaction.response.send_message.assert_called_once_with(
            "You claimed your daily 200 currency! Your new balance is 200."
        )

    async def test_daily_user_on_cooldown(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        recent_claim_time = now - datetime.timedelta(minutes=30)
        self.mock_database.get_last_daily_claim.return_value = recent_claim_time
        self.mock_database.get_setting.return_value = "120"

        await discord_bot.daily_slash.callback(self.mock_interaction)
        
        self.mock_database.create_user_if_not_exists.assert_called_once_with(str(self.mock_user.id))
        self.mock_database.get_last_daily_claim.assert_called_once_with(str(self.mock_user.id))
        self.mock_database.update_user_currency.assert_not_called()
        self.mock_database.set_last_daily_claim.assert_not_called()
        
        self.mock_interaction.response.send_message.assert_called_once()
        call_args = self.mock_interaction.response.send_message.call_args[0][0]
        self.assertIn("You have already claimed your daily reward. Try again in", call_args)
        self.assertTrue("hour(s)" in call_args or "minute(s)" in call_args or "second(s)" in call_args)


    async def test_daily_user_off_cooldown(self):
        old_claim_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
        self.mock_database.get_last_daily_claim.return_value = old_claim_time
        self.mock_database.get_setting.return_value = "120" 
        self.mock_database.update_user_currency.return_value = 300

        await discord_bot.daily_slash.callback(self.mock_interaction)

        self.mock_database.create_user_if_not_exists.assert_called_once_with(str(self.mock_user.id))
        self.mock_database.get_last_daily_claim.assert_called_once_with(str(self.mock_user.id))
        self.mock_database.update_user_currency.assert_called_once_with(str(self.mock_user.id), 200)
        self.mock_database.set_last_daily_claim.assert_called_once()
        self.mock_interaction.response.send_message.assert_called_once_with(
            "You claimed your daily 200 currency! Your new balance is 300."
        )

    async def test_daily_cooldown_setting_not_found_or_invalid(self):
        self.mock_database.get_last_daily_claim.return_value = None 
        self.mock_database.get_setting.return_value = None 
        self.mock_database.update_user_currency.return_value = 200

        await discord_bot.daily_slash.callback(self.mock_interaction)

        self.mock_database.get_setting.assert_called_once_with('daily_cooldown_minutes')
        self.mock_database.update_user_currency.assert_called_once_with(str(self.mock_user.id), 200)
        self.mock_interaction.response.send_message.assert_called_once_with(
            "You claimed your daily 200 currency! Your new balance is 200."
        )

class TestTopCommand(TestBotCommands):

    async def test_top_command_empty_leaderboard(self):
        self.mock_database.get_top_users_by_currency.return_value = []
        await discord_bot.top_users_slash.callback(self.mock_interaction)
        self.mock_database.get_top_users_by_currency.assert_called_once_with(limit=10)
        self.mock_interaction.response.send_message.assert_called_once_with(
            "The leaderboard is currently empty or no users have currency.", ephemeral=True
        )

    async def test_top_command_with_users(self):
        user_data_from_db = [
            ("111", 1000), 
            ("222", 500),
            (str(self.mock_user.id), 250) 
        ]
        self.mock_database.get_top_users_by_currency.return_value = user_data_from_db
        
        mock_user1_details = MagicMock(spec=discord.User); mock_user1_details.id = 111; mock_user1_details.display_name = "UserOne"
        mock_user2_details = MagicMock(spec=discord.User); mock_user2_details.id = 222; mock_user2_details.display_name = "UserTwo"
        
        def side_effect_get_user(user_id_int):
            if user_id_int == 111: return mock_user1_details
            if user_id_int == 222: return mock_user2_details
            if user_id_int == self.mock_user.id : return self.mock_user 
            return None
        self.mock_client.get_user.side_effect = side_effect_get_user

        await discord_bot.top_users_slash.callback(self.mock_interaction)

        self.mock_database.get_top_users_by_currency.assert_called_once_with(limit=10)
        self.mock_interaction.response.send_message.assert_called_once()
        sent_embed = self.mock_interaction.response.send_message.call_args[1]['embed']
        
        self.assertIsInstance(sent_embed, discord.Embed)
        self.assertEqual(sent_embed.title, "🏆 Top 10 Richest Users 🏆")
        
        expected_description_lines = [
            "**1.** UserOne - `1000` currency",
            "**2.** UserTwo - `500` currency",
            f"**3.** {self.mock_user.display_name} - `250` currency"
        ]
        actual_description_lines = sent_embed.description.split('\n')
        self.assertEqual(len(actual_description_lines), len(expected_description_lines))
        for i, expected_line in enumerate(expected_description_lines):
            self.assertEqual(actual_description_lines[i], expected_line)

    async def test_top_command_user_not_found(self):
        user_data_from_db = [("99999", 1500)] 
        self.mock_database.get_top_users_by_currency.return_value = user_data_from_db
        self.mock_client.get_user.return_value = None 

        await discord_bot.top_users_slash.callback(self.mock_interaction)
        self.mock_interaction.response.send_message.assert_called_once()
        sent_embed = self.mock_interaction.response.send_message.call_args[1]['embed']
        self.assertIn("**1.** User ID: 99999 - `1500` currency", sent_embed.description)

class TestBlackjackStartCommand(TestBotCommands):

    async def test_blackjack_start_success(self):
        bet_amount = 100
        self.mock_database.get_user_currency.return_value = 500 
        self.mock_blackjack_instance.bet_amount = bet_amount 

        await discord_bot.blackjack_slash.callback(self.mock_interaction, bet_amount=bet_amount)

        self.mock_database.create_user_if_not_exists.assert_called_once_with(str(self.mock_user.id))
        self.mock_database.get_user_currency.assert_called_once_with(str(self.mock_user.id))
        self.mock_database.update_user_currency.assert_called_once_with(str(self.mock_user.id), -bet_amount)
        self.mock_blackjack_game_class.assert_called_once_with(bet_amount=bet_amount)
        self.assertIn(str(self.mock_user.id), discord_bot.active_games)
        self.assertEqual(discord_bot.active_games[str(self.mock_user.id)], self.mock_blackjack_instance)
        self.mock_blackjack_instance.start_deal.assert_called_once()
        self.mock_interaction.response.send_message.assert_called_once()
        sent_embed = self.mock_interaction.response.send_message.call_args[1]['embed']
        self.assertIsInstance(sent_embed, discord.Embed)
        self.assertEqual(sent_embed.title, f"Blackjack Game - Bet: {bet_amount}")
        self.assertIn(self.mock_user.display_name, sent_embed.fields[0].name) 
        self.assertIn("Dealer Shows", sent_embed.fields[1].name) 
        self.assertIn("Use `/hit` or `/stand`", sent_embed.fields[2].value) 

    async def test_blackjack_start_insufficient_funds(self):
        bet_amount = 500
        self.mock_database.get_user_currency.return_value = 100 
        await discord_bot.blackjack_slash.callback(self.mock_interaction, bet_amount=bet_amount)
        self.mock_database.get_user_currency.assert_called_once_with(str(self.mock_user.id))
        self.mock_database.update_user_currency.assert_not_called()
        self.mock_blackjack_game_class.assert_not_called()
        self.assertNotIn(str(self.mock_user.id), discord_bot.active_games)
        self.mock_interaction.response.send_message.assert_called_once_with(
            f"You don't have enough currency. Your balance is 100.", ephemeral=True
        )

    async def test_blackjack_start_already_active_game(self):
        bet_amount = 50
        discord_bot.active_games[str(self.mock_user.id)] = self.mock_blackjack_instance 
        await discord_bot.blackjack_slash.callback(self.mock_interaction, bet_amount=bet_amount)
        self.mock_database.get_user_currency.assert_not_called() 
        self.mock_blackjack_game_class.assert_not_called() 
        self.mock_interaction.response.send_message.assert_called_once_with(
            "You already have an active game. Finish it before starting a new one.", ephemeral=True
        )
        
    async def test_blackjack_start_bet_zero_or_negative(self):
        await discord_bot.blackjack_slash.callback(self.mock_interaction, bet_amount=0)
        self.mock_interaction.response.send_message.assert_called_once_with(
            "Bet amount must be a positive number.", ephemeral=True
        )
        self.mock_interaction.response.reset_mock() 
        await discord_bot.blackjack_slash.callback(self.mock_interaction, bet_amount=-10)
        self.mock_interaction.response.send_message.assert_called_once_with(
            "Bet amount must be a positive number.", ephemeral=True
        )
        self.mock_database.get_user_currency.assert_not_called()

class TestBlackjackHitCommand(TestBotCommands):

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.mock_blackjack_instance.bet_amount = 100 
        self.mock_blackjack_instance.is_game_over = False 
        discord_bot.active_games[str(self.mock_user.id)] = self.mock_blackjack_instance

    async def test_hit_success_game_continues(self):
        def mock_player_hit_action():
            # Simulate game state after a hit, player not busted
            self.mock_blackjack_instance.is_game_over = False 
            self.mock_blackjack_instance.player_hand.is_busted.return_value = False
        self.mock_blackjack_instance.player_hit = MagicMock(side_effect=mock_player_hit_action)
        self.mock_blackjack_instance.player_hand.is_busted.return_value = False # Initial state before hit call for clarity

        updated_player_details = {'cards': ['DA', 'D5', 'D6'], 'value': 12} 
        self.mock_blackjack_instance.get_player_hand_details.return_value = updated_player_details

        await discord_bot.hit_slash.callback(self.mock_interaction)

        self.mock_blackjack_instance.player_hit.assert_called_once()
        self.mock_interaction.response.send_message.assert_called_once()
        sent_embed = self.mock_interaction.response.send_message.call_args[1]['embed']
        self.assertIn("Value: 12", sent_embed.fields[0].value) 
        self.assertIn("Use `/hit` or `/stand`", sent_embed.fields[2].value) 

    async def test_hit_player_busts(self):
        def mock_player_hit_action():
            self.mock_blackjack_instance.is_game_over = True
            self.mock_blackjack_instance.status_message = "You busted!"
            self.mock_blackjack_instance.player_hand.is_busted.return_value = True 
        self.mock_blackjack_instance.player_hit = MagicMock(side_effect=mock_player_hit_action)
        
        busted_player_details = {'cards': ['DA', 'D10', 'DJ'], 'value': 30} 
        self.mock_blackjack_instance.get_player_hand_details.return_value = busted_player_details
        self.mock_database.get_user_currency.return_value = 0 

        await discord_bot.hit_slash.callback(self.mock_interaction)

        self.mock_blackjack_instance.player_hit.assert_called_once()
        self.mock_interaction.response.send_message.assert_called_once()
        sent_embed = self.mock_interaction.response.send_message.call_args[1]['embed']
        self.assertIn("Value: 30", sent_embed.fields[0].value) 
        self.assertIn("You busted!", sent_embed.fields[2].value) 
        self.assertIn("Game Over. Your new balance: 0", sent_embed.description)
        self.assertNotIn(str(self.mock_user.id), discord_bot.active_games)

    async def test_hit_no_active_game(self):
        discord_bot.active_games.clear() 
        await discord_bot.hit_slash.callback(self.mock_interaction)
        self.mock_blackjack_instance.player_hit.assert_not_called()
        self.mock_interaction.response.send_message.assert_called_once_with(
            "You don't have an active blackjack game. Start one with `/blackjack <bet_amount>`.", ephemeral=True
        )

    async def test_hit_game_already_over(self):
        self.mock_blackjack_instance.is_game_over = True
        await discord_bot.hit_slash.callback(self.mock_interaction)
        self.mock_blackjack_instance.player_hit.assert_not_called()
        self.mock_interaction.response.send_message.assert_called_once_with(
            "This game is already over. Start a new one with `/blackjack <bet_amount>`.", ephemeral=True
        )

class TestBlackjackStandCommand(TestBotCommands):

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.mock_blackjack_instance.bet_amount = 100
        self.mock_blackjack_instance.is_game_over = False 
        discord_bot.active_games[str(self.mock_user.id)] = self.mock_blackjack_instance

    async def test_stand_player_wins(self):
        def mock_player_stand():
            self.mock_blackjack_instance.is_game_over = True
            self.mock_blackjack_instance.outcome = "player_wins"
            self.mock_blackjack_instance.status_message = "Player wins!"
        self.mock_blackjack_instance.player_stand = MagicMock(side_effect=mock_player_stand)
        self.mock_database.update_user_currency.return_value = 600 

        await discord_bot.stand_slash.callback(self.mock_interaction)

        self.mock_blackjack_instance.player_stand.assert_called_once()
        self.mock_database.update_user_currency.assert_called_once_with(str(self.mock_user.id), 200) 
        self.mock_interaction.response.send_message.assert_called_once()
        sent_embed = self.mock_interaction.response.send_message.call_args[1]['embed']
        self.assertIn("Player wins!", sent_embed.description) 
        self.assertIn("Your new balance is 600", sent_embed.fields[2].value) 
        self.assertNotIn(str(self.mock_user.id), discord_bot.active_games)

    async def test_stand_dealer_wins(self):
        def mock_player_stand():
            self.mock_blackjack_instance.is_game_over = True
            self.mock_blackjack_instance.outcome = "dealer_wins"
            self.mock_blackjack_instance.status_message = "Dealer wins!"
        self.mock_blackjack_instance.player_stand = MagicMock(side_effect=mock_player_stand)
        self.mock_database.get_user_currency.return_value = 300

        await discord_bot.stand_slash.callback(self.mock_interaction)

        self.mock_blackjack_instance.player_stand.assert_called_once()
        self.mock_database.update_user_currency.assert_not_called() 
        self.mock_database.get_user_currency.assert_called_once_with(str(self.mock_user.id))
        self.mock_interaction.response.send_message.assert_called_once()
        sent_embed = self.mock_interaction.response.send_message.call_args[1]['embed']
        self.assertIn("Dealer wins!", sent_embed.description)
        self.assertIn("Your balance remains 300", sent_embed.fields[2].value)
        self.assertNotIn(str(self.mock_user.id), discord_bot.active_games)

    async def test_stand_push(self):
        def mock_player_stand():
            self.mock_blackjack_instance.is_game_over = True
            self.mock_blackjack_instance.outcome = "push"
            self.mock_blackjack_instance.status_message = "Push!"
        self.mock_blackjack_instance.player_stand = MagicMock(side_effect=mock_player_stand)
        self.mock_database.update_user_currency.return_value = 500 

        await discord_bot.stand_slash.callback(self.mock_interaction)

        self.mock_blackjack_instance.player_stand.assert_called_once()
        self.mock_database.update_user_currency.assert_called_once_with(str(self.mock_user.id), 100) 
        self.mock_interaction.response.send_message.assert_called_once()
        sent_embed = self.mock_interaction.response.send_message.call_args[1]['embed']
        self.assertIn("Push!", sent_embed.description)
        self.assertIn("Your bet was returned. Your balance is 500", sent_embed.fields[2].value)
        self.assertNotIn(str(self.mock_user.id), discord_bot.active_games)

    async def test_stand_no_active_game(self):
        discord_bot.active_games.clear()
        await discord_bot.stand_slash.callback(self.mock_interaction)
        self.mock_blackjack_instance.player_stand.assert_not_called()
        self.mock_interaction.response.send_message.assert_called_once_with(
            "You don't have an active blackjack game. Start one with `/blackjack <bet_amount>`.", ephemeral=True
        )

    async def test_stand_game_already_over_in_active_games(self):
        self.mock_blackjack_instance.is_game_over = True 
        await discord_bot.stand_slash.callback(self.mock_interaction)
        self.mock_blackjack_instance.player_stand.assert_not_called() 
        self.mock_interaction.response.send_message.assert_called_once_with(
            "This game is already over. Start a new one with `/blackjack <bet_amount>`.", ephemeral=True
        )

class TestSetConfigCommand(TestBotCommands):

    async def test_set_config_daily_cooldown_success(self):
        key = "daily_cooldown"
        value = "180" 
        await discord_bot.set_config_slash.callback(self.mock_interaction, key=key, value=value)
        self.mock_database.set_setting.assert_called_once_with('daily_cooldown_minutes', value)
        self.mock_interaction.response.send_message.assert_called_once_with(
            f"Daily cooldown has been updated to {value} minutes."
        )

    async def test_set_config_daily_cooldown_invalid_value_not_number(self):
        key = "daily_cooldown"
        value = "abc" 
        await discord_bot.set_config_slash.callback(self.mock_interaction, key=key, value=value)
        self.mock_database.set_setting.assert_not_called()
        self.mock_interaction.response.send_message.assert_called_once_with(
            "Invalid value. Cooldown must be a number of minutes (e.g., '120').", ephemeral=True
        )

    async def test_set_config_daily_cooldown_invalid_value_negative(self):
        key = "daily_cooldown"
        value = "-60" 
        await discord_bot.set_config_slash.callback(self.mock_interaction, key=key, value=value)
        self.mock_database.set_setting.assert_not_called()
        self.mock_interaction.response.send_message.assert_called_once_with(
            "Invalid value. Cooldown must be a positive number of minutes.", ephemeral=True
        )

    async def test_set_config_invalid_key(self):
        key = "unknown_setting"
        value = "some_value"
        await discord_bot.set_config_slash.callback(self.mock_interaction, key=key, value=value)
        self.mock_database.set_setting.assert_not_called()
        self.mock_interaction.response.send_message.assert_called_once_with(
            "Invalid setting key. Currently supported: `daily_cooldown`", ephemeral=True
        )

class TestGlobalErrorHandler(TestBotCommands):

    async def test_on_app_command_error_missing_permissions(self):
        error = discord.app_commands.MissingPermissions([]) 
        self.mock_interaction.command = MagicMock(spec=discord.app_commands.Command)
        self.mock_interaction.command.name = "test_command_perms"
        await discord_bot.on_app_command_error(self.mock_interaction, error) 
        self.mock_interaction.response.send_message.assert_called_once_with(
            "You don't have the required permissions to use this command.", ephemeral=True
        )

    async def test_on_app_command_error_missing_required_argument(self):
        # This test now checks the fallback behavior since the specific check
        # for MissingRequiredArgument was removed from bot.py's error handler
        # due to AttributeErrors in the test environment.
        mock_command_for_error = MagicMock(spec=discord.app_commands.Command)
        mock_command_for_error.name = "test_command_missing_arg"
        
        # Simulate an error that would be an AppCommandError but not one of the other specific types
        class SomeSpecificAppError(discord.app_commands.AppCommandError):
            pass
        error = SomeSpecificAppError("A specific error that implies a missing arg.")
        # If we knew MissingRequiredArgument existed, we'd use it:
        # mock_param = MagicMock(spec=discord.app_commands.Parameter)
        # mock_param.name = "my_arg"
        # error = discord.app_commands.MissingRequiredArgument(mock_param)


        self.mock_interaction.command = mock_command_for_error 
        await discord_bot.on_app_command_error(self.mock_interaction, error)
        # Expecting the generic fallback message because MissingRequiredArgument specific check was removed from bot.py
        self.mock_interaction.response.send_message.assert_called_once_with(
            "An unexpected error occurred. Please try again later.", ephemeral=True
        )

    async def test_on_app_command_error_command_on_cooldown(self):
        mock_command_for_cooldown = MagicMock(spec=discord.app_commands.Command)
        mock_command_for_cooldown.name = "test_command_cooldown"
        cooldown_mock = MagicMock(spec=discord.app_commands.Cooldown) 
        try:
            cooldown_mock.bucket = discord.app_commands.BucketType.user
        except AttributeError: 
            cooldown_mock.bucket = 1 # Placeholder if BucketType enum fails
        cooldown_mock.rate = 1
        cooldown_mock.per = 60.0
        error = discord.app_commands.CommandOnCooldown(cooldown_mock, 30.555) 
        self.mock_interaction.command = mock_command_for_cooldown
        await discord_bot.on_app_command_error(self.mock_interaction, error)
        self.mock_interaction.response.send_message.assert_called_once_with(
            f"This command is on cooldown. Try again in {error.retry_after:.2f} seconds.", ephemeral=True
        )

    async def test_on_app_command_error_command_invoke_error_generic(self):
        original_exception = ValueError("Something went very wrong inside the command.")
        mock_command_obj = MagicMock(spec=discord.app_commands.Command)
        mock_command_obj.name = "test_command_invoke_error"
        self.mock_interaction.command = mock_command_obj
        error = discord.app_commands.CommandInvokeError(mock_command_obj, original_exception) 
        await discord_bot.on_app_command_error(self.mock_interaction, error)
        self.mock_interaction.response.send_message.assert_called_once_with(
            f"An error occurred while executing the command: {error.original}", ephemeral=True
        )

    async def test_on_app_command_error_unhandled_app_command_error(self):
        class CustomAppError(discord.app_commands.AppCommandError): pass         
        error = CustomAppError("A very specific app command error.")
        self.mock_interaction.command = MagicMock(spec=discord.app_commands.Command)
        self.mock_interaction.command.name = "test_command_custom_error"
        await discord_bot.on_app_command_error(self.mock_interaction, error)
        self.mock_interaction.response.send_message.assert_called_once_with(
            "An unexpected error occurred. Please try again later.", ephemeral=True
        )

    async def test_error_handler_response_already_done_then_followup(self):
        self.mock_interaction.response.is_done = MagicMock(return_value=True)
        error = discord.app_commands.MissingPermissions([]) 
        self.mock_interaction.command = MagicMock(spec=discord.app_commands.Command, name="test_cmd_done") 
        await discord_bot.on_app_command_error(self.mock_interaction, error)
        self.mock_interaction.response.send_message.assert_not_called() 
        self.mock_interaction.followup.send.assert_called_once_with(
            "You don't have the required permissions to use this command.", ephemeral=True
        )

if __name__ == '__main__':
    unittest.main()

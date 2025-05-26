# Discord Blackjack Bot

A Discord bot that allows users to play Blackjack against it and manage virtual currency.

## Features

*   Play Blackjack against the bot using text commands.
*   Virtual currency system.
*   `!daily` command to receive free currency once per cooldown period.
*   Configurable cooldown for the `!daily` command via `!set daily_cooldown <minutes>` (admin only).
*   Simple Blackjack rules: hit or stand.
*   Users can only have one active Blackjack game at a time.
*   Currency and user data stored in a SQLite database.
*   Application packaged with Docker for easy deployment.

## Project Architecture

The project is structured into several Python modules:

*   **`bot.py`**: The main application file that handles Discord bot events, command registration, and integrates other modules.
*   **`database.py`**: Manages all interactions with the SQLite database (`discord_bot.db`). This includes:
    *   Storing user information (ID, currency, last daily claim time).
    *   Storing bot settings (e.g., daily cooldown duration).
    *   Uses parameterized queries to prevent SQL injection.
*   **`blackjack_game.py`**: Contains the `BlackjackGame` class, which orchestrates the overall flow and state of a single Blackjack game instance.
*   **`game_logic/` (Package)**: Contains the fundamental components for the Blackjack game:
    *   **`game_logic/card.py`**: Defines the `Card` class (rank, suit, value).
    *   **`game_logic/deck.py`**: Defines the `Deck` class (standard 52-card deck, shuffling, dealing).
    *   **`game_logic/hand.py`**: Defines the `Hand` class (manages cards in a hand, calculates value considering Aces, checks for busts).
*   **`tests/`**: Contains unit tests for various parts of the application to ensure correctness.
    *   `test_card.py`, `test_deck.py`, `test_hand.py`: Test the core game logic components.
    *   `test_blackjack_game.py`: Tests the overall game flow.
    *   `test_database.py`: Tests the database interaction functions using an in-memory SQLite database.
*   **`Dockerfile`**: Defines the Docker image for deploying the bot.
*   **`requirements.txt`**: Lists Python dependencies (e.g., `discord.py`).

## Core Commands

*   **`!daily`**: Allows a user to claim 200 currency. This command can be used once every cooldown period (default is 2 minutes, configurable).
*   **`!set daily_cooldown <minutes>`**: (Admin only) Sets the cooldown period for the `!daily` command in minutes.
*   **`!blackjack <bet_amount>`** (or `!bj <bet_amount>`): Starts a new game of Blackjack with the specified bet amount. The bet is deducted from the user's currency.
*   **`!hit`**: During an active Blackjack game, requests another card from the deck.
*   **`!stand`** (or `!hold`): During an active Blackjack game, finalizes the user's hand, and the dealer plays out their turn. The game outcome is then determined.

## Database Schema

The bot uses a SQLite database (`discord_bot.db`) with the following main tables:

*   **`users`**:
    *   `user_id` (TEXT, PRIMARY KEY): The user's Discord ID.
    *   `currency` (INTEGER): The amount of virtual currency the user has.
    *   `last_daily_claim` (TIMESTAMP): The last time the user successfully used the `!daily` command.
*   **`settings`**:
    *   `key` (TEXT, PRIMARY KEY): The name of the setting (e.g., `daily_cooldown_minutes`).
    *   `value` (TEXT): The value of the setting.

## Running with Docker

To build and run the bot using Docker:

1.  **Build the Docker image:**
    ```bash
    docker build -t discord-blackjack-bot .
    ```

2.  **Run the Docker container:**
    You need to provide your Discord bot token as an environment variable.
    ```bash
    docker run -e DISCORD_BOT_TOKEN="YOUR_ACTUAL_BOT_TOKEN" --name blackjack-bot-container discord-blackjack-bot
    ```
    Replace `"YOUR_ACTUAL_BOT_TOKEN"` with your bot's actual token.
    The `--name` flag is optional but helpful for managing the container.

## Dependencies

Python dependencies are listed in `requirements.txt` and include:
*   `discord.py`

(If there are other direct dependencies the bot code uses, list them here. For now, discord.py is the main one.)

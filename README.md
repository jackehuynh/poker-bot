# Discord Blackjack Bot

A Discord bot that allows users to play Blackjack against it and manage virtual currency using slash commands.

## Features

*   Play Blackjack against the bot using **slash commands**.
*   Virtual currency system.
*   `/daily` command to receive free currency once per cooldown period.
*   Configurable cooldown for the `/daily` command via `/set key:daily_cooldown value:<minutes>` (admin only).
*   `/top` command to display the top users by currency.
*   Simple Blackjack rules: hit or stand.
*   Users can only have one active Blackjack game at a time.
*   Currency and user data stored in a SQLite database.
*   Database file path is configurable via the `DB_PATH` environment variable.
*   Application packaged with Docker for easy deployment.

## Project Architecture

The project is structured into several Python modules:

*   **`bot.py`**: The main application file that handles Discord bot events, slash command registration, and integrates other modules.
*   **`database.py`**: Manages all interactions with the SQLite database. This includes:
    *   Storing user information (ID, currency, last daily claim time).
    *   Storing bot settings (e.g., daily cooldown duration).
    *   Uses parameterized queries to prevent SQL injection.
    *   The database file (default: `discord_bot.db`) path can be configured using the `DB_PATH` environment variable.
*   **`blackjack_game.py`**: Contains the `BlackjackGame` class, which orchestrates the overall flow and state of a single Blackjack game instance.
*   **`game_logic/` (Package)**: Contains the fundamental components for the Blackjack game:
    *   **`game_logic/card.py`**: Defines the `Card` class (rank, suit, value).
    *   **`game_logic/deck.py`**: Defines the `Deck` class (standard 52-card deck, shuffling, dealing).
    *   **`game_logic/hand.py`**: Defines the `Hand` class (manages cards in a hand, calculates value considering Aces, checks for busts).
*   **`tests/`**: Contains unit tests for various parts of the application.
    *   `test_card.py`, `test_deck.py`, `test_hand.py`: Test the core game logic components.
    *   `test_blackjack_game.py`: Tests the overall game flow.
    *   `test_database.py`: Tests database interactions, including `DB_PATH` configuration.
    *   `test_bot.py`: Tests the bot's slash command logic and error handling using mocks.
*   **`Dockerfile`**: Defines the Docker image for deploying the bot.
*   **`requirements.txt`**: Lists Python dependencies (e.g., `discord.py`).

## Core Slash Commands

*   **`/daily`**: Allows a user to claim 200 currency. This command can be used once every cooldown period (default is 120 minutes, configurable via `/set`).
*   **`/blackjack <bet_amount>`**: Starts a new game of Blackjack with the specified bet amount. The bet is deducted from the user's currency.
*   **`/hit`**: During an active Blackjack game, requests another card from the deck.
*   **`/stand`**: During an active Blackjack game, finalizes the user's hand, and the dealer plays out their turn. The game outcome is then determined.
*   **`/top`**: Displays the top 10 users with the most currency.
*   **`/set <key> <value>`**: (Admin only) Changes bot settings.
    *   Supported `key`: `daily_cooldown`
    *   Example: `/set key:daily_cooldown value:180` (sets daily cooldown to 180 minutes).

## Database

The bot uses an SQLite database to store user data and settings.
*   By default, the database file is named `discord_bot.db` and is created in the bot's working directory.
*   The path for this database file can be configured using the `DB_PATH` environment variable. This is particularly useful when running in Docker for data persistence.

## Configuration

The following environment variables are used to configure the bot:

*   **`DISCORD_BOT_TOKEN`** (Required): Your Discord bot's token.
*   **`DB_PATH`** (Optional): The full file path where the SQLite database file should be stored.
    *   Default: `discord_bot.db` (in the current working directory).
    *   Example for Docker: `/data/discord_bot.db` (when using a volume mounted at `/data`).

## Running with Docker (using Docker Compose)

This project includes a `docker-compose.yml` file to simplify running the bot with Docker.

**Prerequisites:**
*   Docker installed: [https://docs.docker.com/get-docker/](https://docs.docker.com/get-docker/)
*   Docker Compose installed: [https://docs.docker.com/compose/install/](https://docs.docker.com/compose/install/) (Often included with Docker Desktop)

**Steps:**

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Configure Environment Variables:**
    *   Create a file named `.env` in the root of the project.
    *   Add the following content to the `.env` file, replacing `your_discord_token_here` with your actual Discord bot token:
        ```env
        DISCORD_TOKEN=your_discord_token_here
        DB_PATH=discord_bot.db
        ```
    *   The `DB_PATH` variable specifies the name of the SQLite database file. It will be created in the project's root directory on your host machine because the `docker-compose.yml` file mounts the current directory (`./`) into the `/app` directory in the container.

3.  **Build and Run the Bot:**
    Open a terminal in the project's root directory (where `docker-compose.yml` is located) and run:
    ```bash
    docker-compose up -d
    ```
    Or, for newer versions of Docker Compose (v2):
    ```bash
    docker compose up -d
    ```
    This command will:
    *   Build the Docker image for the bot (if not already built) based on the `Dockerfile`.
    *   Start the bot service in detached mode (`-d`).
    *   The bot's console output (logs) can be viewed using `docker-compose logs -f app` or `docker compose logs -f app`.

4.  **Stopping the Bot:**
    To stop the bot and remove the containers, run:
    ```bash
    docker-compose down
    ```
    Or, for newer versions:
    ```bash
    docker compose down
    ```
    The SQLite database file (`discord_bot.db` or whatever you set in `DB_PATH`) will remain in your project directory.

## Dependencies

Python dependencies are listed in `requirements.txt`:
*   `discord.py`

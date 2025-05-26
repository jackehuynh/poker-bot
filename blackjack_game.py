# import random # No longer directly used by BlackjackGame after refactoring Deck
# Card, Deck, Hand classes and SUITS, RANKS constants are now in game_logic module

from game_logic.deck import Deck # Deck uses Card implicitly and SUITS, RANKS are in deck.py
from game_logic.hand import Hand # Hand uses Card implicitly

# Note: Card is not directly instantiated or used by BlackjackGame class itself,
# but it's fundamental to Deck and Hand.
# from game_logic.card import Card # Not strictly needed here if BlackjackGame only uses Deck and Hand


class BlackjackGame:
    """Manages the logic for a game of Blackjack."""
    def __init__(self, bet_amount: int):
        """Initializes a new Blackjack game."""
        self.deck = Deck()
        self.player_hand = Hand()
        self.dealer_hand = Hand()
        self.bet_amount = bet_amount
        self.is_game_over = False
        self.status_message = ""
        self.outcome = None # 'player_wins', 'dealer_wins', 'push', 'player_blackjack'

    def start_deal(self):
        """Deals initial cards to player and dealer."""
        if len(self.deck.cards) < 4: # Ensure enough cards for initial deal
            self.status_message = "Not enough cards in deck to start a new game."
            self.is_game_over = True
            return

        self.player_hand.add_card(self.deck.deal_card())
        self.dealer_hand.add_card(self.deck.deal_card())
        self.player_hand.add_card(self.deck.deal_card())
        self.dealer_hand.add_card(self.deck.deal_card())

        self.player_hand.calculate_value()
        self.dealer_hand.calculate_value()

        # Check for player blackjack (21 with two cards)
        if self.player_hand.calculate_value() == 21 and len(self.player_hand.get_cards()) == 2:
            # Check if dealer also has blackjack
            if self.dealer_hand.calculate_value() == 21 and len(self.dealer_hand.get_cards()) == 2:
                self.status_message = "Push! Both player and dealer have Blackjack."
                self.outcome = 'push'
            else:
                self.status_message = "Blackjack! Player wins!"
                self.outcome = 'player_blackjack' # Special win condition for blackjack
            self.is_game_over = True
        # Check for dealer blackjack if player also has blackjack
        if self.player_hand.calculate_value() == 21 and len(self.player_hand.get_cards()) == 2:
            if self.dealer_hand.calculate_value() == 21 and len(self.dealer_hand.get_cards()) == 2:
                self.status_message = "Push! Both player and dealer have Blackjack."
                self.outcome = 'push'
            else:
                self.status_message = "Blackjack! Player wins!"
                self.outcome = 'player_blackjack'
            self.is_game_over = True


    def player_hit(self):
        """Player takes another card. Returns True if game continues, False if game over."""
        if self.is_game_over:
            return False # Game already over

        card = self.deck.deal_card()
        if card:
            self.player_hand.add_card(card)
            if self.player_hand.is_busted():
                self.status_message = "Player busts! Dealer wins."
                self.outcome = 'dealer_wins'
                self.is_game_over = True
                return False # Game over
            return True # Game continues
        else:
            self.status_message = "Deck is empty. Game cannot continue."
            self.is_game_over = True
            return False # Game over

    def player_stand(self):
        """Player stands. Dealer plays out their hand. Sets game_over and outcome."""
        if self.is_game_over: # If already over (e.g. player blackjack on deal)
            return self.outcome

        # Dealer's turn
        while self.dealer_hand.calculate_value() < 17:
            card = self.deck.deal_card()
            if card:
                self.dealer_hand.add_card(card)
            else:
                # Deck empty during dealer's turn, should be rare
                break 

        # Determine winner
        player_value = self.player_hand.calculate_value()
        dealer_value = self.dealer_hand.calculate_value()

        if self.player_hand.is_busted(): # Should have been caught by player_hit, but as a safeguard
            self.status_message = "Player busted! Dealer wins."
            self.outcome = 'dealer_wins'
        elif self.dealer_hand.is_busted():
            self.status_message = "Dealer busts! Player wins."
            self.outcome = 'player_wins'
        elif player_value > dealer_value:
            self.status_message = "Player wins!"
            self.outcome = 'player_wins'
        elif dealer_value > player_value:
            self.status_message = "Dealer wins."
            self.outcome = 'dealer_wins'
        else: # player_value == dealer_value
            self.status_message = "Push!"
            self.outcome = 'push'

        self.is_game_over = True
        return self.outcome

    def get_player_hand_details(self) -> dict:
        """Returns player's cards (as strings) and current hand value."""
        return {
            'cards': self.player_hand.get_cards_as_strings(),
            'value': self.player_hand.calculate_value()
        }

    def get_dealer_hand_details(self, reveal_all=False) -> dict:
        """
        Returns dealer's cards (as strings) and hand value.
        If reveal_all is False and game not over, only the first card is shown.
        """
        dealer_cards_obj = self.dealer_hand.get_cards()
        if not dealer_cards_obj: # No cards yet
             return {'cards': [], 'value': 0}

        if reveal_all or self.is_game_over:
            return {
                'cards': self.dealer_hand.get_cards_as_strings(),
                'value': self.dealer_hand.calculate_value()
            }
        else:
            # Show only the first card and its value, other card is hidden
            return {
                'cards': [str(dealer_cards_obj[0]), "Hidden Card"],
                'value_one_card': dealer_cards_obj[0].value
            }


if __name__ == '__main__':
    print("--- New Blackjack Game ---")
    game = BlackjackGame(bet_amount=10)

    # Initial deal
    game.start_deal()
    player_details = game.get_player_hand_details()
    dealer_details_hidden = game.get_dealer_hand_details(reveal_all=False)
    
    print(f"Player Hand: {player_details['cards']} (Value: {player_details['value']})")
    if not game.is_game_over: # if not initial blackjack
        # Ensure dealer_details_hidden has 'cards' and 'value_one_card'
        if 'cards' in dealer_details_hidden and dealer_details_hidden['cards']:
             print(f"Dealer Shows: {dealer_details_hidden['cards'][0]} (Value: {dealer_details_hidden.get('value_one_card', 'N/A')})")
        else:
            print("Dealer has no cards to show yet or error in dealer_details_hidden.")


    if game.is_game_over:
        print(f"Game Over! {game.status_message}")
        dealer_details_revealed = game.get_dealer_hand_details(reveal_all=True)
        print(f"Dealer's Full Hand: {dealer_details_revealed['cards']} (Value: {dealer_details_revealed['value']})")

    # Example: Player hits until bust or decides to stand (simple loop for testing)
    while not game.is_game_over:
        action = input("Hit or Stand? (h/s): ").lower()
        if action == 'h':
            game.player_hit() # player_hit now returns bool, not value/busted directly
            player_details = game.get_player_hand_details()
            print(f"Player Hand: {player_details['cards']} (Value: {player_details['value']})")
            if game.is_game_over: # Check game.is_game_over after hit
                print(f"Game Over! {game.status_message}")
                break
        elif action == 's':
            outcome = game.player_stand()
            print(f"Player stands. Outcome: {outcome}")
            print(f"Game Over! {game.status_message}") # player_stand sets this
            break
        else:
            print("Invalid input. Type 'h' or 's'.")

    # Show final hands if game ended by stand or bust during hit
    if game.is_game_over:
        player_details = game.get_player_hand_details()
        dealer_details_revealed = game.get_dealer_hand_details(reveal_all=True)
        print(f"\n--- Final Hands ---")
        print(f"Player Hand: {player_details['cards']} (Value: {player_details['value']})")
        print(f"Dealer Hand: {dealer_details_revealed['cards']} (Value: {dealer_details_revealed['value']})")
        print(f"Outcome: {game.status_message}")

    print("\n--- Testing Blackjack Scenario ---")
    # Test for player blackjack
    # Need to import Card for Mock Decks if they are kept in this file for testing.
    # For now, let's assume tests might be moved or updated separately.
    # If we keep these tests, we MUST import Card: from game_logic.card import Card
    # class MockDeckForBlackjack(Deck):
    #     def __init__(self): # Card is now a class
    #         from game_logic.card import Card # Import for test mock
    #         self.cards = [
    #             Card('A', 'Spades', 11), Card('K', 'Hearts', 10), # Player
    #             Card('5', 'Clubs', 5), Card('Q', 'Diamonds', 10)  # Dealer
    #         ]
    #         self.cards.reverse() # So pop() works as expected

    game_bj = BlackjackGame(bet_amount=100)
    # game_bj.deck = MockDeckForBlackjack() # This line would require MockDeckForBlackjack
    # For now, to make the file runnable without test-specific import, commenting out mock deck usage.
    # Real tests should be in a separate test suite.
    game_bj.deck = MockDeckForBlackjack()
    game_bj.start_deal()
    player_details_bj = game_bj.get_player_hand_details()
    print(f"Player Hand BJ Test: {player_details_bj['cards']} (Value: {player_details_bj['value']})")
    print(f"Game Status: {game_bj.status_message}")
    print(f"Is game over: {game_bj.is_game_over}")
    print(f"Outcome: {game_bj.outcome}")

    dealer_details_bj = game_bj.get_dealer_hand_details(reveal_all=True)
    print(f"Dealer Hand BJ Test: {dealer_details_bj['cards']} (Value: {dealer_details_bj['value']})")


    print("\n--- Testing Dealer Bust Scenario ---")
    # class MockDeckForDealerBust(Deck):
    #     def __init__(self):
    #         from game_logic.card import Card # Import for test mock
    #         self.cards = [
    #             Card('10', 'Spades', 10), Card('7', 'Hearts', 7),   # Player
    #             Card('K', 'Clubs', 10), Card('6', 'Diamonds', 6), # Dealer initial
    #             Card('J', 'Spades', 10) # Dealer hit card -> bust
    #         ]
    #         self.cards.reverse()

    game_db = BlackjackGame(bet_amount=20)
    # game_db.deck = MockDeckForDealerBust() # Commenting out mock usage for now
    game_db.deck = MockDeckForDealerBust()
    game_db.start_deal()
    player_details_db = game_db.get_player_hand_details()
    print(f"Player Hand: {player_details_db['cards']} (Value: {player_details_db['value']})")
    
    outcome_db = game_db.player_stand() # Player stands on 17
    print(f"Player stands. Outcome: {outcome_db}")
    print(f"Game Status: {game_db.status_message}")
    dealer_details_db = game_db.get_dealer_hand_details(reveal_all=True)
    print(f"Dealer Hand: {dealer_details_db['cards']} (Value: {dealer_details_db['value']})")


    print("\n--- Test Player Bust ---")
    game_pb = BlackjackGame(bet_amount=5)
    # game_pb.deck = Deck() # Fresh deck - already default
    game_pb.start_deal()
    print(f"Player initial: {game_pb.get_player_hand_details()['cards']}")
    game_pb.player_hit() 
    print(f"Player after 1 hit: {game_pb.get_player_hand_details()['cards']}")
    game_pb.player_hit() 
    print(f"Player after 2 hits: {game_pb.get_player_hand_details()['cards']}")
    if not game_pb.is_game_over:
        game_pb.player_hit()
        print(f"Player after 3 hits: {game_pb.get_player_hand_details()['cards']}")
    if not game_pb.is_game_over:
        game_pb.player_hit()
        print(f"Player after 4 hits: {game_pb.get_player_hand_details()['cards']}")

    print(f"Player value: {game_pb.player_hand.calculate_value()}") # Access hand directly for value if needed
    print(f"Player busted: {game_pb.player_hand.is_busted()}")
    print(f"Game status: {game_pb.status_message}")
    print(f"Game over: {game_pb.is_game_over}")
    print(f"Outcome: {game_pb.outcome}")

import unittest
from blackjack_game import BlackjackGame
from game_logic.card import Card
from game_logic.deck import Deck # For MockDeck inheritance and isinstance
from game_logic.hand import Hand # For isinstance

class MockDeck(Deck):
    def __init__(self, cards_to_deal): # cards_to_deal should be a list of Card objects
        # We don't call super().__init__() here because we don't want to create a standard deck.
        self.cards = list(cards_to_deal) 
        # Game deals P1, D1, P2, D2, then hits.
        # If cards_to_deal = [P1, D1, P2, D2, HitP, HitD]
        # we want pop() to get P1 first. list.pop() gets from the end. So reverse.
        self.cards.reverse() 

    def shuffle(self):
        pass # Prevent shuffling for controlled tests

    def _create_deck(self): # Override to prevent actual deck creation
        pass


class TestBlackjackGame(unittest.TestCase):
    def setUp(self):
        """Create a new game instance for each test method using the default deck."""
        self.game_default_deck = BlackjackGame(bet_amount=10)

    def test_game_initialization(self):
        """Test that a new game is initialized correctly."""
        game = self.game_default_deck # Use the one from setUp for this test
        self.assertEqual(game.bet_amount, 10)
        self.assertIsInstance(game.player_hand, Hand)
        self.assertIsInstance(game.dealer_hand, Hand)
        self.assertIsInstance(game.deck, Deck) 
        self.assertFalse(game.is_game_over)

    def test_start_deal_normal(self):
        """Test the initial deal of cards in a normal scenario (no immediate blackjack)."""
        game = BlackjackGame(bet_amount=10)
        # Player: 5, 6. Dealer: 7, 8 (Values: P:11, D:15)
        mock_cards = [Card('5', 'S', 5), Card('7', 'H', 7), Card('6', 'D', 6), Card('8', 'C', 8)]
        game.deck = MockDeck(mock_cards)
        
        game.start_deal()
        self.assertEqual(len(game.player_hand.cards), 2)
        self.assertEqual(len(game.dealer_hand.cards), 2)
        self.assertFalse(game.is_game_over, f"Game should not be over. Status: {game.status_message}, Outcome: {game.outcome}")
        self.assertEqual(game.player_hand.calculate_value(), 11)
        self.assertEqual(game.dealer_hand.calculate_value(), 15)


    def test_start_deal_player_blackjack(self):
        """Test the scenario where the player gets a blackjack on the initial deal."""
        game = BlackjackGame(bet_amount=10)
        # Player: Ace, King; Dealer: 5, 9
        # Card order for deal: P1, D1, P2, D2
        mock_cards = [Card('A', 'S', 11), Card('5', 'H', 5), Card('K', 'D', 10), Card('9', 'C', 9)]
        game.deck = MockDeck(mock_cards)
        game.start_deal()

        self.assertTrue(game.is_game_over)
        self.assertEqual(game.outcome, 'player_blackjack')
        self.assertEqual(game.status_message, "Blackjack! Player wins!")

    def test_start_deal_push_both_blackjack(self):
        """Test scenario where both player and dealer get blackjack (push)."""
        game = BlackjackGame(bet_amount=10)
        # Player: A, K; Dealer: A, Q
        mock_cards = [Card('A', 'S', 11), Card('A', 'H', 11), Card('K', 'D', 10), Card('Q', 'C', 10)]
        game.deck = MockDeck(mock_cards)
        game.start_deal()
        self.assertTrue(game.is_game_over)
        self.assertEqual(game.outcome, 'push')
        self.assertEqual(game.status_message, "Push! Both player and dealer have Blackjack.")

    def test_player_hit_normal(self):
        """Test player hitting a card without busting."""
        game = BlackjackGame(bet_amount=10)
        # Player: 5, 6 (initial 11) -> hits 7 (total 18). Dealer: K, Q (20)
        # Order for MockDeck: P1, D1, P2, D2, PlayerHit1
        mock_cards = [Card('5', 'S', 5), Card('K', 'H', 10), Card('6', 'D', 6), Card('Q', 'C', 10), Card('7', 'S', 7)]
        game.deck = MockDeck(mock_cards)
        game.start_deal() 
        
        self.assertFalse(game.is_game_over) 
        game.player_hit() 
        
        self.assertEqual(len(game.player_hand.cards), 3)
        self.assertEqual(game.player_hand.calculate_value(), 18)
        self.assertFalse(game.is_game_over)

    def test_player_hit_bust(self):
        """Test player hitting a card and busting."""
        game = BlackjackGame(bet_amount=10)
        # Player: K, Q (initial 20) -> hits 5 (busts 25). Dealer: 5, 6 (11)
        mock_cards = [Card('K', 'S', 10), Card('5', 'H', 5), Card('Q', 'D', 10), Card('6', 'C', 6), Card('5', 'S', 5)]
        game.deck = MockDeck(mock_cards)
        game.start_deal() 
        
        self.assertFalse(game.is_game_over)
        game.player_hit() 
        
        self.assertTrue(game.is_game_over)
        self.assertEqual(game.outcome, 'dealer_wins')
        self.assertEqual(game.status_message, "Player busts! Dealer wins.")

    def test_player_stand_dealer_bust(self):
        """Test player standing, dealer plays and busts."""
        game = BlackjackGame(bet_amount=10)
        # Player: K, 7 (17). Dealer: Q, 6 (16) -> dealer must hit, gets J (busts 26)
        # Order: P1, D1, P2, D2, DealerHit1
        mock_cards = [Card('K', 'S', 10), Card('Q', 'H', 10), Card('7', 'D', 7), Card('6', 'C', 6), Card('J', 'S', 10)]
        game.deck = MockDeck(mock_cards)
        game.start_deal() 
        
        self.assertFalse(game.is_game_over)
        game.player_stand() 
        
        self.assertTrue(game.is_game_over)
        self.assertEqual(game.outcome, 'player_wins')
        self.assertTrue(game.dealer_hand.is_busted())
        self.assertEqual(game.status_message, "Dealer busts! Player wins.")

    def test_player_stand_player_wins(self):
        """Test player standing, player's hand is higher than dealer's (dealer doesn't bust)."""
        game = BlackjackGame(bet_amount=10)
        # Player: K, 9 (19). Dealer: Q, 7 (17) -> dealer stands on 17. Player wins.
        mock_cards = [Card('K', 'S', 10), Card('Q', 'H', 10), Card('9', 'D', 9), Card('7', 'C', 7)]
        game.deck = MockDeck(mock_cards)
        game.start_deal() 
        
        self.assertFalse(game.is_game_over)
        game.player_stand() 
        
        self.assertTrue(game.is_game_over)
        self.assertEqual(game.outcome, 'player_wins')
        self.assertEqual(game.player_hand.calculate_value(), 19)
        self.assertEqual(game.dealer_hand.calculate_value(), 17)
        self.assertIn("Player wins!", game.status_message)

    def test_player_stand_dealer_wins(self):
        """Test player standing, dealer's hand is higher than player's."""
        game = BlackjackGame(bet_amount=10)
        # Player: K, 7 (17). Dealer: Q, 9 (19) -> dealer stands on 19. Dealer wins.
        mock_cards = [Card('K', 'S', 10), Card('Q', 'H', 10), Card('7', 'D', 7), Card('9', 'C', 9)]
        game.deck = MockDeck(mock_cards)
        game.start_deal() 
        
        self.assertFalse(game.is_game_over)
        game.player_stand() 
        
        self.assertTrue(game.is_game_over)
        self.assertEqual(game.outcome, 'dealer_wins')
        self.assertIn("Dealer wins.", game.status_message)

    def test_player_stand_push(self):
        """Test player standing, results in a push (equal non-busted hands)."""
        game = BlackjackGame(bet_amount=10)
        # Player: K, 9 (19). Dealer: Q, 9 (19)
        mock_cards = [Card('K', 'S', 10), Card('Q', 'H', 10), Card('9', 'D', 9), Card('9', 'C', 9)]
        game.deck = MockDeck(mock_cards)
        game.start_deal() 
        
        self.assertFalse(game.is_game_over)
        game.player_stand() 
        
        self.assertTrue(game.is_game_over)
        self.assertEqual(game.outcome, 'push')
        self.assertIn("Push!", game.status_message)

if __name__ == '__main__':
    unittest.main()

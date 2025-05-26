import unittest
from game_logic.hand import Hand
from game_logic.card import Card

class TestHand(unittest.TestCase):
    def setUp(self):
        """Create a new hand and sample cards for each test method."""
        self.hand = Hand()
        self.card_ace = Card('A', 'Spades', 11)
        self.card_king = Card('K', 'Hearts', 10)
        self.card_queen = Card('Q', 'Diamonds', 10) # Added for more tests
        self.card_jack = Card('J', 'Clubs', 10) # Added for more tests
        self.card_ten = Card('10', 'Spades', 10) # Added for more tests
        self.card_nine = Card('9', 'Diamonds', 9)
        self.card_five = Card('5', 'Clubs', 5)
        self.card_two = Card('2', 'Hearts', 2) # Added for more tests


    def test_hand_initialization(self):
        """Test that a new hand is initialized empty with a value of 0."""
        self.assertEqual(len(self.hand.cards), 0)
        self.assertEqual(self.hand.value, 0)

    def test_add_card(self):
        """Test adding cards to the hand."""
        self.hand.add_card(self.card_king)
        self.assertEqual(len(self.hand.cards), 1)
        self.assertIn(self.card_king, self.hand.cards)

        self.hand.add_card(self.card_five)
        self.assertEqual(len(self.hand.cards), 2)
        self.assertIn(self.card_five, self.hand.cards)
        
        # Test that adding None does not change the hand (or raise error, Hand.add_card handles if card:)
        initial_len = len(self.hand.cards)
        self.hand.add_card(None)
        self.assertEqual(len(self.hand.cards), initial_len)


    def test_calculate_value_simple(self):
        """Test calculating value with non-Ace cards."""
        self.hand.add_card(self.card_king)  # 10
        self.hand.add_card(self.card_five)  # 5
        self.assertEqual(self.hand.calculate_value(), 15)

        self.hand.add_card(self.card_two) # 10 + 5 + 2 = 17
        self.assertEqual(self.hand.calculate_value(), 17)

    def test_calculate_value_with_ace(self):
        """Test calculating value with an Ace counted as 11."""
        self.hand.add_card(self.card_ace)   # 11
        self.hand.add_card(self.card_five)  # 5
        self.assertEqual(self.hand.calculate_value(), 16)

    def test_calculate_value_ace_as_one(self):
        """Test calculating value with an Ace counted as 1 when total exceeds 21."""
        self.hand.add_card(self.card_ace)   # 11 initially
        self.hand.add_card(self.card_king)  # 10
        self.hand.add_card(self.card_nine)  # 9 (11 + 10 + 9 = 30, Ace becomes 1. So, 1 + 10 + 9 = 20)
        self.assertEqual(self.hand.calculate_value(), 20)

    def test_calculate_value_multiple_aces(self):
        """Test calculating value with multiple Aces, one eventually counted as 1."""
        ace1 = Card('A', 'Spades', 11)
        ace2 = Card('A', 'Hearts', 11)
        self.hand.add_card(ace1) # 11
        self.hand.add_card(ace2) # 11 (11 + 11 = 22. One Ace becomes 1. So, 1 + 11 = 12)
        self.assertEqual(self.hand.calculate_value(), 12)
        
        self.hand.add_card(self.card_five) # 12 + 5 = 17
        self.assertEqual(self.hand.calculate_value(), 17)

    def test_calculate_value_multiple_aces_bust(self):
        """Test calculating value with multiple Aces and other cards, forcing Aces to be 1."""
        ace1 = Card('A', 'Spades', 11)
        ace2 = Card('A', 'Hearts', 11)
        king = Card('K', 'Clubs', 10)
        self.hand.add_card(ace1) # 11
        self.hand.add_card(ace2) # 11 -> becomes 1 (Hand is 11 + 1 = 12)
        self.hand.add_card(king) # 10 (Hand is 1 + 11 + 10 = 22 -> first ace is 11, second is 1. Total 12 + 10 = 22. Oh, game logic for Hand.calculate_value:
                                 # it first sums all aces as 11. Then if sum > 21, it subtracts 10 for each ace until sum <= 21.
                                 # So: ace1 (11) + ace2 (11) + king (10) = 32.
                                 # First ace conversion: 32 - 10 = 22. (ace1=1, ace2=11, king=10)
                                 # Second ace conversion: 22 - 10 = 12. (ace1=1, ace2=1, king=10)
        self.assertEqual(self.hand.calculate_value(), 12)

    def test_is_busted_false(self):
        """Test is_busted returns False when value is <= 21."""
        self.hand.add_card(self.card_king)  # 10
        self.hand.add_card(self.card_nine)  # 9 (Total 19)
        self.assertFalse(self.hand.is_busted())

        self.hand = Hand() # Reset hand
        self.hand.add_card(self.card_king) #10
        self.hand.add_card(self.card_ace) #11 (Total 21)
        self.assertFalse(self.hand.is_busted())


    def test_is_busted_true(self):
        """Test is_busted returns True when value is > 21."""
        self.hand.add_card(self.card_king)    # 10
        self.hand.add_card(self.card_five)    # 5
        self.hand.add_card(self.card_nine)    # 9 (10 + 5 + 9 = 24)
        self.assertTrue(self.hand.is_busted())

    def test_get_cards_as_strings(self):
        """Test that get_cards_as_strings returns correct list of card strings."""
        self.hand.add_card(self.card_ace)
        self.hand.add_card(self.card_king)
        expected_strings = ["A of Spades", "K of Hearts"]
        self.assertEqual(self.hand.get_cards_as_strings(), expected_strings)

        self.hand.add_card(self.card_five)
        expected_strings = ["A of Spades", "K of Hearts", "5 of Clubs"]
        self.assertEqual(self.hand.get_cards_as_strings(), expected_strings)
        
        # Test with an empty hand
        empty_hand = Hand()
        self.assertEqual(empty_hand.get_cards_as_strings(), [])

if __name__ == '__main__':
    unittest.main()

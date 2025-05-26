import unittest
from game_logic.card import Card # Assuming game_logic is in PYTHONPATH or tests run from project root

class TestCard(unittest.TestCase):
    def test_card_creation(self):
        """Test that a Card object is created with the correct rank, suit, and value."""
        card1 = Card('A', 'Spades', 11)
        self.assertEqual(card1.rank, 'A')
        self.assertEqual(card1.suit, 'Spades')
        self.assertEqual(card1.value, 11)

        card2 = Card('7', 'Diamonds', 7)
        self.assertEqual(card2.rank, '7')
        self.assertEqual(card2.suit, 'Diamonds')
        self.assertEqual(card2.value, 7)

        card3 = Card('K', 'Clubs', 10)
        self.assertEqual(card3.rank, 'K')
        self.assertEqual(card3.suit, 'Clubs')
        self.assertEqual(card3.value, 10)

    def test_card_str_representation(self):
        """Test the string representation of a Card object."""
        card1 = Card('K', 'Hearts', 10)
        self.assertEqual(str(card1), "K of Hearts")

        card2 = Card('2', 'Clubs', 2)
        self.assertEqual(str(card2), "2 of Clubs")
        
        card3 = Card('A', 'Spades', 11)
        self.assertEqual(str(card3), "A of Spades")

if __name__ == '__main__':
    unittest.main()

import unittest
from game_logic.deck import Deck
from game_logic.card import Card # For isinstance checks

class TestDeck(unittest.TestCase):
    def setUp(self):
        """Create a new deck instance for each test method."""
        self.deck = Deck()

    def test_deck_creation(self):
        """Test that a new deck has 52 unique cards."""
        self.assertEqual(len(self.deck.cards), 52)
        # Check for uniqueness: convert cards to a set of string representations
        self.assertEqual(len(set(str(card) for card in self.deck.cards)), 52)

    def test_deal_card(self):
        """Test dealing cards from the deck."""
        card1 = self.deck.deal_card()
        self.assertIsInstance(card1, Card, "Dealt item should be a Card instance.")
        self.assertEqual(len(self.deck.cards), 51, "Deck should have 51 cards after dealing one.")

        # Deal all remaining 51 cards
        for _ in range(51):
            card = self.deck.deal_card()
            self.assertIsNotNone(card, "Should be able to deal all 52 cards.")
        
        self.assertEqual(len(self.deck.cards), 0, "Deck should be empty after dealing all cards.")
        self.assertIsNone(self.deck.deal_card(), "Dealing from an empty deck should return None.")

    def test_deck_shuffle(self):
        """Test that shuffling changes the order of cards but retains all original cards."""
        # Note: Deck is shuffled on initialization. To test shuffle effectively,
        # we need a way to get a known order, or compare two shuffles,
        # or compare a deck's order before and after an explicit shuffle call.
        # The Deck() constructor already shuffles. So, we'll take its initial order,
        # then shuffle again and compare.

        initial_shuffled_order = [str(c) for c in self.deck.cards[:]] # Cards after initial shuffle in setUp

        self.deck.shuffle() # Shuffle again
        second_shuffled_order = [str(c) for c in self.deck.cards[:]]

        self.assertEqual(len(initial_shuffled_order), 52)
        self.assertEqual(len(second_shuffled_order), 52)

        # It's theoretically possible (though extremely unlikely) for a shuffle to result in the same order.
        # This test might fail in such rare cases.
        self.assertNotEqual(initial_shuffled_order, second_shuffled_order, 
                            "Deck order should ideally change after a second shuffle. (Small chance of false negative)")

        # Crucially, ensure all original cards are still present in the shuffled deck, just in a different order.
        self.assertEqual(sorted(initial_shuffled_order), sorted(second_shuffled_order),
                         "All original cards must be present after shuffle, regardless of order.")

if __name__ == '__main__':
    unittest.main()

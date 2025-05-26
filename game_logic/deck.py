import random
from .card import Card

SUITS = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

class Deck:
    """Represents a standard 52-card deck."""
    def __init__(self):
        """Initializes a new deck of cards and shuffles it."""
        self.cards = self._create_deck()
        self.shuffle()

    def _create_deck(self):
        """Creates a standard 52-card deck."""
        cards = []
        for suit in SUITS:
            for rank in RANKS:
                if rank.isdigit():
                    value = int(rank)
                elif rank in ['J', 'Q', 'K']:
                    value = 10
                elif rank == 'A':
                    value = 11  # Ace is initially 11
                cards.append(Card(rank, suit, value))
        return cards

    def shuffle(self):
        """Shuffles the deck."""
        random.shuffle(self.cards)

    def deal_card(self):
        """Removes and returns the top card from the deck. Returns None if empty."""
        if self.cards:
            return self.cards.pop()
        return None

    def __len__(self):
        return len(self.cards)

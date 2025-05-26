from .card import Card

class Hand:
    """Represents a hand of cards in Blackjack."""
    def __init__(self):
        """Initializes an empty hand."""
        self.cards = []
        self.value = 0

    def add_card(self, card: Card):
        """Adds a card to the hand and recalculates the value."""
        if card:
            self.cards.append(card)
            self.calculate_value()

    def calculate_value(self) -> int:
        """Calculates the total value of the hand. Adjusts for Aces."""
        self.value = 0
        num_aces = 0
        for card in self.cards:
            self.value += card.value
            if card.rank == 'A':
                num_aces += 1

        # Adjust for Aces if value is over 21
        while self.value > 21 and num_aces > 0:
            self.value -= 10  # Change Ace from 11 to 1
            num_aces -= 1
        return self.value

    def is_busted(self) -> bool:
        """Checks if the hand's value is over 21."""
        return self.calculate_value() > 21

    def get_cards(self) -> list[Card]:
        """Returns the list of Card objects in the hand."""
        return self.cards

    def get_cards_as_strings(self) -> list[str]:
        """Returns a list of string representations of cards in the hand."""
        return [str(card) for card in self.cards]

    def __str__(self):
        # Updated to use the new Card.__str__ if needed, or keep concise form for internal logging
        return f"{[f'{c.rank}{c.suit[0]}' for c in self.cards]} (Value: {self.calculate_value()})"

import itertools
import random
from enum import IntEnum
from dataclasses import dataclass
from typing import List, Tuple, Optional, Set, Union, Sequence, Any, Dict


class HandRank(IntEnum):
    HIGH_CARD = 1
    ONE_PAIR = 2
    TWO_PAIR = 3
    THREE_OF_A_KIND = 4
    STRAIGHT = 5
    FLUSH = 6
    FULL_HOUSE = 7
    FOUR_OF_A_KIND = 8
    STRAIGHT_FLUSH = 9
    ROYAL_FLUSH = 10

    @property
    def label(self) -> str:
        names = {
            HandRank.HIGH_CARD: "High Card",
            HandRank.ONE_PAIR: "One Pair",
            HandRank.TWO_PAIR: "Two Pair",
            HandRank.THREE_OF_A_KIND: "Three of a Kind",
            HandRank.STRAIGHT: "Straight",
            HandRank.FLUSH: "Flush",
            HandRank.FULL_HOUSE: "Full House",
            HandRank.FOUR_OF_A_KIND: "Four of a Kind",
            HandRank.STRAIGHT_FLUSH: "Straight Flush",
            HandRank.ROYAL_FLUSH: "Royal Flush"
        }
        return names.get(self, "Unknown")


RANK_MAP = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
    'T': 10, '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
}
REV_RANK_MAP = {v: k for k, v in RANK_MAP.items() if k != '10'}
REV_RANK_MAP[10] = 'T'


@dataclass(frozen=True)
class PokerCard:
    rank: int       # 2 to 14 (14 = Ace)
    suit: str       # 'h' (Hearts), 'd' (Diamonds), 'c' (Clubs), 's' (Spades)

    @classmethod
    def extract_cards(cls, raw_input: Any) -> List['PokerCard']:
        """Recursively unpacks and extracts all PokerCards from any complex nested structure (dicts, lists, json strings, ints)."""
        if raw_input is None:
            return []

        cards: List[PokerCard] = []
        if isinstance(raw_input, PokerCard):
            return [raw_input]

        if isinstance(raw_input, (int, float)):
            try:
                val = int(raw_input)
                if 2 <= val <= 14:
                    return [cls(rank=val, suit="s")]
            except Exception:
                pass
            return []

        if isinstance(raw_input, (list, tuple, set)):
            for item in raw_input:
                cards.extend(cls.extract_cards(item))
            return cards

        if isinstance(raw_input, dict):
            # Check if this dict represents a single card
            if "rank" in raw_input or "value" in raw_input:
                try:
                    c = cls.from_str(raw_input)
                    if c:
                        cards.append(c)
                        return cards
                except Exception:
                    pass
            if "card" in raw_input:
                try:
                    c = cls.from_str(raw_input["card"])
                    if c:
                        cards.append(c)
                        return cards
                except Exception:
                    pass
            # If it's a container dict like {'card_1': {...}, 'card_2': {...}} or {'flop': [...]}
            for k, v in raw_input.items():
                cards.extend(cls.extract_cards(v))
            return cards

        # If it's a string, try parsing directly or via regex if multiple cards
        s = str(raw_input).strip()
        if not s:
            return []

        # Try direct single card parse
        try:
            c = cls.from_str(s)
            if c:
                cards.append(c)
                return cards
        except Exception:
            pass

        # Regex extract multiple cards if string has multiple (e.g. "Ah Kd Qs" or "['Ah', 'Kd']")
        import re
        card_pat = re.compile(r"\b(10|[2-9TJQKA])[shdc]\b", re.IGNORECASE)
        matches = card_pat.findall(s)
        for m in matches:
            try:
                c = cls.from_str(m)
                if c:
                    cards.append(c)
            except Exception:
                pass
        return cards

    @classmethod
    def from_str(cls, card_input: Any) -> 'PokerCard':
        if isinstance(card_input, PokerCard):
            return card_input

        if isinstance(card_input, (int, float)):
            val = int(card_input)
            if 2 <= val <= 14:
                return cls(rank=val, suit="s")
            raise ValueError(f"Invalid integer card rank: {val}")

        if isinstance(card_input, dict):
            # Handle direct card dict: {'value': 'Q', 'suit': 'h'}, {'rank': '8'}, {'card': 'Jc'}
            if "card" in card_input:
                return cls.from_str(card_input["card"])
            elif "value" in card_input or "rank" in card_input:
                val = str(card_input.get("value") or card_input.get("rank") or "").strip()
                suit = str(card_input.get("suit") or card_input.get("color") or "").strip()
                if len(val) >= 2 and val[-1].lower() in ['h', 'd', 'c', 's', '♥', '♦', '♣', '♠']:
                    card_str = val
                elif suit:
                    card_str = f"{val}{suit}"
                else:
                    card_str = f"{val}s"
            else:
                # Container dict (e.g. {'card_1': {'rank': 'A', ...}, 'card_2': ...})
                extracted = cls.extract_cards(card_input)
                if extracted:
                    return extracted[0]
                card_str = "As"
        else:
            card_str = str(card_input or "")

        s = card_str.strip().upper()
        if not s:
            raise ValueError(f"Invalid card representation: '{card_input}'")

        # Single rank representation without suit (e.g. 'Q', '8', 'A', '10')
        if len(s) == 1 or s == "10":
            if s in RANK_MAP:
                return cls(rank=RANK_MAP[s], suit="s")

        if s.startswith("10"):
            rank_str = "10"
            suit_str = s[2:].lower()
        else:
            rank_str = s[0]
            suit_str = s[1:].lower()

        if rank_str not in RANK_MAP:
            # Check if entire string is an int within range
            try:
                num_val = int(s)
                if 2 <= num_val <= 14:
                    return cls(rank=num_val, suit="s")
            except Exception:
                pass
            raise ValueError(f"Unknown card rank: '{rank_str}' in '{card_input}'")

        suit_map = {
            'h': 'h', 'd': 'd', 'c': 'c', 's': 's',
            '♥': 'h', '♦': 'd', '♣': 'c', '♠': 's',
            'hearts': 'h', 'diamonds': 'd', 'clubs': 'c', 'spades': 's',
            'heart': 'h', 'diamond': 'd', 'club': 'c', 'spade': 's',
            'rot': 'h', 'red': 'h', 'schwarz': 's', 'black': 's'
        }
        suit_str = suit_map.get(suit_str.lower(), 's')

        rank_val = RANK_MAP[rank_str]
        return cls(rank=rank_val, suit=suit_str)

    def __str__(self) -> str:
        return f"{REV_RANK_MAP.get(self.rank, str(self.rank))}{self.suit}"

    def __repr__(self) -> str:
        return self.__str__()


class PokerHandEvaluator:
    """High-performance 5-card & 7-card Texas Hold'em evaluator with Monte-Carlo simulation."""

    @staticmethod
    def get_full_deck() -> List[PokerCard]:
        deck = []
        for r in range(2, 15):
            for s in ['h', 'd', 'c', 's']:
                deck.append(PokerCard(rank=r, suit=s))
        return deck

    @classmethod
    def evaluate_5cards(cls, cards: List[PokerCard]) -> Tuple[HandRank, List[int]]:
        """
        Evaluates a 5-card hand.
        Returns a tuple (HandRank, tie_breaker_values_descending).
        """
        if len(cards) != 5:
            raise ValueError("evaluate_5cards requires exactly 5 cards.")

        ranks = sorted([c.rank for c in cards], reverse=True)
        suits = [c.suit for c in cards]
        is_flush = len(set(suits)) == 1

        # Check Straight
        unique_ranks = sorted(list(set(ranks)), reverse=True)
        is_straight = False
        straight_high = 0

        if len(unique_ranks) == 5:
            if unique_ranks[0] - unique_ranks[4] == 4:
                is_straight = True
                straight_high = unique_ranks[0]
            elif unique_ranks == [14, 5, 4, 3, 2]: # Steel Wheel (Ace-to-Five)
                is_straight = True
                straight_high = 5

        # Straight Flush & Royal Flush
        if is_flush and is_straight:
            if straight_high == 14:
                return (HandRank.ROYAL_FLUSH, [14])
            return (HandRank.STRAIGHT_FLUSH, [straight_high])

        # Rank frequency counts
        rank_counts: dict[int, int] = {}
        for r in ranks:
            rank_counts[r] = rank_counts.get(r, 0) + 1

        # Group by frequency, then by rank descending
        # Example for Full House (3 Kings, 2 Aces): [(3, 13), (2, 14)]
        grouped = sorted([(count, r) for r, count in rank_counts.items()], reverse=True)

        counts = [g[0] for g in grouped]
        ordered_ranks = [g[1] for g in grouped]

        # Four of a Kind
        if counts == [4, 1]:
            return (HandRank.FOUR_OF_A_KIND, ordered_ranks)

        # Full House
        if counts == [3, 2]:
            return (HandRank.FULL_HOUSE, ordered_ranks)

        # Flush
        if is_flush:
            return (HandRank.FLUSH, ranks)

        # Straight
        if is_straight:
            return (HandRank.STRAIGHT, [straight_high])

        # Three of a Kind
        if counts == [3, 1, 1]:
            return (HandRank.THREE_OF_A_KIND, ordered_ranks)

        # Two Pair
        if counts == [2, 2, 1]:
            return (HandRank.TWO_PAIR, ordered_ranks)

        # One Pair
        if counts == [2, 1, 1, 1]:
            return (HandRank.ONE_PAIR, ordered_ranks)

        # High Card
        return (HandRank.HIGH_CARD, ranks)

    @classmethod
    def evaluate_7cards(cls, cards: List[PokerCard]) -> Tuple[HandRank, List[int]]:
        """Evaluates best 5-card hand out of 5, 6 or 7 cards."""
        if len(cards) < 5:
            raise ValueError(f"Need at least 5 cards to evaluate hand, got {len(cards)}")
        if len(cards) == 5:
            return cls.evaluate_5cards(cards)

        best_rank: Optional[HandRank] = None
        best_tie: List[int] = []

        for combo in itertools.combinations(cards, 5):
            rank, tie = cls.evaluate_5cards(list(combo))
            if best_rank is None or (rank > best_rank) or (rank == best_rank and tie > best_tie):
                best_rank = rank
                best_tie = tie

        return (best_rank or HandRank.HIGH_CARD, best_tie)

    @classmethod
    def compare_hands(cls, hand1: List[PokerCard], hand2: List[PokerCard]) -> int:
        """Returns 1 if hand1 wins, -1 if hand2 wins, 0 on tie."""
        r1, tie1 = cls.evaluate_7cards(hand1)
        r2, tie2 = cls.evaluate_7cards(hand2)
        if r1 > r2:
            return 1
        elif r1 < r2:
            return -1
        else:
            if tie1 > tie2:
                return 1
            elif tie1 < tie2:
                return -1
            return 0

    @classmethod
    def calculate_equity_monte_carlo(
        cls,
        my_hole_cards: Sequence[Union[PokerCard, str]],
        community_cards: Optional[Sequence[Union[PokerCard, str]]] = None,
        num_opponents: int = 1,
        iterations: int = 3000
    ) -> dict[str, float]:
        """
        Simulates random runouts against random opponent hands to calculate exact Hand Equity.
        Returns: {'win_rate': float, 'tie_rate': float, 'loss_rate': float, 'equity': float}
        """
        my_cards = [c if isinstance(c, PokerCard) else PokerCard.from_str(c) for c in my_hole_cards]
        comm_cards = [c if isinstance(c, PokerCard) else PokerCard.from_str(c) for c in (community_cards or [])]

        used_cards = set(my_cards + comm_cards)
        full_deck = [c for c in cls.get_full_deck() if c not in used_cards]

        needed_comm = 5 - len(comm_cards)
        needed_opp_cards = num_opponents * 2

        if len(full_deck) < (needed_comm + needed_opp_cards):
            return {"win_rate": 0.0, "tie_rate": 0.0, "loss_rate": 1.0, "equity": 0.0}

        wins = 0
        ties = 0
        losses = 0

        for _ in range(iterations):
            sampled = random.sample(full_deck, needed_comm + needed_opp_cards)
            runout_comm = comm_cards + sampled[:needed_comm]
            offset = needed_comm

            my_final_hand = my_cards + runout_comm
            my_eval = cls.evaluate_7cards(my_final_hand)

            is_loss = False
            is_tie = False

            for opp_idx in range(num_opponents):
                opp_cards = sampled[offset:offset + 2]
                offset += 2
                opp_final_hand = opp_cards + runout_comm
                opp_eval = cls.evaluate_7cards(opp_final_hand)

                if opp_eval > my_eval:
                    is_loss = True
                    break
                elif opp_eval == my_eval:
                    is_tie = True

            if is_loss:
                losses += 1
            elif is_tie:
                ties += 1
            else:
                wins += 1

        total = float(iterations)
        win_rate = wins / total
        tie_rate = ties / total
        loss_rate = losses / total
        equity = (wins + (ties / (num_opponents + 1))) / total

        return {
            "win_rate": round(win_rate, 4),
            "tie_rate": round(tie_rate, 4),
            "loss_rate": round(loss_rate, 4),
            "equity": round(equity, 4)
        }

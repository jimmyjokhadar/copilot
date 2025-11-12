# user_context.py
from dataclasses import dataclass
from typing import Any, Dict, List
from pymongo.collection import Collection

@dataclass
class UserDataContext:
    client_id: str
    cards_col: Collection
    transactions_col: Collection

    def get_cards(self) -> List[Dict[str, Any]]:
        return list(self.cards_col.find({"clientId": self.client_id}))

    def get_card(self, card_number: str) -> Dict[str, Any] | None:
        return self.cards_col.find_one({"clientId": self.client_id, "cardNumber": card_number})

    def update_pin(self, card_number: str, new_hash: str) -> int:
        res = self.cards_col.update_one(
            {"clientId": self.client_id, "cardNumber": card_number},
            {"$set": {"pinHash": new_hash}},
        )
        return res.modified_count

    def get_transactions(self, card_number: str) -> List[Dict[str, Any]]:
        card = self.get_card(card_number)
        if not card:
            return []
        return card.get("transactions", [])

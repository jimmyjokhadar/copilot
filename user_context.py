# user_context.py
from dataclasses import dataclass
from typing import Any, Dict, List
from pymongo.collection import Collection

@dataclass
class UserDataContext:
    """
    User-scoped access to banking data.
    The LLM never sees client_id. It's only used inside this class.
    """
    client_id: str
    cards_col: Collection
    transactions_col: Collection

    # READ operations
    def get_cards(self) -> List[Dict[str, Any]]:
        return list(self.cards_col.find({"clientId": self.client_id}))

    def get_card_by_token(self, card_token: str) -> Dict[str, Any] | None:
        return self.cards_col.find_one({"clientId": self.client_id, "cardToken": card_token})

    def get_transactions(self, limit: int = 10) -> List[Dict[str, Any]]:
        return list(
            self.transactions_col.find({"clientId": self.client_id})
            .sort("date", -1)
            .limit(limit)
        )

    # WRITE operations (still scoped to this user only)
    def update_card_pin(self, card_token: str, new_hash: str) -> int:
        res = self.cards_col.update_one(
            {"clientId": self.client_id, "cardToken": card_token},
            {"$set": {"pinHash": new_hash}},
        )
        return res.modified_count

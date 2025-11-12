import bcrypt
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
from typing import List
from datetime import datetime

from user_context import UserDataContext


class ChangePINInput(BaseModel):
    cardNumber: str = Field(..., description="The card number associated with the PIN.")
    old_pin: str = Field(..., description="The current PIN code.")
    new_pin: str = Field(..., description="The new PIN code to set.")



class ViewCardDetailsInput(BaseModel):
    pass



class ListRecentTransactionsInput(BaseModel):
    cardNumber: str = Field(..., description="The card number associated with the transactions.")
    count: int = Field(5, description="Number of recent transactions to retrieve.")



class ListTransactionsDateRangeInput(BaseModel):
    cardNumber: str = Field(..., description="The card number associated with the transactions.")
    start_date: str = Field(..., description="Start date in DDMMYYYY format.")
    end_date: str = Field(..., description="End date in DDMMYYYY format.")



def build_banking_tools(user_ctx: UserDataContext) -> List[StructuredTool]:

    def change_pin(cardNumber: str, old_pin: str, new_pin: str) -> str:
        cards = user_ctx.get_cards()
        if not cards:
            return "No cards found for this user."

        card = user_ctx.get_card(cardNumber)
        if not card:
            return "No matching card found for this user."

        pin_hash = card.get("pinHash")
        if not pin_hash:
            return "This card has no PIN set."

        if not bcrypt.checkpw(old_pin.encode(), pin_hash.encode()):
            return "The old PIN is incorrect."

        new_hash = bcrypt.hashpw(new_pin.encode(), bcrypt.gensalt()).decode()
        modified = user_ctx.update_pin(cardNumber, new_hash)
        if modified:
            return "PIN changed successfully."
        return "PIN update failed."

    change_pin_tool = StructuredTool.from_function(
        func=change_pin,
        name="change_pin",
        description="Change the PIN for this user's specified card.",
        args_schema=ChangePINInput,
    )

    def view_card_details() -> str:
        cards = user_ctx.get_cards()
        if not cards:
            return "No cards found for this user."

        details = ""
        for idx, card in enumerate(cards, start=1):
            masked = (
                "**** **** **** " + card["cardNumber"][-4:]
                if len(card.get("cardNumber", "")) >= 4
                else "N/A"
            )
            details += f"--- Card {idx} ---\n"
            details += f"Card Number: {masked}\n"
            details += f"Expiry Date: {card.get('expiryDate', 'N/A')}\n"
            details += f"Status: {card.get('status', 'N/A')}\n"
            details += f"Type: {card.get('type', 'N/A')}\n"
            details += f"Currency: {card.get('currency', 'N/A')}\n"
            details += f"Available Balance: {card.get('availableBalance', 'N/A')}\n"
            details += f"Current Balance: {card.get('currentBalance', 'N/A')}\n\n"
        return details.strip()

    view_card_details_tool = StructuredTool.from_function(
        func=view_card_details,
        name="view_card_details",
        description="View all card details for this user.",
        args_schema=ViewCardDetailsInput,
    )

    def list_recent_transactions(cardNumber: str, count: int = 5) -> str:
        txns = user_ctx.get_transactions(cardNumber)
        if not txns:
            return "No transactions found."

        recent = txns[:count]
        lines = []
        for t in recent:
            lines.append(
                f"{t.get('date', 'N/A')} {t.get('time', '')} | "
                f"{t.get('transactionAmount', 'N/A')} {t.get('transactionCurrency', '')} | "
                f"{t.get('terminalLocation', 'N/A')} | {t.get('responseCodeDescription', '')}"
            )
        return "\n".join(lines)

    list_recent_transactions_tool = StructuredTool.from_function(
        func=list_recent_transactions,
        name="list_recent_transactions",
        description="List the most recent transactions for a given card.",
        args_schema=ListRecentTransactionsInput,
    )

    # --- List Transactions by Date Range ---
    def list_transactions_date_range(cardNumber: str, start_date: str, end_date: str) -> str:
        txns = user_ctx.get_transactions(cardNumber)
        if not txns:
            return "No transactions available for this card."

        filtered = [t for t in txns if start_date <= t.get("date", "") <= end_date]
        if not filtered:
            return f"No transactions between {start_date} and {end_date}."

        lines = []
        for t in filtered:
            lines.append(
                f"{t.get('date', 'N/A')} {t.get('time', '')} | "
                f"{t.get('transactionAmount', 'N/A')} {t.get('transactionCurrency', '')} | "
                f"{t.get('terminalLocation', 'N/A')} | {t.get('responseCodeDescription', '')}"
            )
        return "\n".join(lines)

    list_transactions_date_range_tool = StructuredTool.from_function(
        func=list_transactions_date_range,
        name="list_transactions_date_range",
        description="List all transactions for a given card in a specific date range.",
        args_schema=ListTransactionsDateRangeInput,
    )

    return [
        change_pin_tool,
        view_card_details_tool,
        list_recent_transactions_tool,
        list_transactions_date_range_tool,
    ]


# --- Manual test ---
if __name__ == "__main__":
    from pymongo import MongoClient
    from dotenv import load_dotenv
    import os

    load_dotenv()
    client = MongoClient(os.getenv("MONGO_URI"))
    db = client["fransa_demo"]

    from user_context import UserDataContext

    ctx = UserDataContext("1001", db["cards"], db["transactions"])
    tools = build_banking_tools(ctx)

    print(tools[0].invoke({"cardNumber": "5007673290469960", "old_pin": "0000", "new_pin": "1234"}))
    print(tools[1].invoke({}))  # view_card_details
    print(tools[2].invoke({"cardNumber": "5007673290469960", "count": 3}))
    print(tools[3].invoke({"cardNumber": "5007673290469960", "start_date": "23102025", "end_date": "24102025"}))

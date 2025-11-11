import bcrypt
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from pprint import pprint
import bcrypt
from datetime import datetime
from contextvars import ContextVar
load_dotenv()

# Thread-safe context variable to store authenticated clientId
_authenticated_client_id: ContextVar[str | None] = ContextVar('authenticated_client_id', default=None)

def set_authenticated_client_id(client_id: str | None):
    """Set the authenticated client ID for the current context."""
    _authenticated_client_id.set(client_id)

def get_authenticated_client_id() -> str | None:
    """Get the authenticated client ID for the current context."""
    return _authenticated_client_id.get()

def verify_client_access(requested_client_id: str | None = None) -> tuple[bool, str, str | None]:
    """
    Verify that the user has access to the requested client ID.
    Returns: (is_authorized, error_message, authenticated_client_id)
    """
    authenticated_id = get_authenticated_client_id()
    
    if not authenticated_id:
        return False, "❌ Authentication required. Please authenticate via Slack.", None
    
    # If a clientId is explicitly requested, verify it matches the authenticated user
    if requested_client_id and requested_client_id != authenticated_id:
        return False, f"❌ Access denied. You are not authorized to access client ID {requested_client_id}.", authenticated_id
    
    return True, "", authenticated_id

###### Change PIN Tool ######

class ChangePINInput(BaseModel):
    cardNumber: str = Field(..., description="The card number associated with the PIN.")
    old_pin: str = Field(..., description="The current PIN code.")
    new_pin: str = Field(..., description="The new PIN code to set.")

def change_pin(cardNumber: str, old_pin: str, new_pin: str) -> str:
    """Change a user's PIN stored in MongoDB after verifying the old PIN."""
    # Security check
    is_authorized, error_msg, clientId = verify_client_access()
    if not is_authorized:
        return error_msg
    
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        return "MONGO_URI not set in environment."

    client = MongoClient(mongo_uri)
    db = client["fransa_demo"]  # adjust DB name
    cards = db["cards"]  # adjust collection name

    user_cards = list(cards.find({"clientId": clientId, "cardNumber": {"$exists": True}}))

    if not user_cards:
        return f"Either no client found with clientId {clientId} or no card associated."
    elif len(user_cards) == 1:
        user = user_cards[0]
    else:
        if cardNumber:
            user = cards.find_one({"clientId": clientId, "cardNumber": cardNumber})
            if not user:
                return f"No card found for clientId {clientId} with cardNumber {cardNumber}."

    pin_hash = user.get("pinHash")
    if not pin_hash:
        return "No existing PIN found. Cannot change PIN."

    if not bcrypt.checkpw(old_pin.encode(), pin_hash.encode()):
        return "The old PIN provided is incorrect."

    new_hash = bcrypt.hashpw(new_pin.encode(), bcrypt.gensalt()).decode()

    result = cards.update_one(
        {"clientId": clientId},
        {"$set": {"pinHash": new_hash}}
    )

    if result.modified_count == 1:
        return "PIN changed successfully."
    else:
        return "PIN change failed. Try again."

change_pin_tool = StructuredTool.from_function(
    func=change_pin,
    name="change_pin",
    description="Changes the authenticated user's PIN in MongoDB after verifying the old PIN. Uses the authenticated client ID from Slack.",
    args_schema=ChangePINInput
)

###### View Card Details Tool ######
#__________________________________#

class ViewCardDetailsInput(BaseModel):
    pass  # No parameters needed - uses authenticated client ID

def view_card_details() -> str:
    """Fetch and display card details for the authenticated user from MongoDB."""
    # Security check
    is_authorized, error_msg, clientId = verify_client_access()
    if not is_authorized:
        return error_msg
    
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        return "MONGO_URI not set in environment."

    client = MongoClient(mongo_uri)
    db = client["fransa_demo"]  # adjust DB name
    cards = db["cards"]  # adjust collection name

    users = list(cards.find({"clientId": clientId}))
    print(f"[DEBUG] view_card_details fetched users: {users}")

    if len(users) == 0:
        return f"No card found for clientId {clientId}."
    
    
    cards = []
    for user in users:
        user_card_number = user.get("cardNumber", "N/A")
        if user_card_number != "N/A" and len(user_card_number) >= 4:
            masked_card_number = "**** **** **** " + user_card_number[-4:]
        else:
            masked_card_number = "N/A"
        card_info = {
            "Card Number": masked_card_number,
            "Expiry Date": user.get("expiryDate", "N/A"),
            "Status": user.get("status", "N/A"),
            "Type": user.get("type", "N/A"),
            "Product Type": user.get("productType", "N/A"),
            "Currency": user.get("currency", "N/A"),
            "Available Balance": user.get("availableBalance", "N/A"),
            "Current Balance": user.get("currentBalance", "N/A"),
            "Card Limit": user.get("cardLimit", "N/A"),
            "Cashback Percentage": user.get("cashback", "N/A"),
        }
        cards.append(card_info)

    details = ""
    for idx, card in enumerate(cards, start=1):
        details += f"--- Card {idx} ---\n"
        for key, value in card.items():
            details += f"{key}: {value}\n"
        details += "\n"
    return details

view_card_details_tool = StructuredTool.from_function(
    func=view_card_details,
    name="view_card_details",
    description="Retrieves and displays the authenticated user's card details from MongoDB. Uses the authenticated client ID from Slack.",
    args_schema=ViewCardDetailsInput
)
###### List Recent Transactions Tool ######
#_________________________________________#

class ListRecentTransactionsInput(BaseModel):
    cardNumber: str = Field(..., description="The card number associated with the transactions.")
    count: int = Field(5, description="Number of recent transactions to retrieve.")

def list_recent_transactions(cardNumber: str, count: int = 5) -> str:
    """Retrieve and list recent transactions for the authenticated user from MongoDB."""
    # Security check
    is_authorized, error_msg, clientId = verify_client_access()
    if not is_authorized:
        return error_msg
    
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        return "MONGO_URI not set in environment."

    client = MongoClient(mongo_uri)
    db = client["fransa_demo"]
    cards = db["cards"]

    user_cards = list(cards.find({"clientId": clientId, "cardNumber": {"$exists": True}}))

    if not user_cards:
        return f"Either no client found with clientId {clientId} or no card associated."
    elif len(user_cards) == 1:
        user = user_cards[0]
    else:
        if cardNumber:
            user = cards.find_one({"clientId": clientId, "cardNumber": cardNumber})
            if not user:
                return f"No card found for clientId {clientId} with cardNumber {cardNumber}."

    transactions = user.get("transactions", [])
    if not transactions:
        return "No transactions found."

    recent_transactions = transactions[:count]
    transaction_details = []
    for txn in recent_transactions:
        detail = f"""
Date: {txn.get('date', 'N/A')}  Time: {txn.get('time', 'N/A')}
Terminal Location: {txn.get('terminalLocation', 'N/A')}
Amount: {txn.get('transactionAmount', 'N/A')}
Currency: {txn.get('transactionCurrency', 'N/A')}
Response: {txn.get('responseCodeDescription', 'N/A')}
Reference Number: {txn.get('referenceNumber', 'N/A')}
""".strip()
        transaction_details.append(detail)

    return "\n\n".join(transaction_details)

list_recent_transactions_tool = StructuredTool.from_function(
    func=list_recent_transactions,
    name="list_recent_transactions",
    description="Lists recent transactions for the authenticated user fetched from MongoDB (fransa_demo.cards). Uses the authenticated client ID from Slack.",
    args_schema=ListRecentTransactionsInput
)

###### List Transactions Per Date Range Tool ######

class ListTransactionsDateRangeInput(BaseModel):
    cardNumber: str = Field(..., description="The card number associated with the transactions.")
    start_date: str = Field(..., description="Start date in DDMMYYYY format.")
    end_date: str = Field(..., description="End date in DDMMYYYY format.")

def list_transactions_date_range(cardNumber: str, start_date: str, end_date: str) -> str:
    """Retrieve all transactions for the authenticated user within a given date range from MongoDB."""
    # Security check
    is_authorized, error_msg, clientId = verify_client_access()
    if not is_authorized:
        return error_msg
    
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        return "MONGO_URI not set in environment."

    client = MongoClient(mongo_uri)
    db = client["fransa_demo"]
    cards = db["cards"]

    user_cards = list(cards.find({"clientId": clientId, "cardNumber": {"$exists": True}}))

    if not user_cards:
        return f"Either no client found with clientId {clientId} or no card associated."
    elif len(user_cards) == 1:
        user = user_cards[0]
    else:
        if cardNumber:
            user = cards.find_one({"clientId": clientId, "cardNumber": cardNumber})
            if not user:
                return f"No card found for clientId {clientId} with cardNumber {cardNumber}."

    transactions = user.get("transactions", [])
    if not transactions:
        return "No transactions found for this user."

    filtered_transactions = [
        txn for txn in transactions
        if start_date <= txn.get("date", "") <= end_date
    ]

    if not filtered_transactions:
        return f"No transactions found between {start_date} and {end_date}."

    transaction_details = []
    for txn in filtered_transactions:
        detail = f"""
Date: {txn.get('date', 'N/A')}  Time: {txn.get('time', 'N/A')}
Terminal Location: {txn.get('terminalLocation', 'N/A')}
Amount: {txn.get('transactionAmount', 'N/A')}
Currency: {txn.get('transactionCurrency', 'N/A')}
Response: {txn.get('responseCodeDescription', 'N/A')}
Reference Number: {txn.get('referenceNumber', 'N/A')}
""".strip()
        transaction_details.append(detail)

    return "\n\n".join(transaction_details)

list_transactions_date_range_tool = StructuredTool.from_function(
    func=list_transactions_date_range,
    name="list_transactions_date_range",
    description="Lists all transactions for the authenticated user within a given date range from MongoDB (fransa_demo.cards). Uses the authenticated client ID from Slack.",
    args_schema=ListTransactionsDateRangeInput
)

if __name__ == "__main__":
    # Example usage - must set authenticated client ID first
    print("----- Setting authenticated client ID -----")
    set_authenticated_client_id("1001")
    print("----- Change PIN Example -----")
    print(change_pin("5007673290469960", "0000", "1234"))
    print("\n----- View Card Details Example -----")
    print(view_card_details())
    print("\n----- List Recent Transactions Example -----")
    print(list_recent_transactions("5007673290469960", 3))
    print("\n----- List Transactions Date Range Example -----")
    print(list_transactions_date_range("5007673290469960", "23102025", "23102025"))
import bcrypt
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from pprint import pprint
import bcrypt
from datetime import datetime
load_dotenv()

###### Change PIN Tool ######
#___________________________#

class ChangePINInput(BaseModel):
    clientId: str = Field(..., description="Client ID to identify the user in the database.")
    old_pin: str = Field(..., description="The current PIN code.")
    new_pin: str = Field(..., description="The new PIN code to set.")

def change_pin(clientId: str, old_pin: str, new_pin: str) -> str:
    """Change a user's PIN stored in MongoDB after verifying the old PIN."""
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        return "MONGO_URI not set in environment."

    client = MongoClient(mongo_uri)
    db = client["fransa_demo"]  # adjust DB name
    cards = db["cards"]  # adjust collection name

    user = cards.find_one({"clientId": clientId})
    if not user:
        return f"No user found with clientId {clientId}."

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
    description="Changes the user's PIN in MongoDB after verifying the old PIN.",
    args_schema=ChangePINInput
)

###### View Card Details Tool ######
#__________________________________#

class ViewCardDetailsInput(BaseModel):
    clientId: str = Field(..., description="Client ID to identify the user's card in the database.")

def view_card_details(clientId: str) -> str:
    """Fetch and display card details for a given clientId from MongoDB."""
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        return "MONGO_URI not set in environment."

    client = MongoClient(mongo_uri)
    db = client["fransa_demo"]  # adjust DB name
    cards = db["cards"]  # adjust collection name

    user = cards.find_one({"clientId": clientId})
    if not user:
        return f"No card found for clientId {clientId}."

    card_info = {
        "Card Number": user.get("cardNumber", "N/A"),
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

    details = "\n".join([f"{key}: {value}" for key, value in card_info.items()])
    return details

view_card_details_tool = StructuredTool.from_function(
    func=view_card_details,
    name="view_card_details",
    description="Retrieves and displays the user's card details from MongoDB.",
    args_schema=ViewCardDetailsInput
)
###### List Recent Transactions Tool ######
#_________________________________________#

class ListRecentTransactionsInput(BaseModel):
    clientId: str = Field(..., description="Client ID to identify the user's card in the database.")
    count: int = Field(5, description="Number of recent transactions to retrieve.")

def list_recent_transactions(clientId: str, count: int = 5) -> str:
    """Retrieve and list recent transactions for a user from MongoDB."""
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        return "MONGO_URI not set in environment."

    client = MongoClient(mongo_uri)
    db = client["fransa_demo"]
    cards = db["cards"]

    user = cards.find_one({"clientId": clientId})
    if not user:
        return f"No card found for clientId {clientId}."

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
    description="Lists recent transactions for a user fetched from MongoDB (fransa_demo.cards).",
    args_schema=ListRecentTransactionsInput
)

###### List Transactions Per Date Range Tool ######

class ListTransactionsDateRangeInput(BaseModel):
    clientId: str = Field(..., description="Client ID to identify the user's card in the database.")
    start_date: str = Field(..., description="Start date in YYYYMMDD format.")
    end_date: str = Field(..., description="End date in YYYYMMDD format.")

def list_transactions_date_range(clientId: str, start_date: str, end_date: str) -> str:
    """Retrieve all transactions for a user within a given date range from MongoDB."""
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        return "MONGO_URI not set in environment."

    client = MongoClient(mongo_uri)
    db = client["fransa_demo"]
    cards = db["cards"]

    user = cards.find_one({"clientId": clientId})
    if not user:
        return f"No card found for clientId {clientId}."

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
    description="Lists all transactions for a user within a given date range from MongoDB (fransa_demo.cards).",
    args_schema=ListTransactionsDateRangeInput
)

if __name__ == "__main__":
    pass 
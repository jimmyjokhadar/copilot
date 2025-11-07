import bcrypt
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
from pymongo import MongoClient
from dotenv import load_dotenv
import os

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
    USER_DATA: dict = Field(..., description="User data containing transaction information.")
    count: int = Field(5, description="Number of recent transactions to retrieve.")

def list_recent_transactions(USER_DATA: dict, count: int) -> str:
    transactions = USER_DATA.get("transactions", [])
    recent_transactions = transactions[:count]
    if not recent_transactions:
        return "No transactions found."
    transaction_details = []
    for txn in recent_transactions:
        detail = f"""
Date: {txn.get('date', 'N/A')} Time: {txn.get('time', 'N/A')},
Terminal Location: {txn.get('terminalLocation', 'N/A')},
Amount: {txn.get('transactionAmount', 'N/A')},
Currency: {txn.get('transactionCurrency', 'N/A')},
Response: {txn.get('responseCodeDescription', 'N/A')}
Reference Number: {txn.get('referenceNumber', 'N/A')}
""".strip()
        transaction_details.append(detail)
    return "\n".join(transaction_details)

list_recent_transactions_tool = StructuredTool.from_function(
    func=list_recent_transactions,
    name="list_recent_transactions",
    description="Lists recent transactions made with the user's card.",
    args_schema=ListRecentTransactionsInput
)

###### List Transactions Per Date Range Tool ######
#_________________________________________________#

class ListTransactionsDateRangeInput(BaseModel):
    USER_DATA: dict = Field(..., description="User data containing transaction information.")
    start_date: str = Field(..., description="Start date in YYYYMMDD format.")
    end_date: str = Field(..., description="End date in YYYYMMDD format.")

def list_transactions_date_range(USER_DATA: dict, start_date: str, end_date: str) -> str:
    transactions = USER_DATA.get("transactions", [])
    filtered_transactions = [
        txn for txn in transactions
        if start_date <= txn.get("date", "") <= end_date
    ]
    if not filtered_transactions:
        return "No transactions found in the specified date range."
    transaction_details = []
    for txn in filtered_transactions:
        detail = f"""
Date: {txn.get('date', 'N/A')} Time: {txn.get('time', 'N/A')},
Terminal Location: {txn.get('terminalLocation', 'N/A')},
Amount: {txn.get('transactionAmount', 'N/A')},
Currency: {txn.get('transactionCurrency', 'N/A')},
Response: {txn.get('responseCodeDescription', 'N/A')}
Reference Number: {txn.get('referenceNumber', 'N/A')}
- 
""".strip()
        transaction_details.append(detail)
    return "\n".join(transaction_details)

list_transactions_date_range_tool = StructuredTool.from_function(
    func=list_transactions_date_range,
    name="list_transactions_date_range",
    description="Lists transactions made with the user's card within a specified date range.",
    args_schema=ListTransactionsDateRangeInput
)

if __name__ == "__main__":
    USER_DATA = {
        "_id": {
            "$oid": "690d99a78d4d382f6faeceb9"
        },
        "clientId": "1001",
        "cardToken": "?A96CEEA242F1F97",
        "cardNumber": "5000214044289662",
        "type": "DEBIT",
        "productType": "CLASSIC",
        "currency": "840",
        "limitProfile": "MTY-CC1",
        "status": "A",
        "expiryDate": "30112025",
        "cvv2": "733",
        "pinHash": "$2b$12$/O8cPcOSS1BUOg2QKHgNQux6vinIivi5bhJEUJzOq6EtibnWzn9q2",
        "availableBalance": 125,
        "currentBalance": 125,
        "cashback": 12.5,
        "minimumPayment": 10,
        "pendingAuthorization": 0,
        "reissue": "N",
        "statusReason": "",
        "transactions": [
            {
            "date": "28102025",
            "terminalLocation": "STORE X",
            "transactionStatus": "Posted",
            "stanNumber": "070303081853",
            "terminalId": "FSB",
            "responseCodeDescription": "APPROVED TRANSACTION",
            "responseCode": "00",
            "transactionType": "10",
            "referenceNumber": "070303081853",
            "transactionAmount": "12.75",
            "currency": "840",
            "time": "070303",
            "transactionTypeDescription": "PURCHASE - POS"
            },
            {
            "date": "31102025",
            "terminalLocation": "REBATE",
            "transactionStatus": "Posted",
            "stanNumber": "070303081890",
            "terminalId": "FSB",
            "responseCodeDescription": "APPROVED TRANSACTION",
            "responseCode": "00",
            "transactionType": "23",
            "referenceNumber": "070303081890",
            "transactionAmount": "55.00",
            "currency": "840",
            "time": "070303",
            "transactionTypeDescription": "MEMO-CREDIT ADJUSTMENT"
            },
            {
            "date": "06112025",
            "terminalLocation": "ECOMMERCE Y",
            "transactionStatus": "Posted",
            "stanNumber": "070303081902",
            "terminalId": "FSB",
            "responseCodeDescription": "APPROVED TRANSACTION",
            "responseCode": "00",
            "transactionType": "11",
            "referenceNumber": "070303081902",
            "transactionAmount": "8.90",
            "currency": "840",
            "time": "070303",
            "transactionTypeDescription": "PURCHASE - ECOM"
            }
        ],
        "embossingName1": "RAMI K",
        "embossingName2": "",
        "firstName": "Rami",
        "lastName": "Khoury",
        "address1": "Hamra Street 12",
        "city": "Beirut",
        "mobile": "+96170123456",
        "dob": "1990-01-10",
        "marital": "S",
        "gender": "M",
        "email": "rami.k@example.com",
        "channelId": "MOB",
        "cardLimit": "0",
        "design": ""
    }
    # Example usage of the tools
    print("---- Change PIN Tool ----")
    print("Case 1: Incorrect old PIN")
    print(change_pin_tool.func(USER_DATA, "1234", "5678"))
    print("Case 2: Correct old PIN")
    print(change_pin_tool.func(USER_DATA, "0000", "5678"))
    print("Verifying new PIN by changing it back:")
    print(change_pin_tool.func(USER_DATA, "5678", "0000"))

    print("\n---- View Card Details Tool ----")
    print(view_card_details_tool.func(USER_DATA))

    print("\n---- List Recent Transactions Tool ----")
    print(list_recent_transactions_tool.func(USER_DATA, 2))

    print("\n---- List Transactions Per Date Range Tool ----")
    print(list_transactions_date_range(USER_DATA, "28102025", "28102025"))
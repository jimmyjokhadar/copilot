import os
from pprint import pprint
from datetime import datetime
from tools.mcptools import (
    change_pin,
    view_card_details,
    list_recent_transactions,
    list_transactions_date_range
)
import bcrypt
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# Setup: Ensure Mongo URI is defined
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise EnvironmentError("MONGO_URI not found in .env")

client = MongoClient(MONGO_URI)
db = client["fransa_demo"]
cards = db["cards"]

# Clean up previous test doc if exists
cards.delete_many({"clientId": "9999"})

# Create mock test data
hashed_pin = bcrypt.hashpw("1234".encode(), bcrypt.gensalt()).decode()

mock_user = {
    "clientId": "9999",
    "cardNumber": "5000214044289662",
    "expiryDate": "30112025",
    "status": "A",
    "type": "DEBIT",
    "productType": "CLASSIC",
    "currency": "840",
    "availableBalance": 1500.75,
    "currentBalance": 1800.50,
    "cardLimit": 2000,
    "cashback": 10.5,
    "pinHash": hashed_pin,
    "transactions": [
        {
            "date": "20251028",
            "time": "14:25:00",
            "terminalLocation": "Beirut Mall",
            "transactionAmount": "25.50",
            "transactionCurrency": "USD",
            "responseCodeDescription": "Approved",
            "referenceNumber": "TXN001"
        },
        {
            "date": "20251027",
            "time": "09:10:00",
            "terminalLocation": "ABC Dbayeh",
            "transactionAmount": "100.00",
            "transactionCurrency": "USD",
            "responseCodeDescription": "Approved",
            "referenceNumber": "TXN002"
        },
        {
            "date": "20251026",
            "time": "19:45:00",
            "terminalLocation": "Online - Amazon",
            "transactionAmount": "15.99",
            "transactionCurrency": "USD",
            "responseCodeDescription": "Approved",
            "referenceNumber": "TXN003"
        },
    ]
}

cards.insert_one(mock_user)

print("\n=== Running Tests ===\n")

# 1. Test View Card Details
print("▶ TEST 1: View Card Details")
output = view_card_details("9999")
print(output)
print("-" * 80)

# 2. Test Change PIN
print("▶ TEST 2: Change PIN (correct old pin)")
output = change_pin("9999", "1234", "5678")
print(output)
print("-" * 80)

print("▶ TEST 3: Change PIN (wrong old pin)")
output = change_pin("9999", "9999", "5678")
print(output)
print("-" * 80)

print("▶ TEST 4: List Recent Transactions (3)")
output = list_recent_transactions("9999", count=3)
print(output)
print("-" * 80)

# 4. Test List Transactions by Date Range
print("▶ TEST 5: Transactions from 20251026 to 20251028")
output = list_transactions_date_range("9999", "20251026", "20251028")
print(output)
print("-" * 80)

print("\n✅ All tests completed.\n")

# Optional Cleanup
cards.delete_many({"clientId": "9999"})
client.close()

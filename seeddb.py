#!/usr/bin/env python3
import os
import random
import calendar
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from pymongo import MongoClient
import bcrypt

load_dotenv()
MONGODB_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB", "fransa_demo")

mongo = MongoClient(MONGODB_URI)[DB_NAME]
users = mongo["users"]
cards = mongo["cards"]

def _stan() -> str:
    return datetime.utcnow().strftime("%H%M%S%f")[-12:]

def _fmt(amount: float) -> str:
    return f"{float(amount):.2f}"

def _month_end_expiry(year: int, month: int) -> str:
    last_day = calendar.monthrange(year, month)[1]
    return f"{last_day:02d}{month:02d}{year}"

def _new_card_number() -> str:
    base = 5_000_000_000_000_000
    n = base + random.randint(0, 9_999_999_999_999)
    return str(n).zfill(16)

def _new_token() -> str:
    return "?A" + "".join(random.choice("0123456789ABCDEF") for _ in range(14))

def _ddmmyyyy(dt: datetime) -> str:
    return dt.strftime("%d%m%Y")

def _hhmmss(dt: datetime) -> str:
    return dt.strftime("%H%M%S")

def _txn_template(amount: float, currency: str, ttype: str, descr: str, loc: str = "FSB CORE") -> dict:
    now = datetime.now(timezone.utc)
    stan = _stan()
    return {
        "date": _ddmmyyyy(now - timedelta(days=random.randint(0, 10))),
        "terminalLocation": loc,
        "transactionStatus": "Posted",
        "stanNumber": stan,
        "terminalId": "FSB",
        "responseCodeDescription": "APPROVED TRANSACTION",
        "responseCode": "00",
        "transactionType": ttype,
        "referenceNumber": stan,
        "transactionAmount": _fmt(amount),
        "currency": currency,
        "time": _hhmmss(now),
        "transactionTypeDescription": descr,
    }

def _card_doc(
    *,
    clientId: str,
    firstName: str,
    lastName: str,
    currency: str,
    productType: str,
    city: str,
    email: str,
    channelId: str,
    add_seed_txns: bool = True,
) -> dict:
    now = datetime.utcnow()
    token = _new_token()
    expiry = _month_end_expiry(now.year, now.month)
    doc = {
        "clientId": clientId,
        "cardToken": token,
        "cardNumber": _new_card_number(),
        "type": random.choice(["DEBIT", "CREDIT"]),
        "productType": productType,
        "currency": currency,
        "status": random.choice(["A", "B"]),
        "expiryDate": expiry,
        "cvv2": f"{random.randint(0, 999):03d}",
        "pinHash": bcrypt.hashpw(b"1234", bcrypt.gensalt()).decode(),
        "availableBalance": round(random.uniform(10, 1000), 2),
        "currentBalance": round(random.uniform(10, 1000), 2),
        "cashback": round(random.uniform(0, 50), 2),
        "minimumPayment": 10.0,
        "pendingAuthorization": 0.0,
        "reissue": "N",
        "statusReason": "",
        "transactions": [],
        "embossingName1": f"{firstName[:4].upper()} {lastName[:1].upper()}",
        "embossingName2": "",
        "firstName": firstName,
        "lastName": lastName,
        "address1": f"{city} Main Street {random.randint(1, 50)}",
        "city": city,
        "mobile": f"+96170{random.randint(100000, 999999)}",
        "dob": f"19{random.randint(80, 99)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
        "marital": random.choice(["S", "M"]),
        "gender": random.choice(["M", "F"]),
        "email": email,
        "channelId": channelId,
        "cardLimit": str(random.randint(1000, 5000)),
        "design": random.choice(["CLASSIC", "GOLD", "PLATINUM"]),
    }
    if add_seed_txns:
        doc["transactions"] = [
            _txn_template(random.uniform(10, 200), currency, "10", "PURCHASE - POS"),
            _txn_template(random.uniform(5, 150), currency, "11", "PURCHASE - ECOM"),
            _txn_template(random.uniform(1, 100), currency, "23", "MEMO-CREDIT ADJUSTMENT"),
        ]
    return doc

def main():
    users.delete_many({})
    cards.delete_many({})

    users_seed = [
        {
            "clientId": "1001",
            "firstName": "Samer",
            "lastName": "Kandalaft",
            "Mobile": "+96170123456",
            "email": "samer.k@example.com",
            "wallets": {"840": 150.00, "422": 2_000_000.00, "978": 0.00},
            "accounts": {"840": 2500.00, "422": 0.00, "978": 0.00},
            "qr_withdrawals": [],
        },
        {
            "clientId": "1002",
            "firstName": "Mohamed",
            "lastName": "Moslemani",
            "Mobile": "+96170111222",
            "email": "mohamed.m@example.com",
            "wallets": {"840": 20.00, "978": 500.00},
            "accounts": {"840": 10.00, "978": 2000.00},
            "qr_withdrawals": [],
        },
    ]
    users.insert_many(users_seed)

    card_docs = []
    for user in users_seed:
        for currency in random.sample(["840", "422", "978"], 3):
            card_docs.append(
                _card_doc(
                    clientId=user["clientId"],
                    firstName=user["firstName"],
                    lastName=user["lastName"],
                    currency=currency,
                    productType=random.choice(["CLASSIC", "GOLD", "PLATINUM"]),
                    city="Beirut",
                    email=user["email"],
                    channelId=random.choice(["WEB", "MOB"]),
                )
            )

    cards.insert_many(card_docs)

    ucount = users.count_documents({})
    ccount = cards.count_documents({})
    print(f"Seed complete. users={ucount}, cards={ccount}")
    print("Sample cards:")
    for c in cards.find({}, {"_id": 0, "clientId": 1, "cardToken": 1, "currency": 1, "status": 1}).limit(6):
        print(c)

if __name__ == "__main__":
    main()

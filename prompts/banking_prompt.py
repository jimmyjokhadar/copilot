
def banking_prompt(user_input: str) -> str:
    USER_DATA = USER_DATA = {
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
    
    return f"""
You are a banking assistant.
You are given this user data: {USER_DATA}
You can retrieve card details, list transactions, or change a user’s PIN.
Always respond concisely and clearly.
If a request doesn’t fit any of these, reply 'Not in scope.'
"""

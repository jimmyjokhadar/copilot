from langchain.tools import StructuredTool
from pydantic import BaseModel, Field
from base64 import b64encode, b64decode


###### Change PIN Tool ######
#___________________________#

class ChangePINInput(BaseModel):
    USER_DATA: dict = Field(..., description="User data containing current PIN information.")
    old_pin: str = Field(..., description="The current PIN code.")
    new_pin: str = Field(..., description="The new PIN code to set.")

# adjust here the encoding
def change_pin(USER_DATA: dict, old_pin: str, new_pin: str) -> str:
    old_pin = b64encode(old_pin.encode()).decode()
    new_pin = b64encode(new_pin.encode()).decode()
    if USER_DATA.get("pinHash") is None:
        return "No existing PIN found. Cannot change PIN."
    if USER_DATA["pinHash"] != old_pin:
        return "The old PIN provided is incorrect."
    USER_DATA["pinHash"] = new_pin
    return "PIN changed successfully."

change_pin_tool = StructuredTool.from_function(
    func=change_pin,
    name="change_pin",
    description="Changes the user's PIN after verifying the old PIN.",
    args_schema=ChangePINInput
)

###### View Card Details Tool ######
#__________________________________#

class ViewCardDetailsInput(BaseModel):
    USER_DATA: dict = Field(..., description="User data containing card information.")

def view_card_details(USER_DATA: dict) -> str:
    card_info = {
        "Card Number": USER_DATA.get("cardNumber", "N/A"),
        "Expiry Date": USER_DATA.get("expiryDate", "N/A"),
        "Status": USER_DATA.get("status", "N/A"),
        "Type": USER_DATA.get("type", "N/A"),
        "Product Type": USER_DATA.get("productType", "N/A"),
        "Currency": USER_DATA.get("currency", "N/A"),
        "Available Balance": USER_DATA.get("availableBalance", "N/A"),
        "Current Balance": USER_DATA.get("currentBalance", "N/A"),
        "Card Limit": USER_DATA.get("cardLimit", "N/A"),
        "Cashback Percentage": USER_DATA.get("cashback", "N/A"),
    }
    details = "\n".join([f"{key}: {value}" for key, value in card_info.items()])
    return details

view_card_details_tool = StructuredTool.from_function(
    func=view_card_details,
    name="view_card_details",
    description="Retrieves and displays the user's card details.",
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
        """
        transaction_details.append(detail)
    return "\n".join(transaction_details)

list_recent_transactions_tool = StructuredTool.from_function(
    func=list_recent_transactions,
    name="list_recent_transactions",
    description="Lists recent transactions made with the user's card.",
    args_schema=ListRecentTransactionsInput
)

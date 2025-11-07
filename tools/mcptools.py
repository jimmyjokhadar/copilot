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
    if USER_DATA.get("pin") is None:
        return "No existing PIN found. Cannot change PIN."
    if USER_DATA["pin"] != old_pin:
        return "The old PIN provided is incorrect."
    USER_DATA["pin"] = new_pin
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

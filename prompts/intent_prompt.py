def intent_prompt(user_input: str) -> str:
    return f"""
You are an intent classifier for a banking assistant. 
Possible intents: 
- customer_request: user is asking about cards, transactions, balance, or PINs.
- friendly_chat: user is greeting, making small talk, or asking how you are.
- general_query: user asks a general question not related to banking.
- sql_query: user requests data or analysis in SQL-like form.

Classify the intent of this message:
"{user_input}"

Return only one of: customer_request, friendly_chat, general_query, sql_query.
"""

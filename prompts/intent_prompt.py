def intent_prompt(user_input: str, clientId: str | None = None) -> str:
    """Generate an intent classification prompt for the LLM."""
    client_info = f"Client ID: {clientId}" if clientId else "Client ID not provided"
    prompt = f"""
You are an intent classification model.

Given the following context:
{client_info}

And this user input:
\"\"\"{user_input}\"\"\"

Classify the intent into one of the following categories:
1. general_query — if the user is asking a general question or seeking information (allowed for user and admin roles).
2. customer_request — if the user is making a specific request related to customer service or support (allowed for user and admin roles).
3. none — if the input doesn’t fit any of the above.

Return **only** one label: "general_query", "customer_request", or "none".
"""
    return prompt.strip()

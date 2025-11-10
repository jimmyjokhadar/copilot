def intent_prompt(clientId):
    prompt = f"""given the following client ID: {clientId}, check the intent of the user input and classify it into one of the following categories:
1. General Query: output "general_query" if the user is asking a general question or seeking information." ( allowed for user and admin roles)
2. customer request: output "customer_request" if the user is making a specific request related to customer service or support. ( allowed for user and admin roles)
3. None: output "None" if the user input does not fit into any of the above categories.
"""
    return prompt


import pymongo 
def intent_prompt(user_input):
    prompt = f"""given the following user input: {user_input}, check the intent of the user input and classify it into one of the following categories:
1. General Query: output "General_Query" if the user is asking a general question or seeking information."
2. Sql Query: output "Sql_query" if the user is asking about a specific query on a structured database.
3. customer request: output "customer_request" if the user is making a specific request related to customer service or support.
4. None: output "None" if the user input does not fit into any of the above categories.
"""
    return prompt


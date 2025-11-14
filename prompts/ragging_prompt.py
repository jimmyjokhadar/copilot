def ragging_prompt(user_input: str, context: str) -> str:
    return f"""
            Use the following context to answer the question.\n\nContext:\n{context}
            \n\nQuestion: {user_input}\n\nAnswer:
            """
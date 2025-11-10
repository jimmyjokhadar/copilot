import gradio as gr
from agents.intentAgent import create_intent_agent

# Initialize once
agent = create_intent_agent()

# Each session has its own message history in memory
def chat_with_agent(message, history):
    # Convert Gradio history into one message string
    user_input = message

    # Keep conversation context if needed
    full_conversation = "\n".join([f"User: {m[0]}\nBot: {m[1]}" for m in history if m[0] and m[1]])
    combined_input = f"{full_conversation}\nUser: {user_input}"

    # Invoke your LangGraph agent
    result = agent.invoke({"user_input": combined_input})
    response = result["result"]["content"]
    return response

chat_ui = gr.ChatInterface(
    fn=chat_with_agent,
    title="Agent test",
    description="testing interface for banking agent",
    theme="soft",
    examples=[
        "Show my last 3 transactions.",
        "List transactions between 01/10/2025 and 05/10/2025.",
        "Change my PIN to 4321 (id=1001).",
    ],
)

if __name__ == "__main__":
    chat_ui.launch(server_name="127.0.0.1", server_port=7860)

from typing import TypedDict, Dict, Any, List
from langgraph.graph import StateGraph, START, END
from langchain_ollama import ChatOllama
from prompts.intent_prompt import intent_prompt
from dotenv import load_dotenv
import os 
load_dotenv()

class IntentState(TypedDict):
    user_input: str
    intent: str | None
    result: Dict[str, Any] | None
    conversation_history: List[Dict[str, str]]  # Store conversation context

# Initialize LLM for intent detection
llm = ChatOllama(model=os.getenv("MODEL_NAME"), temperature=0)

def intent_detector(state: IntentState) -> IntentState:
    user_input = state["user_input"]
    conversation_history = state.get("conversation_history", [])
    
    # If there's conversation history, check if we're in a banking context
    in_banking_context = False
    if conversation_history:
        # Check if the last assistant message was from banking (asking for info, etc.)
        for msg in reversed(conversation_history):
            if msg.get("role") == "assistant":
                # If assistant was asking for card number or other banking info, we're in banking context
                content_lower = msg.get("content", "").lower()
                if any(keyword in content_lower for keyword in ["card", "pin", "transaction", "balance", "which card", "provide"]):
                    in_banking_context = True
                break
    
    # If in banking context and user input looks like a card number or simple response, treat as banking
    if in_banking_context:
        # Check if input is numeric (card number) or a simple continuation
        if user_input.replace(" ", "").isdigit() or len(user_input.split()) <= 3:
            intent = "customer_request"
        else:
            # Still use LLM for complex inputs
            prompt = intent_prompt(user_input)
            response = llm.invoke(prompt)
            intent = response.content.strip().lower()
    else:
        # No banking context, use LLM to detect intent
        prompt = intent_prompt(user_input)
        response = llm.invoke(prompt)
        intent = response.content.strip().lower()
    
    return {
        "user_input": user_input, 
        "intent": intent,
        "conversation_history": conversation_history
    }

def banking_node(state: IntentState) -> IntentState:
    # Lazy import to avoid circular dependency
    from agents.bankingAgent import create_banking_agent

    banking_agent = create_banking_agent()
    
    # Build messages from conversation history
    conversation_history = state.get("conversation_history", [])
    messages = []
    
    # Add previous conversation turns
    for msg in conversation_history:
        messages.append(msg)
    
    # Add current user message
    user_message = {"role": "user", "content": state["user_input"]}
    messages.append(user_message)
    
    # Invoke the banking agent with full conversation history
    result = banking_agent.invoke({"messages": messages})

    final_message = result["messages"][-1]
    content = getattr(final_message, "content", str(final_message))
    
    # Update conversation history with the new exchange
    updated_history = conversation_history + [
        user_message,
        {"role": "assistant", "content": content}
    ]
    
    return {
        "user_input": state["user_input"], 
        "intent": state["intent"], 
        "result": {"type": "banking_response", "content": content},
        "conversation_history": updated_history
    }

def fallback_node(state: IntentState) -> IntentState:
    conversation_history = state.get("conversation_history", [])
    fallback_msg = "I'm sorry, I can only assist with banking-related queries."
    
    # Update conversation history
    updated_history = conversation_history + [
        {"role": "user", "content": state["user_input"]},
        {"role": "assistant", "content": fallback_msg}
    ]
    
    return {
        "user_input": state["user_input"],
        "intent": state["intent"],
        "result": {"type": "fallback_response", "content": fallback_msg},
        "conversation_history": updated_history
    }

def route_by_intent(state: IntentState) -> str:
    intent = state["intent"]
    if intent == "customer_request":
        return "banking_node"
    elif intent in ("general_query", "sql_query"):
        return "fallback_node"
    return "fallback_node"

def create_intent_agent():
    builder = StateGraph(IntentState)

    builder.add_node("intent_detector", intent_detector)
    builder.add_node("banking_node", banking_node)
    builder.add_node("fallback_node", fallback_node)

    builder.add_edge(START, "intent_detector")
    builder.add_conditional_edges("intent_detector", route_by_intent)
    builder.add_edge("banking_node", END)
    builder.add_edge("fallback_node", END)

    return builder.compile()

if __name__ == "__main__":
    # For testing purposes - use main.py for interactive mode
    agent = create_intent_agent()
    user_input = "Show my transactions on 05-11-2025, client id 1003."
    result = agent.invoke({"user_input": user_input})
    print("\n=== Final Output ===")
    print("Detected Intent:", result["intent"])
    print("Response:", result["result"]["content"])

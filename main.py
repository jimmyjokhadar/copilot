"""
Main entry point for the Banking Assistant application.
Runs an interactive loop that continuously waits for user input.
"""

from agents.intentAgent import create_intent_agent
from dotenv import load_dotenv

load_dotenv()

def print_separator():
    print("\n" + "="*60 + "\n")

def main():
    """Run the banking assistant in interactive mode."""
    agent = create_intent_agent()
    
    print("="*60)
    print("  Welcome to the Banking Assistant!")
    print("="*60)
    print("\nI can help you with:")
    print("  • View card details")
    print("  • List transactions")
    print("  • Change your PIN")
    print("\nCommands:")
    print("  • Type 'quit', 'exit', or 'bye' to end the conversation")
    print("  • Type 'clear' or 'reset' to start a fresh conversation")
    print_separator()
    
    # Initialize conversation state
    conversation_history = []
    
    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()
            
            # Check for exit commands
            if user_input.lower() in ['quit', 'exit', 'bye', 'q']:
                print("\nThank you for using the Banking Assistant. Goodbye!")
                break
            
            # Check for clear/reset commands
            if user_input.lower() in ['clear', 'reset']:
                conversation_history = []
                print("\nConversation history cleared. Starting fresh!")
                print_separator()
                continue
            
            # Skip empty input
            if not user_input:
                continue
            
            # Process the input through the agent with conversation history
            print("\nProcessing your request...\n")
            result = agent.invoke({
                "user_input": user_input,
                "conversation_history": conversation_history
            })
            
            # Update conversation history from the result
            conversation_history = result.get("conversation_history", conversation_history)
            
            # Display the response
            print(f"Assistant: {result['result']['content']}")
            print_separator()
            
        except KeyboardInterrupt:
            print("\n\nSession interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\nAn error occurred: {str(e)}")
            print("Please try again.")
            print_separator()

if __name__ == "__main__":
    main()

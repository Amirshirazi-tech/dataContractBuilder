from langchain_core.messages import HumanMessage, AIMessage
from agent import app

def run():
    state = {
        "messages": [],
        "phase": "intake",
        "partner_info": None,
        "models": [],
        "consumers": [],
        "validation_errors": []
    }

    print("Data Contract Agent — type 'exit' to quit\n")

    # Kick off with greeting
    state["messages"] = [HumanMessage(content="Hello, I want to create a data contract.")]

    while True:
        # Run graph
        state = app.invoke(state)

        # Print last AI message
        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage) and msg.content:
                print(f"\nAgent: {msg.content}\n")
                break

        # Check if done
        if state.get("phase") == "done":
            print("Contract generation complete.")
            break

        # Get user input
        user_input = input("You: ").strip()
        if user_input.lower() in ("exit", "quit"):
            break

        # Add to state and loop
        state["messages"] = list(state["messages"]) + [HumanMessage(content=user_input)]
    # After the loop ends, verify state
    print("\n--- State verification ---")
    print("partner_info:", state.get("partner_info"))
    print("models:", [m["key"] for m in state.get("models", [])])
    print("consumers:", [c["name"] for c in state.get("consumers", [])])
    print("phase:", state.get("phase"))
    print("generated_yaml:", "YES" if state.get("generated_yaml") else "None")

if __name__ == "__main__":
    run()
from langchain_core.messages import HumanMessage, AIMessage
from agent import app


def run():
    config = {"configurable": {"thread_id": "session-1"}}

    state = {
        "messages": [HumanMessage(content="Hello, I want to create a data contract.")],
        "phase": "intake",
        "partner_info": None,
        "models": [],
        "consumers": [],
        "validation_errors": []
    }

    print("Data Contract Agent — type 'exit' to quit\n")

    while True:
        # Run graph — may pause at interrupt
        result = app.invoke(state, config)
        state = result

        # Print last AI message
        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage) and msg.content:
                print(f"\nAgent: {msg.content}\n")
                break

        # Check if paused at human_review
        snapshot = app.get_state(config)
        if snapshot.next and "human_review" in snapshot.next:
            print("\n[INTERRUPT] Graph paused for your confirmation.")
            user_input = input("You: ").strip()
            if user_input.lower() in ("exit", "quit"):
                break
            # Resume graph with user's response added to messages
            app.update_state(config, {
                "messages": [HumanMessage(content=user_input)]
            })
            state = app.invoke(None, config)
            continue

        # Check if done
        if state.get("phase") == "generating":
            print("\nContract ready for generation.")
            break

        # Normal turn — get user input
        user_input = input("You: ").strip()
        if user_input.lower() in ("exit", "quit"):
            break

        state["messages"] = list(state["messages"]) + [
            HumanMessage(content=user_input)
        ]

    print("\n--- State verification ---")
    print("models:", [m["key"] for m in state.get("models", [])])
    print("consumers:", [c["name"] for c in state.get("consumers", [])])
    print("phase:", state.get("phase"))
    print("generated_yaml:", "YES" if state.get("generated_yaml") else "None")
if __name__ == "__main__":
    run()
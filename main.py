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
            # Find and print the show_summary ToolMessage
            for msg in reversed(state["messages"]):
                if hasattr(msg, "content") and "Contract ID:" in str(msg.content):
                    print(f"\n{msg.content}\n")
                    break
            print("\n[INTERRUPT] Please review the summary above.")
            user_input = input("You: (yes to confirm / describe corrections): ").strip()
            if user_input.lower() in ("exit", "quit"):
                break
            # Resume graph with user's response added to messages
            app.update_state(config, {
                "messages": [HumanMessage(content=user_input)]
            })
            state = app.invoke(None, config)
            continue

        # Check if done
        if state.get("phase") == "done":
            yaml_str = state.get("generated_yaml", "")
            print("\n--- Generated Contract Preview ---")
            print(yaml_str[:500])

            output_path = f"{state['partner_info']['contract_id']}.yaml"
            with open(output_path, "w") as f:
                f.write(yaml_str)
            print(f"\nContract saved to: {output_path}")
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
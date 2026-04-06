# from typing import Annotated
from generator import generate_contract_yaml
from validator import validate_contract
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from state import ContractState
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from IPython.display import Image, display
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from tools import save_partner_info, add_model, suggest_quality_rules, add_consumer, show_summary, finalize_contract
from prompts import SYSTEM_PROMPT
import os

load_dotenv()

def generate_node(state: ContractState) -> dict:
    """Generate the YAML contract from collected state."""
    yaml_str = generate_contract_yaml(state)
    return {"generated_yaml": yaml_str, "validation_errors": []}
from generator import generate_contract_yaml
from validator import validate_contract
from langchain_core.messages import SystemMessage

def generate_node(state: ContractState) -> dict:
    """Generate the YAML contract from collected state."""
    yaml_str = generate_contract_yaml(state)
    return {"generated_yaml": yaml_str, "validation_errors": []}

def validate_node(state: ContractState) -> dict:
    """Validate the generated YAML."""
    yaml_str = state.get("generated_yaml", "")
    errors = validate_contract(yaml_str)
    if errors:
        error_msg = (
            "Contract validation failed:\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\n\nPlease explain these to the user and ask which to fix."
        )
        return {
            "validation_errors": errors,
            "phase": "modeling",
            "messages": [SystemMessage(content=error_msg)],
        }
    return {"validation_errors": [], "phase": "done"}

def agent_node(state:ContractState):
    backend = os.getenv("MODEL_BACKEND", "ollama")

    if backend == "anthropic":
        from langchain_anthropic import ChatAnthropic
        llm = ChatAnthropic(model="claude-haiku-4-5", temperature=0)
    elif backend == "openrouter":
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model="anthropic/claude-haiku-4.5",
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
            temperature=0,
        )
    else:
        llm = ChatOllama(model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"), base_url="https://ollama.wineme.wiwi.uni-siegen.de", temperature=0)

    llm_with_tools=llm.bind_tools([save_partner_info, add_model, suggest_quality_rules, add_consumer, show_summary, finalize_contract])
    context_parts = []
    if state.get("partner_info"):
        p = state["partner_info"]
        context_parts.append(f"Partner already saved: {p['name']} ({p['code']})")
    if state.get("models"):
        keys = [m["key"] for m in state["models"]]
        context_parts.append(f"Models already added: {', '.join(keys)}")
    if state.get("consumers"):
        names = [c["name"] for c in state["consumers"]]
        context_parts.append(f"Consumers already added: {', '.join(names)}")

    context = "\n".join(context_parts)
    system_content = SYSTEM_PROMPT
    if context:
        system_content += f"\n\n## Current state\n{context}"

    phase = state.get("phase", "intake")
    extra = ""
    if phase == "reviewing":
        extra = "\nThe summary has been shown. Ask the user to confirm or correct it. If confirmed, call finalize_contract immediately."

    system = SystemMessage(content=system_content + extra)
    messages = [system] + state.get("messages", [])
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

def route_from_agent(state:ContractState):
    messages = state.get("messages", [])
    if not messages:
        return END
    last = messages[-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END

# Add a human_review node
def human_review_node(state: ContractState) -> dict:
    # This node does nothing — it is just the pause point
    return {}

graph = StateGraph(ContractState)
graph.add_node("agent", agent_node)
graph.add_node("tools", ToolNode([save_partner_info, add_model,
                                  suggest_quality_rules, add_consumer,
                                  show_summary, finalize_contract]))
graph.add_node("human_review", human_review_node)
graph.add_node("generate", generate_node)      # ← new
graph.add_node("validate", validate_node)
graph.set_entry_point("agent")
graph.add_conditional_edges("agent",
                            route_from_agent,
                            {"tools" : "tools", END:END})

# After tools — check if we need human review
def route_from_tools(state: ContractState) -> str:
    if state.get("phase") == "reviewing":
        return "human_review"
    if state.get("phase") == "generating":
        return "generate"        # ← now this works
    return "agent"

graph.add_conditional_edges("tools", route_from_tools, {
    "human_review": "human_review",
    "generate": "generate",
    "agent": "agent"
})
graph.add_edge("human_review", "agent")
graph.add_edge("generate", "validate")         # ← new

def route_from_validate(state: ContractState) -> str:
    if state.get("validation_errors"):
        return "agent"
    return END

graph.add_conditional_edges("validate", route_from_validate, {
    "agent": "agent",
    END: END
})


app = graph.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["human_review"]
)


if __name__ == "__main__":
    try:
        display(Image(app.get_graph().draw_mermaid_png()))
    except Exception:
        # This might fail if certain dependencies aren't installed
        print("Could not display graph directly.")

    # Option B: Save the graph to a PNG file
    with open("graph_visualization.png", "wb") as f:
        f.write(app.get_graph().draw_mermaid_png())

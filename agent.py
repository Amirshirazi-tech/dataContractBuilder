from typing import Annotated
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from state import ContractState
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from IPython.display import Image, display
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from tools import save_partner_info, add_model, suggest_quality_rules, add_consumer
from prompts import SYSTEM_PROMPT
import os

load_dotenv()


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

    llm_with_tools=llm.bind_tools([save_partner_info, add_model, suggest_quality_rules, add_consumer])
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
    system = SystemMessage(content=SYSTEM_PROMPT)
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

graph = StateGraph(ContractState)
graph.add_node("agent", agent_node)
graph.add_node("tools", ToolNode([save_partner_info, add_model, suggest_quality_rules, add_consumer]))
graph.set_entry_point("agent")
graph.add_conditional_edges("agent", route_from_agent, {"tools" : "tools", END:END})
graph.add_edge("tools", "agent")
app = graph.compile()
try:
    display(Image(app.get_graph().draw_mermaid_png()))
except Exception:
    # This might fail if certain dependencies aren't installed
    print("Could not display graph directly.")

# Option B: Save the graph to a PNG file
with open("graph_visualization.png", "wb") as f:
    f.write(app.get_graph().draw_mermaid_png())

# if __name__ == "__main__":
#     graph = StateGraph(ContractState)
#     graph.add_node("agent", agent_node)
#     graph.add_node("tools", ToolNode([save_partner_info, add_model, suggest_quality_rules, add_consumer]))
#     graph.set_entry_point("agent")
#     graph.add_conditional_edges("agent", route_from_agent, {"tools" : "tools", END:END})
#     graph.add_edge("tools", "agent")
#     app = graph.compile()
#     try:
#         display(Image(app.get_graph().draw_mermaid_png()))
#     except Exception:
#         # This might fail if certain dependencies aren't installed
#         print("Could not display graph directly.")
#
#     # Option B: Save the graph to a PNG file
#     with open("graph_visualization.png", "wb") as f:
#         f.write(app.get_graph().draw_mermaid_png())


    # result = app.invoke({
    #     "messages": [HumanMessage(content="Hello, I want to create a contract for SpaceX.")],
    #     "phase": "intake",
    #     "partner_info": None,
    #     "models": [],
    #     "consumers": [],
    #     "validation_errors": []
    # })
    #
    # # Print the last message
    # print(result["messages"][-1].content)
    # print(result["partner_info"])
    # print(result["phase"])
    #---------------------------
    # result = app.invoke({
    #     "messages": [HumanMessage(content="I want to share product and material data.")],
    #     "phase": "modeling",
    #     "partner_info": {"name": "SpaceX", "code": "spacex"},
    #     "models": [],
    #     "consumers": [],
    #     "validation_errors": []
    # })
    # print(result["models"])
    # for msg in result["messages"]:
    #     print(type(msg).__name__, ":", msg.content)
    #     if hasattr(msg, "tool_calls") and msg.tool_calls:
    #         print("  TOOL CALLS:", msg.tool_calls)
    #     print("---")

    # print(result["models"])
    #---------------------------
    # result = app.invoke({
    #     "messages": [HumanMessage(content="Suggest quality rules for the material model.")],
    #     "phase": "modeling",
    #     "partner_info": {"name": "SpaceX", "code": "spacex"},
    #     "models": [
    #         {'key': 'material', 'name': 'Materials', 'description': 'Material data',
    #          'fields': {'material_no': {'type': 'string', 'description': 'Internal material number'},
    #                     'material_name': {'type': 'string', 'description': 'Human-readable name', 'nullable': True},
    #                     'category': {'type': 'string', 'description': 'Material category', 'nullable': True},
    #                     'density_g_per_cm3': {'type': 'number', 'format': 'float', 'description': 'Density in g/cm3',
    #                                           'nullable': True}},
    #          'required': ['material_no'], 'kg_node': 'Material', 'source': 'template'}
    #     ],
    #     "consumers": [],
    #     "validation_errors": []
    # })
    #
    # print(result["messages"][-1].content)
    # # Print all messages to see what actually happened
    # for msg in result["messages"]:
    #     print(type(msg).__name__, ":", msg.content)
    #     print("---")
    #------------------------
    # result = app.invoke({
    #     "messages": [HumanMessage(
    #         content="Add University of Siegen as a consumer for research purposes only. They cannot share externally. Retention 365 days. Completeness 80, accuracy 85.")],
    #     "phase": "modeling",
    #     "partner_info": {"name": "SpaceX", "code": "spacex"},
    #     "models": [],
    #     "consumers": [],
    #     "validation_errors": []
    # })
    #
    # print(result["consumers"])
    # for msg in result["messages"]:
    #     print(type(msg).__name__, ":", msg.content)
    #     if hasattr(msg, "tool_calls") and msg.tool_calls:
    #         print("  TOOL CALLS:", msg.tool_calls)
    #     print("---")
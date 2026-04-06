from typing import TypedDict
from langgraph.graph import StateGraph, END
from IPython.display import Image, display


class ToyState(TypedDict):
    value: int
    log: list[str]

def node_a(state):
    return {"value": state["value"]+1, "log": state["log"]+ ["a ran"]}

def node_b(state):
    return {"value": state["value"]*2, "log": state["log"]+ ["b ran"]}

def node_c(state):
    return {"log": state["log"]+ ["c done"]}

def node_d(state):
    return {"log": state["log"]+ ["d alternative"]}

def route(state):
    return "c" if state["value"] > 10 else "d"

graph = StateGraph(ToyState)
graph.add_node("a", node_a)
graph.add_node("b", node_b)
graph.add_node("c", node_c)
graph.add_node("d", node_d)

graph.set_entry_point("a")
graph.add_edge("a", "b")
graph.add_conditional_edges("b", route, {"c": "c", "d": "d"})
graph.add_edge("c", END)
graph.add_edge("d", END)

app = graph.compile()

try:
    display(Image(app.get_graph().draw_mermaid_png()))
except Exception:
    # This might fail if certain dependencies aren't installed
    print("Could not display graph directly.")

# Option B: Save the graph to a PNG file
with open("graph_visualization.png", "wb") as f:
    f.write(app.get_graph().draw_mermaid_png())

print(app.invoke({"value": 5, "log": []}))
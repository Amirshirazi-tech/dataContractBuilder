from __future__ import annotations
from typing import Annotated, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

# Reducer that always takes the newest value
def replace(old, new):
    return new

class ContractState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    phase: str
    partner_info: Optional[dict]
    models: Annotated[list, replace]
    consumers: Annotated[list, replace]
    kafka_broker: str
    kafka_security: str
    license: str
    compliance: list
    unknown_fields: list
    extension_proposals: list
    confirmed_extensions: list
    generated_yaml: Optional[str]
    validation_errors: list
    output_file: Optional[str]



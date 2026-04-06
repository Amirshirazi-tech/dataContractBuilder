from langgraph.types import Command
from typing import Annotated, Optional
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import ToolMessage
import yaml
from pathlib import Path

def save_partner_info(
        name: str,
        code: str,
        email: str,
        description: str,
        status: str,
        retention_days: int,
        quality_level: str,
        tool_call_id: Annotated[str, InjectedToolCallId],
)-> Command:
    """Save partner and company information. Call once after collecting all partner details
    Args:
        name: Company display name e.g. Acme GmbH
        code: Short slug for contract ID, lowercase and underscores only e.g. acme_gmbh
        email: Data steward contact email
        description: One sentence description of what data they share
        status: draft or active
        retention_days: How long to retain data in days, suggest 365
        quality_level: flexible, standard, or strict
    """
    partner = {
        "name": name,
        "code": code.lower().replace(" ", "_").replace("-", "_"),
        "email": email,
        "description": description,
        "status": status,
        "retention_days": retention_days,
        "quality_level": quality_level,
    }

    return Command(update={"partner_info": partner,
        "phase": "modeling",
        "messages": [ToolMessage(
            content=f"Partner info saved: {name} ({code})",
            tool_call_id=tool_call_id,
        )],
        })

def load_template_model(model_key: str)-> dict | None:
    """Load a predefine model from data_contact_template.yaml"""
    template_path = Path(__file__).parent/"contract/data_contract_template.yaml"
    with open(template_path) as f:
        template = yaml.safe_load(f)
    return template.get("models", {}).get(model_key)


from langgraph.prebuilt import InjectedState


def add_model(
        key: str,
        name: str,
        description: str,
        kg_node: Optional[str],  # ← None means lakehouse only
        tool_call_id: Annotated[str, InjectedToolCallId],
        state: Annotated[dict, InjectedState],
) -> Command:
    """Add a data model to the contract.

    Args:
        key: snake_case model identifier e.g. product, material, custom_sensor
        name: Human readable model name e.g. Products
        description: What this model represents
        kg_node: Neo4j node label e.g. Product. Pass null if data goes to lakehouse only.
    """
    template_model = load_template_model(key)

    if template_model:
        fields = template_model.get("fields", {})
        required = template_model.get("required", [])
        kg_node = kg_node if kg_node is not None else template_model.get("kg_node")  # respect explicit null
        source = "template"
    else:
        fields = {}
        required = []
        source = "custom"

    model = {
        "key": key,
        "name": name,
        "description": description,
        "fields": fields,
        "required": required,
        "kg_node": kg_node,  # None = lakehouse only
        "source": source,
    }

    # Append to existing models list without replacing it
    existing = list(state.get("models", []))
    existing = [m for m in existing if m["key"] != key]  # replace if already exists
    existing.append(model)

    return Command(update={
        "models": existing,
        "messages": [ToolMessage(
            content=f"Model '{name}' added with {len(fields)} fields from {source}.",
            tool_call_id=tool_call_id,
        )],
    })


def suggest_quality_rules(
        model_key: str,
        tool_call_id: Annotated[str, InjectedToolCallId],
        state: Annotated[dict, InjectedState],
) -> Command:
    """Auto-generate quality rule suggestions for a model based on its field types.
    Call after add_model. The agent should present suggestions to user for confirmation.

    Args:
        model_key: The key of the model already saved in state e.g. product
    """
    # Find the model in state
    models = state.get("models", [])
    model = next((m for m in models if m["key"] == model_key), None)

    if not model:
        return Command(update={
            "messages": [ToolMessage(
                content=f"Model '{model_key}' not found in state. Call add_model first.",
                tool_call_id=tool_call_id,
            )]
        })

    fields = model.get("fields", {})
    required = model.get("required", [])
    rules = []

    for field_key, field_def in fields.items():
        ftype = field_def.get("type", "string")
        fmt = field_def.get("format", "")
        is_required = field_key in required

        # not_null for all required fields
        if is_required:
            rules.append({
                "field": field_key,
                "rule": "not_null",
                "severity": "error",
                "description": f"{field_key} is required",
            })

        # datetime checks
        if fmt == "date-time":
            rules.append({
                "field": field_key,
                "rule": "valid_datetime",
                "severity": "error",
                "description": f"{field_key} must be valid ISO 8601",
            })
            if "timestamp" in field_key or "date" in field_key:
                rules.append({
                    "field": field_key,
                    "rule": "not_future",
                    "severity": "warning",
                    "description": f"{field_key} should not be in the future",
                })

        # numeric checks
        if ftype == "number":
            fmin = field_def.get("min")
            fmax = field_def.get("max")
            if fmin is not None and fmax is not None:
                rules.append({
                    "field": field_key,
                    "rule": "between",
                    "severity": "warning",
                    "min": fmin,
                    "max": fmax,
                    "description": f"{field_key} must be between {fmin} and {fmax}",
                })
            elif fmin is not None and fmin >= 0:
                rules.append({
                    "field": field_key,
                    "rule": "greater_than_zero",
                    "severity": "error",
                    "description": f"{field_key} must be positive",
                })

    import json
    return Command(update={
        "messages": [ToolMessage(
            content=f"Suggested {len(rules)} quality rules for '{model_key}':\n"
                    f"{json.dumps(rules, indent=2)}\n\n"
                    f"Please review these with the user before confirming.",
            tool_call_id=tool_call_id,
        )]
    })


def add_consumer(
        name: str,
        description: str,
        allowed_purposes: str,
        retention_days: int,
        can_share_externally: bool,
        min_completeness: int,
        min_accuracy: int,
        export_profile: str,
        tool_call_id: Annotated[str, InjectedToolCallId],
        state: Annotated[dict, InjectedState],
) -> Command:
    """Add a data consumer to the contract.

    Args:
        name: Consumer identifier e.g. Research_University, Consulting_Partner
        description: Who this consumer is
        allowed_purposes: Comma separated list of purposes e.g. research,reporting
        retention_days: How long consumer may retain data in days
        can_share_externally: Whether consumer can share data outside their org
        min_completeness: Minimum data completeness percent required 0 to 100
        min_accuracy: Minimum data accuracy percent required 0 to 100
        export_profile: Which export profile to use. Options: full_internal,
                        customer_exchange_minimum, supplier_exchange_minimum,
                        public_dpp_view
    """
    consumer = {
        "name": name,
        "description": description,
        "allowed_purposes": [p.strip() for p in allowed_purposes.split(",")],
        "retention_days": retention_days,
        "can_share_externally": can_share_externally,
        "requires_audit": True,
        "min_completeness": min_completeness,
        "min_accuracy": min_accuracy,
        "export_profile": export_profile,
    }

    existing = list(state.get("consumers", []))
    existing = [c for c in existing if c["name"] != name]
    existing.append(consumer)

    return Command(update={
        "consumers": existing,
        "messages": [ToolMessage(
            content=f"Consumer '{name}' added with export profile '{export_profile}'.",
            tool_call_id=tool_call_id,
        )],
    })
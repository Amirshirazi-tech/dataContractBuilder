from __future__ import annotations
from datetime import date
from pathlib import Path
import yaml
from state import ContractState

# Platform constants — fixed for platform
KAFKA_HOST = "kafka.example.com:9092"
KAFKA_SECURITY = "SASL_SSL"
KAFKA_FORMAT = "json"
LICENSE = "CC-BY-NC-4.0"
COMPLIANCE = ["GDPR", "IDS_Usage_Control"]

QUALITY_PRESETS = {
    "flexible": {"completeness": 80, "accuracy": 85},
    "standard": {"completeness": 90, "accuracy": 95},
    "strict":   {"completeness": 95, "accuracy": 98},
}

def generate_contract_yaml(state: ContractState) -> str:
    p = state["partner_info"]
    code = p["code"]
    project = p["project"]
    qual = QUALITY_PRESETS.get(p.get("quality_level", "standard"), QUALITY_PRESETS["standard"])
    today = str(date.today())

    doc = {
        "dataContractSpecification": "1.1.0",
        "id": p["contract_id"],
        "info": _build_info(p, today),
        "consumers": _build_consumers(state, qual, project, code),
        "servers": _build_servers(state, project, code),
        "models": _build_models(state),
        "quality": _build_quality(qual),
        "terms": _build_terms(p),
    }

    return yaml.dump(doc, default_flow_style=False,
                     allow_unicode=True, sort_keys=False, width=100)


def _build_info(p: dict, today: str) -> dict:
    return {
        "title": f"{p['name']} – Data Contract",
        "version": "1.0.0",
        "owner": p["name"],
        "description": p.get("description", f"Data contract for {p['name']}"),
        "status": p.get("status", "draft"),
        "contact": {"email": p.get("email", "")},
        "created": today,
        "modified": today,
        "project": p.get("project", ""),
        "project_prefix": p.get("project", ""),
    }


def _build_consumers(state: ContractState, qual: dict, project: str, code: str) -> dict:
    consumers = {}

    # Platform consumer — always present
    consumers["Platform"] = {
        "description": "platform — main consumer",
        "allowed_purposes": [
            "circular_economy_analysis",
            "product_lifecycle_tracking",
            "sustainability_reporting",
        ],
        "allowed_topics": [f"{project}.{code}.*"],
        "data_retention_days": 730,
        "can_share_externally": False,
        "requires_audit": True,
        "max_data_size_mb": 500,
        "data_quality_requirements": {
            "min_completeness": qual["completeness"],
            "min_accuracy": qual["accuracy"],
            "validation_required": True,
            "reject_invalid": True,
        },
        "constraints": [
            {"type": "rate_limit", "value": 1000, "unit": "messages/minute"},
            {"type": "no_raw_export", "description": "No bulk export of raw data"},
        ],
    }

    # User-defined consumers
    for c in state.get("consumers", []):
        allowed_topics = [
            f"{project}.{code}.{m}"
            for m in c.get("allowed_models", [])
        ]
        consumers[c["name"]] = {
            "description": c.get("description", ""),
            "allowed_purposes": c.get("allowed_purposes", []),
            "allowed_topics": allowed_topics,
            "requires_audit": True,
            "export_profile": c.get("export_profile", "full_internal"),
        }

    # Default policy — always present
    consumers["default_consumer_policy"] = {
        "allowed_purposes": ["research_demonstration"],
        "data_retention_days": 90,
        "can_share_externally": False,
        "requires_audit": True,
        "max_data_size_mb": 10,
        "data_quality_requirements": {
            "min_completeness": 80,
            "min_accuracy": 85,
            "validation_required": True,
        },
        "constraints": [
            {
                "type": "manual_approval",
                "approval_contact": state["partner_info"].get("email", ""),
                "approval_sla_days": 5,
            }
        ],
    }

    return consumers


def _build_servers(state: ContractState, project: str, code: str) -> dict:
    topics = [m.get("topic", f"{project}.{code}.{m['key']}")
              for m in state.get("models", [])]
    return {
        "production": {
            "type": "kafka",
            "host": KAFKA_HOST,
            "topics": topics,
            "format": KAFKA_FORMAT,
            "security": KAFKA_SECURITY,
        }
    }


def _build_models(state: ContractState) -> dict:
    models_out = {}
    for m in state.get("models", []):
        fields = m.get("fields", {})
        required = m.get("required", [])

        fields_dict = {}
        for fk, fdef in fields.items():
            entry = {
                "type": fdef.get("type", "string"),
                "description": fdef.get("description", fk),
            }
            if fdef.get("format"):
                entry["format"] = fdef["format"]
            if fdef.get("nullable"):
                entry["nullable"] = True
            if fdef.get("unit"):
                entry["unit"] = fdef["unit"]
            fields_dict[fk] = entry

        model_entry = {
            "topic": m.get("topic", ""),
            "description": m.get("description", ""),
            "type": "object",
            "kg_node": m.get("kg_node"),
            "required": required,
            "fields": fields_dict,
        }

        if m.get("quality_rules"):
            model_entry["quality_rules"] = m["quality_rules"]

        models_out[m["key"]] = model_entry

    return models_out


def _build_quality(qual: dict) -> dict:
    return {
        "schema_validation": {
            "enabled": True,
            "strict_mode": True,
            "reject_invalid": True,
            "log_violations": True,
        },
        "metrics": {
            "completeness_target": qual["completeness"],
            "accuracy_target": qual["accuracy"],
        },
    }


def _build_terms(p: dict) -> dict:
    return {
        "license": LICENSE,
        "confidentiality": "internal_partners",
        "usage": f"Data shared by {p['name']} under agreed terms.",
        "compliance": COMPLIANCE,
        "privacy": {
            "gdpr_compliant": True,
            "contains_personal_data": False,
            "data_classification": "internal",
        },
    }
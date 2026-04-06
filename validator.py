import yaml

REQUIRED_TOP_LEVEL = {
    "dataContractSpecification", "id", "info",
    "consumers", "servers", "models", "quality", "terms"
}

def validate_contract(yaml_str: str) -> list[str]:
    errors = []
    try:
        doc = yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        return [f"YAML parse error: {e}"]

    if not isinstance(doc, dict):
        return ["Contract must be a YAML mapping"]

    missing = REQUIRED_TOP_LEVEL - set(doc.keys())
    for key in sorted(missing):
        errors.append(f"Missing required key: '{key}'")

    if not errors:
        models = doc.get("models", {})
        if not models:
            errors.append("'models' must define at least one model")
        for mk, mdef in models.items():
            if "fields" not in mdef:
                errors.append(f"models.{mk} is missing 'fields'")
            if "required" not in mdef:
                errors.append(f"models.{mk} is missing 'required'")

    return errors
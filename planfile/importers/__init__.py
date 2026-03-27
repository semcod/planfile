"""Import tickets from various tool outputs."""


_IMPORTERS = {}


def register_importer(name: str, importer_cls):
    _IMPORTERS[name] = importer_cls


def import_from_source(path: str, source: str, **kwargs) -> list[dict]:
    """Auto-detect format and import tickets."""
    if path.endswith(".toon") or path.endswith(".toon.yaml"):
        if source == "vallm":
            from planfile.importers.vallm_importer import import_vallm
            return import_vallm(path, **kwargs)
        else:
            from planfile.importers.code2llm_importer import import_code2llm
            return import_code2llm(path, **kwargs)
    elif path.endswith(".json"):
        from planfile.importers.json_importer import import_json
        return import_json(path, **kwargs)
    elif path.endswith(".yaml") or path.endswith(".yml"):
        from planfile.importers.yaml_importer import import_yaml
        return import_yaml(path, **kwargs)
    raise ValueError(f"Unknown format: {path}")

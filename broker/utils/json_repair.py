"""
JSON extraction and repair helpers.
"""
import json


def json_extract_preprocessor(text: str) -> str:
    """
    Preprocessor for models that may return JSON.
    Extracts text content from JSON if present.
    """
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            for key in ["response", "output", "text", "content"]:
                if key in data:
                    return str(data[key])
        return text
    except json.JSONDecodeError:
        return text

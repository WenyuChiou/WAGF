"""
DeepSeek-specific preprocessing.
"""
import re


def deepseek_preprocessor(text: str) -> str:
    """
    Preprocessor for DeepSeek models.
    Removes <think>...</think> reasoning tags, but preserves content
    if the model put the entire decision inside the think tag.
    """
    if not text:
        return ""

    text = text.replace("<thinking>", "<think>").replace("</thinking>", "</think>")

    after_think_match = re.search(r"</think>\s*(.+)", text, flags=re.DOTALL)
    if after_think_match:
        after_content = after_think_match.group(1).strip()
        if len(after_content) > 30:
            return after_content

    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    if not cleaned or len(cleaned) < 20 or re.match(r"^\[?N/A\]?$", cleaned, re.I):
        think_match = re.search(r"<think>(.*?)(?:</think>|$)", text, flags=re.DOTALL)
        if think_match:
            inner = think_match.group(1).strip()
            decision_patterns = [
                r"(final decision:?\s*\d+.*)",
                r"(final decision:?\s*\w+.*)",
                r"(selected action:?\s*.+)",
                r"(decision)[:\s]*(.+)",
            ]
            for pattern in decision_patterns:
                match = re.search(pattern, inner, re.IGNORECASE | re.DOTALL)
                if match:
                    return match.group(0).strip()

            decision_kws = ["decide", "decision", "action", "choice", "id"]
            if any(kw in inner.lower() for kw in decision_kws):
                return inner[-500:] if len(inner) > 500 else inner

            if not cleaned and inner:
                return inner

    return cleaned if cleaned else text

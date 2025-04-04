import re
import json

def extract_json_block(text: str) -> str:
    """
    Extract the first JSON object or array from a string.
    Handles markdown-style code blocks and plain JSON.
    """
    # First: Try to extract from ```json ... ```
    fenced = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text, re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()

    # Then: Look for the first {...} or [...] block
    unfenced = re.search(r"(\{[\s\S]+?\}|\[[\s\S]+?\])", text)
    if unfenced:
        return unfenced.group(1).strip()

    raise ValueError("No JSON block found in LLM response.")

def robust_json_load(s: str):
    import re

    s = s.strip()
    if s.startswith("```json"):
        s = s[7:]
    if s.endswith("```"):
        s = s[:-3]
    s = s.strip()

    # Attempt to extract the most JSON-like substring
    match = re.search(r"(\[.*\]|\{.*\})", s, re.DOTALL)
    if match:
        s = match.group(0)

    try:
        return json.loads(s)
    except Exception as e:
        raise ValueError(f"robust_json_load failed: {e}")

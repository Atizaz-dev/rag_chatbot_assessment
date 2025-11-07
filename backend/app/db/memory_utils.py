# db/memory_utils.py
import re

# very small, conservative heuristics
GENERIC_FACT_RE = re.compile(
    r"(?:(?:^|\n|\.)\s*[-*•]?\s*)([A-Z][^.!?]{3,140})",
    re.I
)
NAME_RE = re.compile(r"\bmy name is ([A-Za-z][A-Za-z\s'-]{0,40})\b", re.I)
LIVE_RE = re.compile(r"\bi (live|reside) in ([A-Za-z][A-Za-z\s,.-]{0,80})\b", re.I)

def extract_memories_from_text(text: str) -> list[str]:
    """Extract small, likely-useful memories from a text blob.

    Very conservative: avoids saving whole transcripts or "I cannot find" messages.
    Returns up to 5 short snippets (max ~140 chars) that look like factual statements.
    """
    if not text:
        return []

    # Drop common negative responses to avoid polluting memory store
    if re.search(r"cannot find the answer|can't find the answer|not found in the provided document",
                 text, re.I):
        return []

    memories: list[str] = []

    # Name and location heuristics (simple, safe)
    m = NAME_RE.search(text)
    if m:
        name = m.group(1).strip()
        if 2 <= len(name) <= 50:
            memories.append(f"name: {name}")

    m2 = LIVE_RE.search(text)
    if m2:
        place = m2.group(2).strip()
        if 2 <= len(place) <= 80:
            memories.append(f"location: {place}")

    # Extract a few generic facts/bullets/sentences
    for match in GENERIC_FACT_RE.findall(text):
        fact = match.strip()
        if 12 <= len(fact) <= 140 and len(fact.split()) >= 3:
            memories.append(f"fact: {fact}")
        if len(memories) >= 5:
            break

    # Deduplicate and clamp lengths
    seen = set()
    out: list[str] = []
    for mem in memories:
        mem = mem.strip()
        if not mem or mem in seen:
            continue
        out.append(mem[:200])
        seen.add(mem)

    return out

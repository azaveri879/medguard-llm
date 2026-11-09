"""
Exact-match redaction of names the hospital already knows.

Names from the EHR catch cases statistical detection misses, such as a bare
surname. Names that are also ordinary words are matched only in their original
or all-caps form, so a patient named White doesn't erase "white count".
"""

import re
from typing import Callable, Dict, Iterable, List, Tuple

COMMON_WORD_NAMES = {
    "art", "baker", "bank", "banks", "bell", "berry", "best", "bill", "bird", "bishop",
    "black", "brown", "bush", "carpenter", "case", "chase", "cook", "cross", "day", "dean",
    "faith", "field", "fields", "fisher", "ford", "foster", "fox", "frost", "golden", "good",
    "grace", "grant", "gray", "green", "grey", "hall", "hill", "hope", "hunter", "joy",
    "king", "lake", "lamb", "land", "lane", "little", "long", "love", "major", "mark",
    "marsh", "mason", "may", "moon", "page", "parks", "pope", "price", "reed", "rice",
    "rich", "river", "rivers", "rose", "sharp", "short", "small", "snow", "stone", "strong",
    "summer", "white", "will", "winter", "wolf", "wood", "woods", "young",
}
NON_NAME_TOKENS = {"dr", "mr", "mrs", "ms", "prof", "md", "do", "rn", "np", "pa", "phd", "jr", "sr", "ii", "iii"}
NAME_PART = re.compile(r"[^\W\d_][\w'’-]*")


def _bounded(pattern: str) -> str:
    return rf"(?<![\w'’-]){pattern}(?![\w'’-])"


def _patterns(names: Iterable[str]) -> List[re.Pattern]:
    """Compile full names first, then individual name parts, longest first."""
    full_names, tokens = set(), set()
    for name in names:
        if not isinstance(name, str):
            continue
        parts = [p for p in NAME_PART.findall(name) if p.lower() not in NON_NAME_TOKENS]
        tokens.update(parts)
        if len(parts) >= 2:
            full_names.add(tuple(parts))
            full_names.add((parts[-1], parts[0]))

    compiled = []
    for parts in sorted(full_names, key=lambda p: -sum(map(len, p))):
        joined = r",?\s+".join(map(re.escape, parts))
        compiled.append(re.compile(_bounded(joined), re.IGNORECASE))
    for token in sorted(tokens, key=len, reverse=True):
        if token.lower() in COMMON_WORD_NAMES or len(token) <= 2:
            forms = sorted({token, token.upper()})
            compiled.append(re.compile(_bounded("(?:" + "|".join(map(re.escape, forms)) + ")")))
        else:
            compiled.append(re.compile(_bounded(re.escape(token)), re.IGNORECASE))
    return compiled


def redact_known_names(text: str, names: Iterable[str]) -> Tuple[str, Dict[str, int]]:
    """Replace known names. Returns (text, count of redactions by PHI type)."""
    out = text or ""
    total = 0
    for pattern in _patterns(names or []):
        out, count = pattern.subn("[PHI_NAME]", out)
        total += count
    return out, ({"NAME": total} if total else {})


def redact_with_known(text: str, names: Iterable[str], redact: Callable) -> Tuple[str, Dict[str, int]]:
    """Remove known names, then run another redactor and combine the counts."""
    out, counts = redact_known_names(text, names)
    out, more = redact(out)
    for phi_type, count in more.items():
        counts[phi_type] = counts.get(phi_type, 0) + count
    return out, counts


def known_names_from_fhir(resources: Iterable[Dict]) -> List[str]:
    """Collect names from FHIR Patient, Practitioner, RelatedPerson and CareTeam resources."""
    names: List[str] = []
    for resource in resources:
        kind = resource.get("resourceType")
        if kind in ("Patient", "Practitioner", "RelatedPerson"):
            for entry in resource.get("name", []):
                parts = [*entry.get("given", []), entry.get("family", "")]
                names.append(" ".join(p for p in parts if p) or entry.get("text", ""))
        elif kind == "CareTeam":
            for participant in resource.get("participant", []):
                names.append(participant.get("member", {}).get("display", ""))
    return list(dict.fromkeys(name for name in names if name))

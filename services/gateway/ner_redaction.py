"""
Model-based PHI redaction, applied after the rule-based pass.

The model catches what rules cannot, mainly names in plain prose. It is loaded
on first use, and any load failure propagates so the gateway fails closed
rather than sending partly redacted text to the LLM.
"""

import os
import re

from phi_redaction import phi_redact

PLACEHOLDER = re.compile(r"\[(?:PHI_[A-Z]+|REDACTED)\]")
DOSE = re.compile(r"\b\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)*\s*(?:mg|mcg|g|mL|ml|units?)\b")

# Model labels mapped to redaction types. AGE and O are not redacted: ages under
# 90 are not PHI under Safe Harbor and are clinically useful.
LABEL_TYPES = {
    "PATIENT": "NAME",
    "STAFF": "NAME",
    "DATE": "DATE",
    "PHONE": "PHONE",
    "EMAIL": "EMAIL",
    "ID": "ID",
    "LOC": "LOCATION",
    "HOSP": "LOCATION",
    "PATORG": "LOCATION",
    "OTHERPHI": "OTHER",
}

_loaded = None


def _load_model():
    global _loaded
    if _loaded is None:
        from transformers import AutoModelForTokenClassification, AutoTokenizer

        path = os.environ.get("PHI_NER_MODEL", "obi/deid_roberta_i2b2")
        tokenizer = AutoTokenizer.from_pretrained(path)
        model = AutoModelForTokenClassification.from_pretrained(path, use_safetensors=True)
        model.eval()
        _loaded = (tokenizer, model)
    return _loaded


def _token_entities(text: str):
    """Return (start, end, PHI type) for each token the model marks as PHI."""
    tokenizer, model = _load_model()

    import torch

    encoded = tokenizer(
        text, truncation=True, max_length=512, stride=128, padding=True,
        return_overflowing_tokens=True, return_offsets_mapping=True, return_tensors="pt",
    )
    offsets = encoded.pop("offset_mapping").tolist()
    encoded.pop("overflow_to_sample_mapping")
    with torch.no_grad():
        predictions = model(**encoded).logits.argmax(dim=-1).tolist()

    entities = []
    for window, labels in zip(offsets, predictions):
        for (start, end), label in zip(window, labels):
            phi_type = LABEL_TYPES.get(model.config.id2label[label].split("-")[-1])
            if end > start and phi_type:
                entities.append((start, end, phi_type))
    return entities


def _overlaps(start: int, end: int, protected) -> bool:
    return any(start < p_end and p_start < end for p_start, p_end in protected)


def redact_entities(text: str):
    """Replace model-detected PHI. Returns (text, count of entities by PHI type)."""
    if not text:
        return text or "", {}

    protected = [m.span() for pattern in (PLACEHOLDER, DOSE) for m in pattern.finditer(text)]
    merged = []
    for start, end, phi_type in sorted(set(_token_entities(text))):
        if _overlaps(start, end, protected):
            continue
        # The model can mark part of a word, which would leave the rest behind.
        while start > 0 and text[start - 1].isalnum():
            start -= 1
        while end < len(text) and text[end].isalnum():
            end += 1
        if merged:
            last_start, last_end, last_type = merged[-1]
            touching = start <= last_end or not text[last_end:start].strip()
            if touching and (phi_type == last_type or start < last_end):
                merged[-1] = (last_start, max(end, last_end), last_type)
                continue
        merged.append((start, end, phi_type))

    counts = {}
    for start, end, phi_type in reversed(merged):
        text = f"{text[:start]}[PHI_{phi_type}]{text[end:]}"
        counts[phi_type] = counts.get(phi_type, 0) + 1
    return text, counts


def phi_redact_with_ner(text: str):
    """Run the rules, then the model on what the rules left."""
    redacted, counts = phi_redact(text)
    redacted, entity_counts = redact_entities(redacted)
    for phi_type, count in entity_counts.items():
        counts[phi_type] = counts.get(phi_type, 0) + count
    return redacted, counts

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
# Clinical words the model must not redact. Device names that are not surnames are
# kept anywhere; eponyms only before a clinical noun, since Parkinson or Murphy can
# also be a patient's name.
CLINICAL_TERMS = re.compile(
    r"(?i)\b(?:foley|picc|dobhoff|swan[- ]ganz|port-a-cath)\b"
    r"|\b[A-Za-z]+(?:-[A-Za-z]+)?(?:'s)?\s+(?:disease|syndrome|palsy|catheter|sign|lymphoma|esophagus"
    r"|thyroiditis|dementia|reflex|respirations|maneuver|procedure)\b"
)

# Model labels mapped to redaction types. O is not redacted, and AGE is not by
# default: ages under 90 are not PHI under Safe Harbor and are clinically useful.
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
    # StanfordAIMI/stanford-deidentifier-base labels.
    "HCW": "NAME",
    "HOSPITAL": "LOCATION",
    "VENDOR": "OTHER",
}

MIN_SCORE = 0.01

# Models fine-tuned by eval/train_deid.py use AGE only for ages over 89 and record
# that in their config, so their AGE label can be redacted.
AGE_OVER_89_FLAG = "medguard_age_over_89"

_loaded = {}
_lexicon = None
NAME_TOKEN = re.compile(r"[A-Za-z]{3,}")


def _label_types(config):
    """Map each model label index to a redaction type, or None to keep the token."""
    types = dict(LABEL_TYPES)
    if getattr(config, AGE_OVER_89_FLAG, False) or os.environ.get("PHI_NER_AGE_OVER_89") == "true":
        types["AGE"] = "AGE"
    return [types.get(config.id2label[index].split("-")[-1]) for index in range(len(config.id2label))]


def _extra_models():
    """Models whose own top-label detections are added to the primary model's (a union)."""
    return [path.strip() for path in os.environ.get("PHI_NER_EXTRA_MODELS", "").split(",") if path.strip()]


def _load_model(path: str = None):
    path = path or os.environ.get("PHI_NER_MODEL", "obi/deid_roberta_i2b2")
    if path not in _loaded:
        from transformers import AutoModelForTokenClassification, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(path)
        model = AutoModelForTokenClassification.from_pretrained(path, use_safetensors=True)
        import torch

        if torch.cuda.is_available():
            model.to("cuda")
        model.eval()
        _loaded[path] = (tokenizer, model)
    return _loaded[path]


def _token_scores(text: str, path: str = None):
    """Return (start, end, PHI type, PHI probability, is top label) for candidate tokens."""
    tokenizer, model = _load_model(path)

    import torch

    encoded = tokenizer(
        text, truncation=True, max_length=512, stride=128, padding=True,
        return_overflowing_tokens=True, return_offsets_mapping=True, return_tensors="pt",
    )
    offsets = encoded.pop("offset_mapping").tolist()
    encoded.pop("overflow_to_sample_mapping")
    encoded = {key: value.to(model.device) for key, value in encoded.items()}
    with torch.no_grad():
        probabilities = model(**encoded).logits.softmax(dim=-1).cpu()

    label_types = _label_types(model.config)
    phi_mask = torch.tensor([phi_type is not None for phi_type in label_types])
    phi_scores = probabilities[..., phi_mask].sum(dim=-1).tolist()
    phi_probabilities = probabilities.masked_fill(~phi_mask, 0)
    best_phi = phi_probabilities.argmax(dim=-1).tolist()
    top_labels = probabilities.argmax(dim=-1).tolist()

    tokens = []
    for w, window in enumerate(offsets):
        for t, (start, end) in enumerate(window):
            if end > start and phi_scores[w][t] >= MIN_SCORE:
                is_top = label_types[top_labels[w][t]] is not None
                tokens.append((start, end, label_types[best_phi[w][t]], phi_scores[w][t], is_top))
    return tokens


def _token_entities(text: str):
    """Return (start, end, PHI type) for tokens that pass the decision rule.

    By default a token is PHI when a PHI label is the model's top choice. Setting
    PHI_NER_THRESHOLD marks it PHI when total PHI probability reaches that value.
    Models in PHI_NER_EXTRA_MODELS add their own top-label detections.
    """
    threshold = os.environ.get("PHI_NER_THRESHOLD") or None  # empty means top label
    entities = []
    for start, end, phi_type, score, is_top in _token_scores(text):
        if is_top if threshold is None else score >= float(threshold):
            entities.append((start, end, phi_type))
    for path in _extra_models():
        entities += [(start, end, phi_type) for start, end, phi_type, _, is_top in _token_scores(text, path) if is_top]
    return entities


def _load_lexicon():
    global _lexicon
    if _lexicon is None:
        path = os.environ.get("PHI_NAME_LEXICON_FILE") or os.path.join(os.path.dirname(__file__), "name_lexicon.txt")
        with open(path, encoding="utf-8") as handle:
            _lexicon = {line.strip() for line in handle if line.strip()}
    return _lexicon


def redact_lexicon_names(text: str):
    """Redact words on the name lexicon (names that are not ordinary words).

    Off unless PHI_NAME_LEXICON=true. Many names in clinical notes are bare surnames
    with no title or capital letter for a model to go on; the lexicon catches the ones
    that cannot be mistaken for ordinary English (eval/build_name_lexicon.py).
    """
    if os.environ.get("PHI_NAME_LEXICON") != "true" or not text:
        return text or "", 0
    lexicon = _load_lexicon()
    protected = [m.span() for m in PLACEHOLDER.finditer(text)]
    hits = [m.span() for m in NAME_TOKEN.finditer(text)
            if m.group().lower() in lexicon and not _overlaps(*m.span(), protected)]
    for start, end in reversed(hits):
        text = f"{text[:start]}[PHI_NAME]{text[end:]}"
    return text, len(hits)


def _overlaps(start: int, end: int, protected) -> bool:
    return any(start < p_end and p_start < end for p_start, p_end in protected)


def redact_entities(text: str):
    """Replace model-detected PHI. Returns (text, count of entities by PHI type)."""
    if not text:
        return text or "", {}

    protected = [m.span() for pattern in (PLACEHOLDER, DOSE, CLINICAL_TERMS) for m in pattern.finditer(text)]
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
    redacted, lexicon_names = redact_lexicon_names(redacted)
    if lexicon_names:
        counts["NAME"] = counts.get("NAME", 0) + lexicon_names
    return redacted, counts

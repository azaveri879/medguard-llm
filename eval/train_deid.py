#!/usr/bin/env python3
"""
Fine-tune the PHI model on MIMIC-III notes with fake identifiers.

Uses only patients in the train split and names from the train list. Reads a
NOTEEVENTS CSV from stdin and prints aggregate progress only. The resulting
weights derive from credentialed data: keep them in eval/models/ (git-ignored)
and do not publish them.

Usage (from eval/):
    python train_deid.py --output-dir models/pilot < notes.csv
"""

import argparse
import random
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

BASE_MODEL = "obi/deid_roberta_i2b2"
IGNORE_INDEX = -100
MODEL_TYPES = {
    "DATE": "DATE", "MONTH": "DATE", "ID": "ID", "PHONE": "PHONE", "EMAIL": "EMAIL",
    "ADDRESS": "LOC", "LOCATION": "LOC", "FACILITY": "HOSP", "AGE_OVER_89": "AGE",
}


def model_type(span: Dict) -> str:
    if span["label"] == "NAME":
        return "STAFF" if span.get("role") == "care_team" else "PATIENT"
    return MODEL_TYPES[span["label"]]


def window_labels(offsets: List[Tuple[int, int]], spans: List[Dict], label2id: Dict[str, int]) -> List[int]:
    """Convert character spans into BILOU token labels for one tokenized window."""
    entities = [s for s in spans if s["label"] != "KEEP"]
    assigned: List[object] = [None] * len(offsets)
    for index, (start, end) in enumerate(offsets):
        if end <= start:
            assigned[index] = IGNORE_INDEX
            continue
        for span_id, span in enumerate(entities):
            if start < span["end"] and span["start"] < end:
                assigned[index] = span_id
                break

    labels = []
    for index, value in enumerate(assigned):
        if value == IGNORE_INDEX:
            labels.append(IGNORE_INDEX)
        elif value is None:
            labels.append(label2id["O"])
        elif entities[value]["label"] == "SKIP":
            labels.append(IGNORE_INDEX)
        else:
            starts = index == 0 or assigned[index - 1] != value
            ends = index == len(assigned) - 1 or assigned[index + 1] != value
            prefix = "U" if starts and ends else "B" if starts else "L" if ends else "I"
            labels.append(label2id[f"{prefix}-{model_type(entities[value])}"])
    return labels


def encode_notes(notes: List[Dict], tokenizer, label2id: Dict[str, int]) -> List[Dict]:
    examples = []
    for note in notes:
        encoded = tokenizer(
            note["text"], truncation=True, max_length=512, stride=128,
            return_overflowing_tokens=True, return_offsets_mapping=True,
        )
        for ids, mask, offsets in zip(
            encoded["input_ids"], encoded["attention_mask"], encoded["offset_mapping"]
        ):
            examples.append({
                "input_ids": ids,
                "attention_mask": mask,
                "labels": window_labels(offsets, note["spans"], label2id),
            })
    return examples


def collate(batch: List[Dict], pad_id: int, torch):
    width = max(len(example["input_ids"]) for example in batch)

    def pad(key: str, value: int):
        rows = [example[key] + [value] * (width - len(example[key])) for example in batch]
        return torch.tensor(rows)

    return {
        "input_ids": pad("input_ids", pad_id),
        "attention_mask": pad("attention_mask", 0),
        "labels": pad("labels", IGNORE_INDEX),
    }


def main():
    parser = argparse.ArgumentParser(description="Fine-tune the PHI model")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--per-category", type=int, default=1000)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=6)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args()

    import torch
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    from mimic_surrogates import build_name_pools, sample_notes

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    pools = build_name_pools()["train"]
    print(f"train name pool: {len(pools['first'])} first, {len(pools['last'])} last", flush=True)
    notes = sample_notes(sys.stdin, args.per_category, args.seed, split="train", name_pools=pools)

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForTokenClassification.from_pretrained(BASE_MODEL, use_safetensors=True).to(device)
    examples = encode_notes(notes, tokenizer, model.config.label2id)
    print(f"notes: {len(notes)} | windows: {len(examples)} | device: {device}", flush=True)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=0.01)
    started = time.time()
    model.train()
    for epoch in range(1, args.epochs + 1):
        random.shuffle(examples)
        running, steps = 0.0, 0
        for start in range(0, len(examples), args.batch_size):
            batch = collate(examples[start:start + args.batch_size], tokenizer.pad_token_id, torch)
            if not (batch["labels"] != IGNORE_INDEX).any():
                continue
            batch = {key: value.to(device) for key, value in batch.items()}
            optimizer.zero_grad(set_to_none=True)
            loss = model(**batch).loss
            if not torch.isfinite(loss):
                raise RuntimeError(f"Non-finite loss at epoch {epoch}, step {steps + 1}; stopping")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            running += loss.item()
            steps += 1
            if steps % 50 == 0:
                print(
                    f"epoch {epoch} step {steps} loss {running / steps:.4f} "
                    f"elapsed {time.time() - started:.0f}s",
                    flush=True,
                )
        print(f"epoch {epoch} done, mean loss {running / max(steps, 1):.4f}", flush=True)

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output, safe_serialization=True)
    tokenizer.save_pretrained(output)
    print(f"saved model after {time.time() - started:.0f}s", flush=True)


if __name__ == "__main__":
    main()

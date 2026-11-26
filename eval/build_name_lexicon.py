#!/usr/bin/env python3
"""
Build the gateway's name lexicon: first and last names that are not ordinary words.

Names come from Faker's person providers in 15 locales. Ordinary English words
(the system word list, lowercase entries only) and clinical eponyms are removed,
so "Brown", "May" or "Foley" are never redacted on the list alone. The result is
written one name per line, lowercase, for services/gateway/name_lexicon.txt.

Usage (from eval/):
    python build_name_lexicon.py --output ../services/gateway/name_lexicon.txt
"""

import argparse
from pathlib import Path

from deid_data import EPONYMS

LOCALES = ["en_US", "en_GB", "en_IN", "es_ES", "es_MX", "de_DE", "fr_FR", "it_IT", "pl_PL",
           "en_CA", "en_AU", "en_IE", "pt_BR", "nl_NL", "sv_SE"]
# Clinical words that are also surnames in some locale.
CLINICAL = {"foley", "swan", "ganz", "levin", "hickman", "port", "picc", "tele", "lasix", "coumadin",
            "heparin", "norvasc"}


def build(word_list: str = "/usr/share/dict/words"):
    from faker import Faker

    names = set()
    for locale in LOCALES:
        provider = Faker(locale).provider("faker.providers.person")
        for attr in ("first_names", "last_names"):
            values = getattr(provider, attr, ())
            names |= {name.lower() for name in values}
    words = {line.strip() for line in open(word_list) if line[:1].islower()}
    clinical = {term.split()[0].lower() for term in EPONYMS} | CLINICAL
    return sorted(n for n in names if len(n) >= 3 and n.isascii() and n.isalpha() and n not in words and n not in clinical)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--output", default="../services/gateway/name_lexicon.txt")
    parser.add_argument("--word-list", default="/usr/share/dict/words")
    args = parser.parse_args()
    lexicon = build(args.word_list)
    Path(args.output).write_text("\n".join(lexicon) + "\n")
    print(f"{len(lexicon)} names -> {args.output}")


if __name__ == "__main__":
    main()

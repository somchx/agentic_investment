"""One-time (re-runnable, idempotent) batch job: translate every XBRL tag's
official SEC label into Thai via Claude, and cache the result in
xbrl_tag_translations (see db.py / models.py). Never called from a request
handler -- the API layer only ever reads the cache (db.get_tag_translations).

Run manually: python3 translate_xbrl_tags.py
Real, small LLM cost -- explicitly approved before running, same standing
rule as every other paid call in this project. Already-cached tags are
skipped, so re-running after adding a new pilot company only pays for the
new tags.
"""

import json

from db import get_tag_translations, save_tag_translations
from llm_client import call_claude
from sec_client import KNOWN_CIKS, get_company_facts
from xbrl_extract import list_available_tags

BATCH_SIZE = 40


def collect_all_labels() -> dict[str, str]:
    """tag -> English label, across every pilot company (same aggregation
    /api/xbrl-tags does)."""
    by_tag: dict[str, str] = {}
    for ticker in sorted(KNOWN_CIKS.keys()):
        try:
            facts_json = get_company_facts(ticker)
        except Exception:  # noqa: BLE001
            continue
        for t in list_available_tags(facts_json):
            by_tag.setdefault(t["tag"], t["label"])
    return by_tag


def translate_batch(pairs: list[tuple[str, str]]) -> dict[str, str]:
    """`pairs` is [(tag, label_en), ...]. Returns {tag: label_th}. Asks
    Claude for a JSON object keyed by tag so a malformed/missing entry for
    one tag doesn't silently misalign the rest (a plain ordered array would
    risk exactly that if the model ever drops or merges one line)."""
    numbered = {tag: label for tag, label in pairs}
    prompt = (
        "Translate each of the following US GAAP / SEC XBRL financial "
        "concept labels into natural, standard financial/accounting Thai "
        "as used by Thai investors and accountants (e.g. \"รายได้\" for "
        "Revenue, \"กำไรขั้นต้น\" for Gross Profit). These are official "
        "accounting terms, not general prose -- keep the translation "
        "precise and in accounting register, not a literal word-for-word "
        "translation. Reply with ONLY a single JSON object mapping each "
        "exact tag name (the keys below) to its Thai translation, no other "
        "text, no markdown fences.\n\n"
        + json.dumps(numbered, ensure_ascii=False, indent=0)
    )
    resp = call_claude([{"role": "user", "content": prompt}], max_tokens=8000)
    text = "".join(b.get("text", "") for b in resp["content"] if b.get("type") == "text").strip()
    usage = resp.get("usage", {})
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    result = json.loads(text)
    return result, usage


def main():
    all_labels = collect_all_labels()
    cached = get_tag_translations(list(all_labels.keys()))
    todo = [(tag, label) for tag, label in all_labels.items() if tag not in cached]
    print(f"{len(all_labels)} total tags, {len(cached)} already cached, {len(todo)} to translate")

    total_in, total_out = 0, 0
    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i : i + BATCH_SIZE]
        print(f"  translating {i}-{i + len(batch)} of {len(todo)}...")
        translations, usage = translate_batch(batch)
        total_in += usage.get("input_tokens", 0)
        total_out += usage.get("output_tokens", 0)
        entries = [
            (tag, label, translations[tag])
            for tag, label in batch
            if tag in translations and translations[tag]
        ]
        missing = [tag for tag, _ in batch if tag not in translations or not translations[tag]]
        if missing:
            print(f"    WARNING: {len(missing)} tag(s) missing from response, left untranslated: {missing[:5]}...")
        save_tag_translations(entries)

    cost = total_in / 1e6 * 3.0 + total_out / 1e6 * 15.0
    print(f"\nDone. input_tokens={total_in} output_tokens={total_out} cost=${cost:.4f}")


if __name__ == "__main__":
    main()

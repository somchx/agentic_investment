"""Paired statistical comparison of two approaches on the same claims.

- McNemar's test on per-claim correctness (exact binomial p-value, plus the
  continuity-corrected chi-square for reference).
- Paired bootstrap confidence intervals for the difference in accuracy and
  in macro-F1 (claims resampled with replacement, both approaches scored on
  the same resample).

Only claims that have a finalized gold label AND a prediction from both
approaches are used; the counts dropped are reported. Nothing here says one
method is "better" in general: a significant result applies to this claim
set, this model snapshot and this corpus.
"""

import math
import random

from .metrics import classification_metrics


def paired(preds_a: list[dict], preds_b: list[dict], gold: dict[str, dict]) -> dict:
    a = {p["claim_id"]: p.get("predicted_label") for p in preds_a}
    b = {p["claim_id"]: p.get("predicted_label") for p in preds_b}
    ids = sorted(set(a) & set(b) & set(gold))
    return {"claim_ids": ids, "y_true": [gold[i]["label"] for i in ids], "pred_a": [a[i] for i in ids], "pred_b": [b[i] for i in ids],
            "dropped_no_gold": len((set(a) | set(b)) - set(gold)), "dropped_unpaired": len((set(a) ^ set(b)) & set(gold))}


def mcnemar(y_true: list[str], pred_a: list, pred_b: list) -> dict:
    ca = [p == t for p, t in zip(pred_a, y_true)]
    cb = [p == t for p, t in zip(pred_b, y_true)]
    b = sum(1 for x, y in zip(ca, cb) if x and not y)  # A right, B wrong
    c = sum(1 for x, y in zip(ca, cb) if y and not x)  # B right, A wrong
    n = b + c
    if n == 0:
        p_exact = 1.0
    else:
        k = min(b, c)
        p_exact = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)
    chi2 = (abs(b - c) - 1) ** 2 / n if n else 0.0
    p_chi2 = math.erfc(math.sqrt(chi2 / 2)) if n else 1.0
    odds = (c + 0.5) / (b + 0.5)
    return {"n_pairs": len(y_true), "a_right_b_wrong": b, "b_right_a_wrong": c, "both_right": sum(1 for x, y in zip(ca, cb) if x and y),
            "both_wrong": sum(1 for x, y in zip(ca, cb) if not x and not y), "discordant": n,
            "p_value_exact": p_exact, "chi2_cc": chi2, "p_value_chi2_cc": p_chi2,
            "odds_ratio_b_over_a": odds, "accuracy_a": sum(ca) / len(ca) if ca else None,
            "accuracy_b": sum(cb) / len(cb) if cb else None,
            "accuracy_diff_b_minus_a": (sum(cb) - sum(ca)) / len(ca) if ca else None,
            "note": "exact test recommended: discordant pairs < 25" if n < 25 else None}


def _acc(t, p):
    return sum(1 for x, y in zip(t, p) if x == y) / len(t) if t else float("nan")


def _f1(t, p):
    m = classification_metrics(t, p)["macro_f1"]
    return m if m is not None else float("nan")


def bootstrap_diff(y_true: list[str], pred_a: list, pred_b: list, n_boot: int = 5000, seed: int = 20261102,
                   alpha: float = 0.05) -> dict:
    n = len(y_true)
    if n == 0:
        return {"n": 0}
    rng = random.Random(seed)
    out = {"n": n, "n_boot": n_boot, "seed": seed, "confidence": 1 - alpha}
    for name, fn in (("accuracy", _acc), ("macro_f1", _f1)):
        point = fn(y_true, pred_b) - fn(y_true, pred_a)
        diffs = []
        for _ in range(n_boot):
            idx = [rng.randrange(n) for _ in range(n)]
            t = [y_true[i] for i in idx]
            diffs.append(fn(t, [pred_b[i] for i in idx]) - fn(t, [pred_a[i] for i in idx]))
        diffs = sorted(d for d in diffs if not math.isnan(d))
        lo = diffs[int(math.floor(alpha / 2 * (len(diffs) - 1)))]
        hi = diffs[int(math.ceil((1 - alpha / 2) * (len(diffs) - 1)))]
        out[name] = {"diff_b_minus_a": point, "ci_low": lo, "ci_high": hi,
                     "p_boot_two_sided": min(1.0, 2 * min(sum(1 for d in diffs if d <= 0), sum(1 for d in diffs if d >= 0)) / len(diffs))}
    return out


def compare(preds_a: list[dict], preds_b: list[dict], gold: dict[str, dict], n_boot: int = 5000, seed: int = 20261102) -> dict:
    p = paired(preds_a, preds_b, gold)
    return {"pairing": {k: p[k] for k in ("dropped_no_gold", "dropped_unpaired")}, "n": len(p["claim_ids"]),
            "mcnemar": mcnemar(p["y_true"], p["pred_a"], p["pred_b"]) if p["claim_ids"] else None,
            "bootstrap": bootstrap_diff(p["y_true"], p["pred_a"], p["pred_b"], n_boot=n_boot, seed=seed)}

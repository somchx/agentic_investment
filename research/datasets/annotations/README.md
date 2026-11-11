# Reviewer annotation files

One JSON Lines file per independent human reviewer: `<reviewer_id>.jsonl`.
Schema and rules: `../annotation_guidelines.md`. `engine.datasets.load_annotations()`
validates every line (label vocabulary, human reviewer, evidence fields) and
refuses a reviewer labelling the same claim twice.

Reviewers can also fill an Excel workbook; `scripts/annotation_workbook.py import`
turns a returned workbook into `<reviewer_id>.jsonl` here (see the guidelines §5).

No annotations exist yet. `example_annotation.json.txt` shows one record; it is
not a `.jsonl` file, so it is never loaded as a label.

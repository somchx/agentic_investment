#!/bin/sh
# Copy run artifacts that are not (or not yet) in git to a directory outside any worktree, so a deleted
# worktree cannot take them with it (incident 2026-11-18, docs/a3v2_2/10_gold150_run_log.md).
# Additive only (rsync without --delete); never touches the source. Safe to run while an experiment runs:
# call it in a loop, e.g.  while sleep 300; do sh research/scripts/backup_artifacts.sh; done
#
#   sh research/scripts/backup_artifacts.sh [destination]     (default: ~/ReasonCheck-backups)
set -e
cd "$(dirname "$0")/../.."
DEST="${1:-$HOME/ReasonCheck-backups}/$(git rev-parse --abbrev-ref HEAD | tr '/' '_')"
mkdir -p "$DEST"
for p in research/results/runs research/results/llm_cache research/results/cost_ledger research/results/gold150 \
         backend/app/data/cache; do
  [ -e "$p" ] && mkdir -p "$DEST/$(dirname "$p")" && rsync -a "$p" "$DEST/$(dirname "$p")/"
done
# content list of what was backed up (paths + sha256), to check a later restore
(cd "$DEST" && find . -type f ! -name SHA256SUMS.backup -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256 > SHA256SUMS.backup)
echo "backed up to $DEST ($(wc -l < "$DEST/SHA256SUMS.backup") files)"

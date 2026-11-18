#!/bin/sh
# Fail if staged changes contain an API key, auth header or e-mail address. Run before every commit:
#   sh research/scripts/secret_scan.sh
if git diff --cached -U0 | grep -nE '^\+.*(sk-ant-[A-Za-z0-9_-]{20,}|x-api-ke[y]:|ANTHROPIC_API_KE[Y]=[^$"]|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,})'; then
  echo "secret_scan: possible secret above; commit blocked" >&2
  exit 1
fi
echo "secret_scan: clean"

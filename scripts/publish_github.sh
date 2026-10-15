#!/usr/bin/env bash
# Create the public GitHub repo, push main, and open good-first issues.
set -euo pipefail

cd "$(dirname "$0")/.."

if ! gh auth status >/dev/null 2>&1; then
  echo "gh is not authenticated. Run: gh auth login -h github.com" >&2
  exit 1
fi

USER="$(gh api user -q .login)"
echo "GitHub user: ${USER}"

# Replace placeholder remote if needed.
CURRENT="$(git remote get-url origin 2>/dev/null || true)"
if [[ -z "${CURRENT}" ]]; then
  git remote add origin "https://github.com/${USER}/agentledger.git"
elif [[ "${CURRENT}" == *"YOUR_USERNAME"* ]]; then
  git remote set-url origin "https://github.com/${USER}/agentledger.git"
fi

# Create repo if missing, then push.
if gh repo view "${USER}/agentledger" >/dev/null 2>&1; then
  echo "Repo already exists: https://github.com/${USER}/agentledger"
  git push -u origin main
else
  gh repo create agentledger --public --source=. --remote=origin --push
fi

echo "Remote: $(git remote get-url origin)"
python3 scripts/publish_good_first_issues.py
echo "Done: https://github.com/${USER}/agentledger"

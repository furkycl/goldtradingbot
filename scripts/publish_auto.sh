#!/usr/bin/env bash
# Publish automated changes (config/params.yaml and reports/ ONLY) to main.
# Usage: publish_auto.sh <kind> <branch-prefix> [<extra commit body file>]
# Flow: stage -> diff guard -> branch -> commit -> push -> PR + merge (if
# Actions may create PRs) else tested fast-forward of main. Every failure is
# annotated with the exact step so it shows up in `gh run view`.
set -euo pipefail
KIND="$1"; PREFIX="$2"; BODY_FILE="${3:-}"
R="${GITHUB_REPOSITORY:?}"
step=""
trap 'echo "::error::publish_auto failed at step: $step (line $LINENO)"' ERR

step="stage"; git add -A config/params.yaml reports/
step="diff-guard(staged)"; python scripts/check_auto_diff.py HEAD --staged
if git diff --cached --quiet; then echo "nothing to publish"; exit 0; fi

BR="$PREFIX-$(date -u +%Y%m%d-%H%M%S)"
step="config"; git config user.name "goldbot-auto"; git config user.email "goldbot-auto@users.noreply.github.com"
step="branch"; git checkout -b "$BR"
step="commit"
if [ -n "$BODY_FILE" ] && [ -f "$BODY_FILE" ]; then
  git commit -q -m "auto: $KIND ($(date -u +%F))" -m "$(head -c 3000 "$BODY_FILE")"
else
  git commit -q -m "auto: $KIND ($(date -u +%F))"
fi
step="push-branch"; git push -q -u origin "$BR"

step="pr-create"
if PR_URL=$(gh pr create --base main --head "$BR" --title "auto: $KIND $(date -u +%F)" \
              --body "Automated. Only config/params.yaml and reports/ change; tests ran in the job." 2>/dev/null); then
  echo "PR: $PR_URL"
  N="${PR_URL##*/}"
  step="pr-merge"
  for attempt in 1 2 3 4 5 6; do
    STATE=$(gh api "repos/$R/pulls/$N" --jq .mergeable_state 2>/dev/null || echo unknown)
    if [ "$STATE" != "unknown" ] && gh api "repos/$R/pulls/$N/merge" -X PUT -f merge_method=squash >/dev/null 2>&1; then
      echo "merged PR #$N"; git push -q origin --delete "$BR" || true; exit 0
    fi
    echo "merge attempt $attempt: state=$STATE"; sleep $((attempt * 10))
  done
  echo "::warning::PR #$N could not be merged automatically; falling back to fast-forward"
else
  echo "::notice::Actions may not create PRs in this repo; using tested fast-forward of main"
fi

for attempt in 1 2 3; do
  step="fetch-main"; git fetch -q origin main
  step="rebase"; git rebase -q origin/main
  step="diff-guard(rebased)"; python scripts/check_auto_diff.py origin/main
  step="pytest(rebased)"; python -m pytest -q -x
  step="push-main"
  if git push -q origin "HEAD:main"; then
    echo "fast-forwarded main"; git push -q origin --delete "$BR" || true; exit 0
  fi
  echo "push rejected (attempt $attempt), retrying"; sleep $((attempt * 20))
done
step="give-up"; false

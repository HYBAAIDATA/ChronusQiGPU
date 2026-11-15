#!/bin/bash
# Publish a HYBA Mine run report to the private results branch (no credentials in it).
#   publish-report.sh <report file> <report name>
set -uo pipefail
report="$1"
name="$2"
branch="${RESULTS_BRANCH:-cowork/supervisor-results-20261111}"
work="$RUNNER_TEMP/results"
git config --global user.name "hyba-mine-deploy"
git config --global user.email "hyba-mine-deploy@users.noreply.github.com"
for attempt in 1 2 3 4 5; do
  rm -rf "$work"
  git worktree prune
  if ! git fetch --quiet --depth 1 origin "+refs/heads/${branch}:refs/remotes/origin/hyba-mine-results"; then
    echo "results branch not reachable"
    exit 0
  fi
  git worktree add --quiet --detach "$work" refs/remotes/origin/hyba-mine-results
  mkdir -p "$work/hyba-mine/runs"
  cp "$report" "$work/hyba-mine/runs/$name"
  cp "$report" "$work/hyba-mine/LATEST.txt"
  git -C "$work" add hyba-mine
  git -C "$work" commit --quiet -m "hyba-mine report $name" || { echo "report unchanged"; exit 0; }
  if git -C "$work" push --quiet origin "HEAD:refs/heads/${branch}"; then
    echo "report published: hyba-mine/runs/$name"
    exit 0
  fi
  sleep $((attempt * 5))
done
echo "report not published"
exit 0

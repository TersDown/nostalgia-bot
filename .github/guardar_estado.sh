#!/usr/bin/env bash
# Guarda data/*.jsonl en el repositorio. Cada workflow escribe su propio archivo, así el rebase no choca.
set -euo pipefail
git config user.name "nostalgia-bot"
git config user.email "nostalgia-bot@users.noreply.github.com"
git add data/
git diff --cached --quiet && exit 0
git commit -m "Estado: $1"
for i in 1 2 3 4 5; do
  git pull --rebase && git push && exit 0
  sleep $((i * 5))
done
exit 1

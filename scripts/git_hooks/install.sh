#!/bin/sh
# Instaluje globalny git hook (core.hooksPath) — auto-crystallize po każdym
# commicie, w każdym repo na tej maszynie. Idempotentny, bezpieczny do
# wielokrotnego uruchomienia.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
chmod +x "$DIR/post-commit"
git config --global core.hooksPath "$DIR"
echo "core.hooksPath -> $DIR"
echo "Uwaga: jeśli jakieś repo miało już własny .git/hooks/post-commit,"
echo "przenieś go do .git/hooks/post-commit.local (będzie doczepiony)."

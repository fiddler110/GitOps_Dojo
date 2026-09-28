#!/usr/bin/env bash
# Exports each workshop's talk (workshops/<name>/content/slides/presentation.md)
# to handouts/<name>_presentation.pptx: one picture per slide, exactly as the
# browser shows it (theme, code colours, diagrams), with the speaker notes as
# editable text.
#
#   handouts/build-presentations.sh             rebuild decks whose sources changed
#   handouts/build-presentations.sh --all       rebuild every deck
#   handouts/build-presentations.sh --check     list stale decks, exit 1 if any
#   handouts/build-presentations.sh NAME...     rebuild just these workshops
#
# Sources are read from the git index (what the next commit holds), not the
# working tree, so the pre-commit hook (.githooks/pre-commit) builds exactly
# what is being committed. handouts/.presentation-sources records, per deck,
# a hash of its inputs: the deck and its images (not the folder's other
# pages), the shared theme and the engine's highlight grammars. A deck is stale when that hash no longer matches.
#
# Marp's export needs Chromium, which the class's slide server leaves out, so
# this uses the upstream marp-cli image at the release the server runs
# (engine/presentation/package.json), with the server's engine.js mounted in.
# Diagrams load mermaid from its CDN, so the export needs internet.
set -euo pipefail

IMAGE="docker.io/marpteam/marp-cli:v3.4.0@sha256:b2e5207e92a25405e6b17e53e3d35bb06c25b8bec349c66639b3151d80436d3d"
root="$(git rev-parse --show-toplevel)"
cd "$root"
manifest=handouts/.presentation-sources
shared=(workshops/assets engine/presentation/engine.js)

decks() { git ls-files 'workshops/*/content/slides/presentation.md' | cut -d/ -f2; }

# hash NAME: one hash over the index's blob ids for the deck's inputs.
hash() {
  git ls-files -s -- "workshops/$1/content/slides" "${shared[@]}" \
    | grep -Ev '/content/slides/(lab/|(cheat-sheet|index|labs|lab-index)\.md$)' \
    | sha256sum | cut -d' ' -f1
}

recorded() { [ -f "$manifest" ] && awk -v n="$1" '$1 == n { print $2 }' "$manifest" || true; }

stale() {
  local n
  for n in $(decks); do
    [ "$(hash "$n")" = "$(recorded "$n")" ] && [ -f "handouts/${n}_presentation.pptx" ] || echo "$n"
  done
}

build() {
  local n="$1" tmp slides
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN
  git ls-files -z -- "workshops/$n/content/slides" workshops/assets \
    | git checkout-index -z --stdin --prefix="$tmp/"
  slides="$tmp/workshops/$n/content/slides"
  # The slide server mounts workshops/assets at slides/assets; do the same.
  rm -rf "$slides/assets" && cp -r "$tmp/workshops/assets" "$slides/assets"
  # The image drops to its own marp user, which has to write the output.
  chmod -R a+rwX "$slides"
  echo "handouts: exporting $n"
  podman run --rm -v "$slides:/home/marp/app:Z" \
    -v "$root/engine/presentation/engine.js:/home/marp/.cli/engine.js:ro,Z" \
    "$IMAGE" --engine /home/marp/.cli/engine.js --html --allow-local-files \
    --pptx presentation.md -o out.pptx >/dev/null
  cp "$slides/out.pptx" "handouts/${n}_presentation.pptx"
  { [ -f "$manifest" ] && awk -v n="$n" '$1 != n' "$manifest"; echo "$n $(hash "$n")"; } \
    | sort > "$manifest.tmp" && mv "$manifest.tmp" "$manifest"
}

case "${1:-}" in
  --check)
    out="$(stale)"
    [ -z "$out" ] && { echo "handouts: every deck is current"; exit 0; }
    printf 'handouts: stale: %s\n' $out; exit 1 ;;
  --all) targets="$(decks)" ;;
  "") targets="$(stale)" ;;
  *) targets="$*" ;;
esac

[ -n "$targets" ] || { echo "handouts: every deck is current"; exit 0; }
command -v podman >/dev/null || { echo "handouts: podman is needed to export slides" >&2; exit 1; }
for n in $targets; do
  [ -n "$(git ls-files "workshops/$n/content/slides/presentation.md")" ] \
    || { echo "handouts: no workshops/$n/content/slides/presentation.md in the index" >&2; exit 1; }
  build "$n"
done

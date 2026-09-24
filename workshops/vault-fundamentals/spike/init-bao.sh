#!/bin/sh
# P0 spike helper: initialise and unseal the spike OpenBao (one key share),
# or just unseal it again after a restart. Keys go to $SPIKE_DIR/init.json,
# never into the repo. Prints the export line for the root token.
#   SPIKE_DIR=<scratch dir> sh workshops/vault-fundamentals/spike/init-bao.sh
set -eu
SPIKE_DIR="${SPIKE_DIR:?Set SPIKE_DIR to a scratch directory}"
b() { podman exec -e BAO_ADDR=http://127.0.0.1:8200 workshop_openbao bao "$@"; }
if b status -format=json 2>/dev/null | grep -q '"initialized": false'; then
  b operator init -key-shares=1 -key-threshold=1 -format=json > "$SPIKE_DIR/init.json"
  chmod 600 "$SPIKE_DIR/init.json"; echo "initialised; keys in $SPIKE_DIR/init.json"
fi
[ -f "$SPIKE_DIR/init.json" ] || { echo "OpenBao is initialised but $SPIKE_DIR/init.json is missing: run ./run.sh stop (wipes volumes) and start again" >&2; exit 1; }
key="$(python3 -B -c "import json,sys;print(json.load(open(sys.argv[1]))['unseal_keys_b64'][0])" "$SPIKE_DIR/init.json")"
b operator unseal "$key" | grep Sealed
echo "export BAO_TOKEN=$(python3 -B -c "import json,sys;print(json.load(open(sys.argv[1]))['root_token'])" "$SPIKE_DIR/init.json")"

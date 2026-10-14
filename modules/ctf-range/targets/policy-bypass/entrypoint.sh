#!/bin/sh
# Attack-pack mode (default): the app answers on $PORT directly, exactly as before.
# Defend slot (CTF_DEFEND_PROXY=1): app on 127.0.0.1:5001, identity proxy on 5000.
if [ "${CTF_DEFEND_PROXY:-0}" != "1" ]; then
  exec python3 /app/app.py
fi
python3 /app/app.py &
APP=$!
python3 /app/proxy.py &
PROXY=$!
trap 'kill $APP $PROXY 2>/dev/null' TERM INT
while kill -0 $APP 2>/dev/null && kill -0 $PROXY 2>/dev/null; do sleep 1; done
kill $APP $PROXY 2>/dev/null
exit 1

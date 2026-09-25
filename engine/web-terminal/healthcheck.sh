#!/bin/sh
# Container health probe: workspace-control.py answers /status only when the request carries the shared control
# token, so a bare wget gets a 403 and would mark the container unhealthy forever.
#
# This lives in one place on purpose. A workshop image that sets its own HEALTHCHECK *replaces* the inherited one, and
# copies of the wget line have drifted before (the token header was added to the base and missed in two workshops).
# Workshop Dockerfiles restate only the line below, so a static scan of them still sees a HEALTHCHECK:
#     HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 CMD web-terminal-healthcheck
wget -q -O /dev/null --header="X-Control-Token: ${CONTROL_TOKEN}" http://127.0.0.1:7682/status || exit 1

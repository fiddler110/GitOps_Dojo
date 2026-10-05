# Extra terminal tools for ctf-defend. ./run.sh builds it on top of the base
# image and any module's tools (BASE is set to the image below this one in the
# chain). Students have no internet: pin each tool's version and check its
# sha256 for every architecture. Don't set ENTRYPOINT. Start-up work goes in
# /etc/dojo/start.d/90-<name>.sh hooks (run as root, after accounts exist).
ARG BASE=gitopsdojo/web-terminal:base
FROM ${BASE}

# No extra tools: target 14's exploit/dump.py and sast/scan.py are stdlib
# python3, already on the base image. Just the provisioning hook below (gives
# each student their own customer-portal repo and its Actions secrets).
COPY start.d/90-ctf-defend.sh /etc/dojo/start.d/90-ctf-defend.sh
RUN chmod 0755 /etc/dojo/start.d/90-ctf-defend.sh

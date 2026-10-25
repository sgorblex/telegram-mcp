#!/usr/bin/env bash
# Pull the :production image on oci and restart the server, as the restricted `deploy` user.
# Every remote command must match /etc/sudoers.d/deploy exactly (tracked in the oci repo as
# conf/System/sudoers.d/deploy).
set -euo pipefail

: "${TG_DEPLOY_HOST:?TG_DEPLOY_HOST must be set (user@host)}"
: "${TG_DEPLOY_SSH_KEY:?TG_DEPLOY_SSH_KEY must be set (private key contents)}"
: "${TG_DEPLOY_KNOWN_HOSTS:?TG_DEPLOY_KNOWN_HOSTS must be set}"
: "${TG_REGISTRY:?TG_REGISTRY must be set}"
: "${TG_REGISTRY_USER:?TG_REGISTRY_USER must be set}"
: "${TG_REGISTRY_PASSWORD:?TG_REGISTRY_PASSWORD must be set}"

keyfile="$(mktemp)"
knownhosts="$(mktemp)"
trap 'rm -f "$keyfile" "$knownhosts"' EXIT

printf '%s\n' "$TG_DEPLOY_SSH_KEY" > "$keyfile"
chmod 600 "$keyfile"
printf '%s\n' "$TG_DEPLOY_KNOWN_HOSTS" > "$knownhosts"

remote_cmd="sudo podman login '${TG_REGISTRY}' -u '${TG_REGISTRY_USER}' --password-stdin \
  && sudo podman pull '${TG_REGISTRY}/telegram/mcp:production' \
  && sudo systemctl restart telegram-mcp \
  && echo 'ssh-deploy: telegram-mcp restarted'"

ssh -i "$keyfile" -o UserKnownHostsFile="$knownhosts" -o StrictHostKeyChecking=yes \
  "$TG_DEPLOY_HOST" "$remote_cmd" <<< "$TG_REGISTRY_PASSWORD"

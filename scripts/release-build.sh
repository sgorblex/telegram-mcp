#!/usr/bin/env bash
# Build the image and push :<version> and :production. Called by .woodpecker/release.yaml
# (a script, not inline: Woodpecker substitutes ${...} in pipeline files itself).
set -euo pipefail

: "${TG_REGISTRY:?TG_REGISTRY must be set}"
: "${CI_COMMIT_TAG:?CI_COMMIT_TAG must be set (v<version>)}"
version="${CI_COMMIT_TAG#v}"
revision="${CI_COMMIT_SHA:-$(git rev-parse HEAD)}"
image="$TG_REGISTRY/telegram/mcp"

# --load: the CLI builds through buildx's container driver, which otherwise keeps the
# result in its cache and leaves nothing for docker push.
docker build --load -f Containerfile \
  --label org.opencontainers.image.version="$version" \
  --label org.opencontainers.image.revision="$revision" \
  -t "$image:$version" -t "$image:production" .
docker push "$image:$version"
docker push "$image:production"

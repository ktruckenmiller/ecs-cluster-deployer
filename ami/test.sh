#!/bin/sh
set -e
rm -f manifest.json
docker run -it --rm \
  -v $(pwd)/ecs:/code \
  --workdir=/code \
  -e REGION=us-east-2 \
  -e IAM_ROLE \
  hashicorp/packer build ecs-linux-overlay2.json

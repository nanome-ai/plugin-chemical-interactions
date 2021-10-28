#!/bin/bash

parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "$parent_path"

# Create redeploy.sh
echo "./deploy.sh $*" > redeploy.sh
chmod +x redeploy.sh

existing=$(docker ps -aq -f name=chem_interactions)
if [ -n "$existing" ]; then
    echo "removing existing container"
    docker rm -f $existing
fi

ARGS="$*"
echo "$ARGS"
docker run \
--name chem_interactions \
--restart unless-stopped \
-e ARGS="$ARGS" \
chem_interactions

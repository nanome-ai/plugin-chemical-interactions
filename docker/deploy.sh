#!/bin/bash

# Determine whether environment variables coming from env-file, or plugin arguments.
env_arg=""
deploy_args=""
echo $PWD
while [ $# -gt 0 ]; do
  case $1 in
    --env-file ) env_arg="$1 $PWD/$2" && shift 2;;
    *) deploy_args=$deploy_args" $1" && shift ;;
  esac
done

# cd into docker folder, so that we can use relative paths
parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "$parent_path"

# Create redeploy.sh
echo "./deploy.sh $*" > redeploy.sh
chmod +x redeploy.sh

# Remove existing docker container
existing=$(docker ps -aq -f name=chem_interactions)
if [ -n "$existing" ]; then
    echo "removing existing container"
    docker rm -f $existing
fi

docker run \
--name chem_interactions \
$env_arg \
--restart unless-stopped \
-e ARGS="$deploy_args" \
chem_interactions

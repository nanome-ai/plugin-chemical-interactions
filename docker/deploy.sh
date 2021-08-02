#!/bin/bash

parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "$parent_path"

# Create redeploy.sh
echo "./deploy.sh $*" > redeploy.sh
chmod +x redeploy.sh

# default env file
ENV_FILE='../.env' 

# Create on the fly .env file to pass args into plugin container
ARGS="$*"
if [ -n "$ARGS" ];  then
    tmpfile=$(mktemp)
    echo ARGS=${ARGS} > $tmpfile
    ENV_FILE=$tmpfile
fi

docker-compose -f ../docker-compose-deploy.yml --env-file $ENV_FILE up -d

#!/bin/bash

parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "$parent_path"

# default env file
ENV_FILE='../.env' 

# Create on the fly .env file to pass args into plugin container
ARGS="$*"
if [ -n "$ARGS" ];  then
    tmpfile=$(mktemp)
    echo ARGS=${ARGS} > $tmpfile
    ENV_FILE=$tmpfile
fi 

docker-compose --env-file $ENV_FILE up  

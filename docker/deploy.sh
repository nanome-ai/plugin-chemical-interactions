#!/bin/bash

parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "$parent_path"

ENV_FILE='../.env'

NTS_HOST=''
NTS_PORT=''
while getopts 'a:p:vr' flag; do
  case "${flag}" in
    a) NTS_HOST="${OPTARG}" ;;
    p) NTS_PORT="${OPTARG}" ;;
  esac
done
ARGS="$*"

# Create on the fly .env file to pass args into plugin container
if [ -n "$ARGS" ];  then
    tmpfile=$(mktemp)
    echo "Generating .env"
    echo 'ARGS=${ARGS}' > $tmpfile
    ENV_FILE=$tmpfile
fi 

docker-compose --env-file $ENV_FILE up

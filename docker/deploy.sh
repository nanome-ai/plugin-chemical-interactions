#!/bin/bash

parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "$parent_path"

# TODO: Forward all args into plugin.
docker-compose --env-file ../.env up

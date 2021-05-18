#!/bin/bash

if [ -n "$(docker ps -aqf name=nanome-chemical-interactions)" ]; then
    echo "removing exited container"
    docker rm -f nanome-chemical-interactions
fi

docker-compose --env-file docker/.env.local up
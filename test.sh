#!/bin/bash

status_code=$(curl -s -o /dev/null -w "%{http_code}" https://pypi.org/project/nanome/0.231312414.2/)
echo $status_code
if [[ "200" != "$status_code" ]];
then
  echo "$status_code" "nanome-lib ${{ github.event.inputs.version_number }} not found"
  exit 1
fi

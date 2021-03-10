$volumeID = docker ps -aqf name=nanome-chemical-interactions
if ($volumeID -ne "") {
    Write-Host "Removing previous container"

    docker stop -t0 nanome-chemical-interactions
    docker rm -f nanome-chemical-interactions
}

docker run -d --memory=10g --name nanome-chemical-interactions --restart unless-stopped $mounts -e ARGS="$args" nanome-chemical-interactions
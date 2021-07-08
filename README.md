# Nanome - Chemical Interactions

A plugin to display various types of interatomic contacts between small- and macromolecules

### Preparation

First thing you need to do is create a `.env` file in the top-level directory containing NTS connection information

```
NTS_HOST=nts-foobar.example.com
NTS_PORT=5555
``` 

And then running the plugin is as simple as
```sh
docker-compose build
docker-compose --env-file .env up
```
The default `docker-compose.yaml` is optimized for development, with debug enabled and the code mounted as volumes. For a deployment, we recommend you use `-f docker-compose-prod.yaml`. We've provided a standalone script as a convenience
```sh
./docker/deploy.sh
```


### Dependencies
The host must support `docker` and `docker-compose`. All other dependencies are handled within the individual docker containers.

### Architecture
The Plugin is broken into two separate containers.
- **plugin**: Runs the Nanome Plugin Instance.
  - Handles all interactions with Nanome application
  - Renders menus
  - Submits data to arpeggio-services
  - Visualizes interactions data in VR.
- **arpeggio-services**:
  - Wrapper API for Arpeggio library, which calculates interactions between molecules.
  - Cleans data to be compatible with interactions command
  - Returns a zip file of interaction results, which is consumed by chem_interactions.


### License

MIT

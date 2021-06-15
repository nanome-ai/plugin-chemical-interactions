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

### Dependencies
The host must support docker and docker-compose. All other dependencies are handled within the individual docker containers.

### Architecture
The Plugin is broken into two separate containers.
- **chem_interactions**: Runs the Nanome Plugin Instance.
  - Handles all interactions with Nanome application
  - Renders menus
  - Submits data to arpeggio-services, and visualizes results in VR.
- **arpeggio-services**:
  - Wrapper API for Arpeggio library, which calculates interactions between molecules.
  - Returns a zip file of interaction results, which is consumed by chem_interactions.

### Development

To run Chemical Interactions with autoreload:

```sh
$ python3 run.py -r -a <plugin_server_address> [optional args]
```

### License

MIT

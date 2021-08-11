# Nanome - Chemical Interactions

A Nanome plugin to Calculate and visualize interatomic contacts between small and macro molecules.


## Dependencies
The host machine must support `docker` and `docker-compose`. All other dependencies are handled within the individual containers.


## Deployments

To start the plugin with production settings, we have a script available at `./docker/deploy.sh`


There's two methods of configuring your plugin.

### 1) Command Line args.
All Nanome plugins can be configured using the following set of command line args.
```sh
user@localhost:~/plugin-chemical-interactions$ python chem_interactions/run.py --help
usage: run.py [-h] [-a HOST] [-p PORT] [-r] [-v] [-n NAME [NAME ...]]
              [-k KEYFILE] [-i IGNORE]

Parse Arguments to set up Nanome Plugin

optional arguments:
  -h, --help            show this help message and exit
  -a HOST, --host HOST  connects to NTS at the specified url or IP address
  -p PORT, --port PORT  connects to NTS at the specified port
  -r, --auto-reload     Restart plugin automatically if a .py or .json file in
                        current directory changes
  -v, --verbose         enable verbose mode, to display Logs.debug
  -n NAME [NAME ...], --name NAME [NAME ...]
                        Name to display for this plugin in Nanome
  -k KEYFILE, --keyfile KEYFILE
                        Specifies a key file or key string to use to connect
                        to NTS
  -i IGNORE, --ignore IGNORE
                        To use with auto-reload. All paths matching this
                        pattern will be ignored, use commas to specify
                        several. Supports */?/[seq]/[!seq]
```
All of these args can be passed to `docker/deploy.sh`, and will be passed to the `plugin` container to connect your plugin to the correct NTS.

For example
`./docker/deploy.sh -a nts-foobar.example.com -p 5555`

When `./docker/deploy.sh` is run, the command is copied into `docker/redeploy.sh` which can be used to redeploy your application without remembering the provided flags.


### 2) Using a .env file
Alternatively, the chemical-interactions plugin supports storing NTS credentials in a `.env` file. This provides less flexibility, and if your environment requires a keyfile, that is not yet supported


First thing you need to do is create a `.env` file in the top-level directory containing NTS connection information
```
NTS_HOST=nts-foobar.example.com
NTS_PORT=5555
``` 

And then running the plugin is as simple as
```sh
./docker/deploy.sh
```

## Architecture
The Plugin is broken into two separate containers.
- **plugin**: Runs the Nanome Plugin Instance.
  - Handles all interactions with Nanome application
  - Renders menus
  - Submits data to arpeggio-services
  - Visualizes interactions data in VR.
- **arpeggio-services**:
  - Wrapper API for Arpeggio library, which calculates interactions between molecules.
  - Cleans data to be compatible with interactions command
  - Returns JSON containing interaction results, which is consumed by chem_interactions.
  - See https://github.com/PDBeurope/arpeggio


##  Development
`docker-compose.yml` is optimized for development, with debug enabled and the code mounted as volumes. If you use the VSCode IDE, we provide tasks and launch configurations to ease development.

### How to get a VScode debugger in your Plugin instance.
1. In your workspace, Open the command pallete, Select `Task: Run Task`, and choose `[wip] plugin container`
2. Open the command pallete again, Select `Remote Containers: Attach to a running Container`, and select the one containing your plugin. VScode should open a new window attached to your container.
3. Click the "Run and Debug" button on the left, and select "run.py" from the dropdown on top. You may need to update the args field in `launch.json` to match your NTS settings.
4. Press play, and VScode should start your plugin in debug mode, and will allow you to set breakpoints as needed


### License
MIT

### References
Harry C Jubb, Alicia P Higueruelo, Bernardo Ochoa-Montaño, Will R Pitt, David B Ascher, Tom L Blundell,
[Arpeggio: A Web Server for Calculating and Visualising Interatomic Interactions in Protein Structures](https://doi.org/10.1016/j.jmb.2016.12.004). Journal of Molecular Biology, Volume 429, Issue 3, 2017, Pages 365-371, ISSN 0022-2836,

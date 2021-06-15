# Nanome - Chemical Interactions

A plugin to display various types of interatomic contacts between small- and macromolecules

### Preparation

First thing you need to do is create a `.env` file in the toplevel directory containing NTS connection information

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
The host must support docker and docker-compose

### Architecture



### Usage

To start Chemical Interactions:

```sh
$ nanome-chemical-interactions -a <plugin_server_address> [optional args]
```

#### Optional arguments:

- `-x arg`

  Example argument documentation

**TODO**: Add any optional argument documentation here, or remove section entirely.


### Development

To run Chemical Interactions with autoreload:

```sh
$ python3 run.py -r -a <plugin_server_address> [optional args]
```

### License

MIT

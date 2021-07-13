import argparse
import os
import nanome
import ChemicalInteractions
from nanome.util.enums import Integrations


def create_parser():
    """Create command line parser For Plugin.

    Some of these flags are passed down into the Plugin, and processed internally.
    rtype: argsparser: args parser
    """
    parser = argparse.ArgumentParser(description='Parse Flags')
    parser.add_argument('-a', '--host', help='connects to NTS at the specified IP address')
    parser.add_argument('-p', '--port', help='connects to NTS at the specified port')
    parser.add_argument('-r', '--auto-reload', action='store_true', help='Restart plugin automatically if a .py or .json file in current directory changes')
    parser.add_argument('-v', '--verbose', action='store_true', help='enable verbose mode, to display Logs.debug')
    parser.add_argument('-n', '--name', default='', help='Name to display for this plugin in Nanome')
    parser.add_argument('-k', '--keyfile', help='Specifies a key file or key string to use to connect to NTS')
    parser.add_argument('-i', '--ignore', help='To use with auto-reload. All paths matching this pattern will be ignored, use commas to specify several. Supports */?/[seq]/[!seq]')
    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()

    default_title = 'Chemical Interactions'
    title = args.name or default_title

    description = (
        'A plugin to display various types of interatomic contacts '
        'between small and macro molecules'
    )
    category = 'Interactions'
    advanced_settings = False

    integrations = [Integrations.interactions]
    plugin = nanome.Plugin(
        title, description, category, advanced_settings, integrations=integrations)

    plugin.set_plugin_class(ChemicalInteractions.ChemicalInteractions)

    # CLI Args take priority over environment variables for NTS settnigs
    host = args.host or os.environ.get('NTS_HOST')
    port = args.port or os.environ.get('NTS_PORT') or 0

    configs = {
        'host': host,
        'port': int(port) if port else None
    }
    items = list(configs.items())
    for key, value in items:
        configs.pop(key) if not value else None
    plugin.run(**configs)


if __name__ == '__main__':
    main()

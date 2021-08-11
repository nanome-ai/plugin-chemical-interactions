import argparse
import os
import nanome
from ChemicalInteractions import ChemicalInteractions
from nanome.util.enums import Integrations


def create_parser():
    """Create command line parser For Plugin.

    This is a subset of the full parser used by Plugins.
    These are the args we want to intercept them and potentially override.
    rtype: argsparser: args parser
    """
    parser = argparse.ArgumentParser(description='Parse Arguments to set up Nanome Plugin')
    parser.add_argument('-a', '--host', help='connects to NTS at the specified IP address')
    parser.add_argument('-p', '--port', help='connects to NTS at the specified port')
    parser.add_argument('-n', '--name', nargs='+', help='Name to display for this plugin in Nanome')
    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()

    default_title = 'Chemical Interactions'
    arg_name = args.name or []
    plugin_name = ' '.join(arg_name) or default_title

    description = 'Calculate and visualize interatomic contacts between small and macro molecules.'
    tags = ['Interactions']

    integrations = [Integrations.interactions]
    plugin = nanome.Plugin(plugin_name, description, tags, integrations=integrations)
    plugin.set_plugin_class(ChemicalInteractions)

    # CLI Args take priority over environment variables for NTS settnigs
    host = args.host or os.environ.get('NTS_HOST')
    port = args.port or os.environ.get('NTS_PORT') or 0

    configs = {}
    if host:
        configs['host'] = host
    if port:
        configs['port'] = int(port)
    plugin.run(**configs)


if __name__ == '__main__':
    main()

import nanome
from plugin.ChemicalInteractions import ChemicalInteractions
from nanome.util.enums import Integrations
from plugin import __version__


def main():
    parser = nanome.Plugin.create_parser()
    args, _ = parser.parse_known_args()

    default_title = 'Chemical Interactions'
    arg_name = args.name or []
    plugin_name = ' '.join(arg_name) or default_title

    description = 'Calculate and visualize chemical interactions made between proteins and small molecules or other proteins'
    tags = ['Interactions']

    integrations = [Integrations.interactions]
    plugin = nanome.Plugin(plugin_name, description, tags, integrations=integrations, has_advanced=True, version=__version__)
    plugin.set_plugin_class(ChemicalInteractions)
    plugin.run()


if __name__ == '__main__':
    main()

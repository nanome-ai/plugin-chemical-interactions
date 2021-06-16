import os
import nanome
import ChemicalInteractions
from nanome.util.enums import Integrations

def main():
    title = 'Chemical Interactions'
    description = (
        'A plugin to display various types of interatomic contacts '
        'between small and macro molecules'
    )
    category = 'Interactions'
    advanced_settings = False

    # temporary hack until nanome-lib 1.22 release
    try:
        integrations = [Integrations.interactions]
    except AttributeError:
        integrations = []

    plugin = nanome.Plugin(
        title, description, category, advanced_settings, integrations=integrations)

    plugin.set_plugin_class(ChemicalInteractions.ChemicalInteractions)

    host = os.environ.get('NTS_HOST')
    port = os.environ.get('NTS_PORT') or 0
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

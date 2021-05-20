import os
import nanome
from .ChemicalInteractions import ChemicalInteractions


def main():
    title = 'Chemical Interactions'
    description = (
        'A plugin to display various types of interatomic contacts '
        'between small and macro molecules'
    )
    category = 'Analysis'
    advanced_settings = False
    plugin = nanome.Plugin(title, description, category, advanced_settings)
    plugin.set_plugin_class(ChemicalInteractions)

    host = os.environ.get('NTS_HOST')
    port = os.environ.get('NTS_PORT') or 0
    configs = {
        'host': host,
        'port': int(port) if port else None
    }
    [configs.pop(key) for key, value in configs.items() if not value]
    plugin.run(**configs)


if __name__ == '__main__':
    main()

import nanome
from nanome.util import Logs

class ChemicalInteractions(nanome.PluginInstance):
    def start(self):
        menu = self.menu
        menu.title = 'Chemical Interactions'
        menu.width = 1
        menu.height = 1

        node = menu.root.create_child_node()
        node.add_new_label('hello, nanome!')

    def on_run(self):
        self.menu.enabled = True
        self.update_menu(self.menu)

def main():
    plugin = nanome.Plugin('Chemical Interactions', 'A plugin to display various types of interatomic contacts between small- and macromolecules', 'other', False)
    plugin.set_plugin_class(ChemicalInteractions)
    plugin.run()

if __name__ == '__main__':
    main()

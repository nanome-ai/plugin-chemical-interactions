from functools import partial
import nanome
from nanome.util import Logs
from os import path
import requests
import tempfile

PDBOPTIONS = nanome.api.structure.Complex.io.PDBSaveOptions()
PDBOPTIONS.write_bonds = True

class ChemicalInteractions(nanome.PluginInstance):
    def start(self):
        menu = self.menu
        menu.title = 'Chemical Interactions'
        menu.width = 1
        menu.height = 1

        self.temp_dir = tempfile.TemporaryDirectory()

        self.ls_complexes = menu.root.create_child_node().add_new_list()
        self.complexes = set()

        self.btn_submit = menu.root.create_child_node().add_new_button('Calculate Interactions')
        self.btn_submit.register_pressed_callback(partial(self.get_complexes, self.get_interactions))

        self.image = 'harryjubb/arpeggio:latest'
        self.flags = r'-v "{{files}}":/run -u `id -u`:`id -g`'
        self.command = 'python arpeggio.py /run/1XKK.pdb -s RESNAME:FMM -v'

        self.request_complex_list(self.display_complexes)

    def on_run(self):
        self.menu.enabled = True
        self.update_menu(self.menu)

    def toggle_complex(self, btn_complex):
        btn_complex.selected = not btn_complex.selected
        if btn_complex.selected:
            self.complexes.add(btn_complex.complex_index)
        else:
            self.complexes.discard(btn_complex.complex_index)
        self.update_content(btn_complex)

    def display_complexes(complexes):
        complex_nodes = []
        for complex in complexes:
            ln_complex = nanome.ui.LayoutNode()
            btn_complex = ln_complex.add_new_button(complex.name)
            btn_complex.complex_index = complex.index
            btn_complex.register_pressed_callback(self.toggle_complex)
            complex_nodes.append(ln_complex)
    
    def get_complexes(self, callback):
        self.request_complexes([item.get_content().complex_index for item in self.ls_complexes.items], callback)

    def get_interactions(self, complexes):
        data = {'flags': self.flags, 'image': self.image, 'command': self.command}
        files = {}
        for complex in complexes:
            complex_path = path.join(self.temp_dir.name, complex.name)
            complex.io.to_pdb(complex_path, PDBOPTIONS)
            files[f'{complex.name}.pdb'] = complex_path
        res = requests.post('http://localhost:80/', data=data, files=files)
        interactions = [''.join([str(chr(c)) for c in res['data']['files'][f'{complex.name}.sift']['data']]) for complex in complexes]
        Logs.debug(interactions)

def main():
    plugin = nanome.Plugin('Chemical Interactions', 'A plugin to display various types of interatomic contacts between small- and macromolecules', 'other', False)
    plugin.set_plugin_class(ChemicalInteractions)
    plugin.run()

if __name__ == '__main__':
    main()

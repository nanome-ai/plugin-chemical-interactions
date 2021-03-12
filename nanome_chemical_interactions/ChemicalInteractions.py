from functools import partial
import nanome
from nanome.util import Logs
from os import path
import re
import requests
import tempfile

PDBOPTIONS = nanome.api.structure.Complex.io.PDBSaveOptions()
PDBOPTIONS.write_bonds = True

IMAGE = 'dockerfile'
FLAGS = r'-v "{{files}}":/run -u `id -u`:`id -g`'

f = open(path.join(path.dirname(__file__), 'Dockerfile'), 'r')
requests.post('http://localhost:80/init', data={'dockerfile': f.read()})
f.close()

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

        self.command_template = 'python arpeggio.py /run/{{complex}}.pdb -s RESNAME:{{residue}} -v'

        self.interaction_types = [
        'clash',
        'covalent',
        'vdw_clash',
        'vdw',
        'proximal',
        'hbond',
        'weak_hbond',
        'xbond',
        'ionic',
        'metal_complex',
        'aromatic',
        'hydrophobic',
        'carbonyl',
        'polar',
        'weak_polar',
        'interacting_entities',
        ]

    def on_run(self):
        self.menu.enabled = True
        self.update_menu(self.menu)
        self.request_complex_list(self.display_complexes)

    def toggle_complex(self, btn_complex):
        for item in (set(self.ls_complexes.items) - {btn_complex.ln}):
            item.get_content().selected = False
        btn_complex.selected = not btn_complex.selected
        if btn_complex.selected:
            self.complexes.add(btn_complex.complex_index)
        else:
            self.complexes.discard(btn_complex.complex_index)
        self.update_content(self.ls_complexes)

    def display_complexes(self, complexes):
        self.ls_complexes.items = []
        for complex in complexes:
            ln_complex = nanome.ui.LayoutNode()
            btn_complex = ln_complex.add_new_button(complex.name)
            btn_complex.complex_index = complex.index
            btn_complex.ln = ln_complex
            btn_complex.register_pressed_callback(self.toggle_complex)
            self.ls_complexes.items.append(ln_complex)
        self.update_content(self.ls_complexes)
    
    def get_complexes(self, callback, btn=None):
        self.request_complexes([item.get_content().complex_index for item in self.ls_complexes.items], callback)

    def get_interactions(self, complexes):
        complex = complexes[0]
        
        # adjust the docker command for the chosen complex and residue
        command = self.command_template.replace('{{complex}}', complex.name).replace('{{residue}}', 'FMM')
        data = {'flags': FLAGS, 'image': IMAGE, 'command': command}

        # write the chosen complex to file
        pdb_path = path.join(self.temp_dir.name, complex.name)
        complex.io.to_pdb(pdb_path, PDBOPTIONS)
        with open(pdb_path, 'r') as pdb_stream:
            pdb_contents = pdb_stream.read()
        files = {f'{complex.name}.pdb': pdb_contents}

        # make the request with the command and file
        res = requests.post('http://localhost:80/', data=data, files=files)
        interaction_data = ''.join([str(chr(c)) for c in res.json()['data']['files'][f'{complex.name}.contacts']['data']])
        self.parse_data(interaction_data, complex)

    def parse_data(self, interaction_data, complex):
        residues = {residue.serial: residue for residue in complex.residues}
        # cplx/res/atm/itrns:c     r      a        i
        interactions = {}
        for m in re.finditer(r'(\w+)/(\d+)/([\w\d]+)\t(\w+)/(\d+)/([\w\d]+)([\t01]+)', interaction_data):
            # add interaction terms to atoms by residue
            _, r1, a1, _, r2, a2, i = m.groups()
            terms = list(filter(lambda e: e is not '', i.split('\t')))
            atom1 = [atom for atom in residues[int(r1)].atoms if atom.name == a1].pop()
            atom2 = [atom for atom in residues[int(r2)].atoms if atom.name == a2].pop()
            # create interactions
        Logs.debug(interactions)

def main():
    plugin = nanome.Plugin('Chemical Interactions', 'A plugin to display various types of interatomic contacts between small- and macromolecules', 'other', False)
    plugin.set_plugin_class(ChemicalInteractions)
    plugin.run()

if __name__ == '__main__':
    main()

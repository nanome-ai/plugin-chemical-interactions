from functools import partial
import os
from os import path
import re
# from Bio import PDB
import requests
import tempfile

import nanome
from nanome.api.shapes import Line
from nanome.util import Logs
from nanome.util.enums import NotificationTypes
from utils.common import ligands

BASE_PATH = path.dirname(path.realpath(__file__))
MENU_PATH = path.join(BASE_PATH, 'menus', 'json', 'menu.json')

PDBOPTIONS = nanome.api.structure.Complex.io.PDBSaveOptions()
PDBOPTIONS.write_bonds = True


class ChemicalInteractions(nanome.PluginInstance):
    def start(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.pdb_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdb", dir=self.temp_dir.name)

        self.index_to_complex = {}
        self.complex_indices = set()
        self.residue = ''

        self.interaction_types = {
            'clash': nanome.util.Color.Red(),
            'covalent': nanome.util.Color.Black(),
            'vdw_clash': nanome.util.Color.from_int(127 << 24 | 0 << 16 | 0 << 8 | 255),
            'vdw': nanome.util.Color.from_int(0 << 24 | 200 << 16 | 20 << 8 | 255),
            'proximal': nanome.util.Color.from_int(0 << 24 | 139 << 16 | 139 << 8 | 255),
            'hbond': nanome.util.Color.Yellow(),
            'weak_hbond': nanome.util.Color.from_int(255 << 24 | 255 << 16 | 224 << 8 | 255),
            'xbond': nanome.util.Color.from_int(151 << 24 | 251 << 16 | 152 << 8 | 255),
            'ionic': nanome.util.Color.from_int(12 << 24 | 0 << 16 | 255 << 8 | 255),
            'metal_complex': nanome.util.Color.from_int(30 << 24 | 30 << 16 | 30 << 8 | 255),
            'aromatic': nanome.util.Color.from_int(63 << 24 | 63 << 16 | 63 << 8 | 255),
            'hydrophobic': nanome.util.Color.from_int(0 << 24 | 0 << 16 | 255 << 8 | 200),
            'carbonyl': nanome.util.Color.from_int(12 << 24 | 12 << 16 | 12 << 8 | 255),
            'polar': nanome.util.Color.Grey(),
            'weak_polar': nanome.util.Color.from_int(0 << 24 | 0 << 16 | 127 << 8 | 255),
        }

        self._menu = nanome.ui.Menu.io.from_json(MENU_PATH)
        self.menu = self._menu
        self.ls_complexes = self._menu.root.find_node('Complex List').get_content()
        self.ls_ligands = self._menu.root.find_node('Ligands List').get_content()
        self.btn_calculate = self._menu.root.find_node('Button').get_content()
        self.btn_calculate.register_pressed_callback(partial(self.get_complexes, self.get_interactions))

    def on_run(self):
        self.menu.enabled = True
        self.update_menu(self.menu)
        self.request_complex_list(self.display_complexes)

    def toggle_complex(self, btn_complex):
        # clear ligand list
        self.ls_ligands.items = []

        # toggle the complex
        btn_complex.selected = not btn_complex.selected

        # deselect everything else
        for item in (set(self.ls_complexes.items) - {btn_complex.ln}):
            item.get_content().selected = False

        # modify state
        if btn_complex.selected:
            self.complex_indices.add(btn_complex.complex_index)
            self.request_complexes([btn_complex.complex_index], self.display_ligands)
        else:
            self.complex_indices.discard(btn_complex.complex_index)

        # update ui
        self.update_content(self.ls_complexes)
        self.update_content(self.ls_ligands)

    def toggle_ligand(self, btn_ligand):
        # toggle the button
        btn_ligand.selected = not btn_ligand.selected

        # deselect everything else
        for ln in set(self.ls_ligands.items) - {btn_ligand.ln}:
            ln.get_content().selected = False

        # modify state
        if btn_ligand.selected:
            self.residue = btn_ligand.ligand
        else:
            self.residue = ''

        # update ui
        self.update_content(self.ls_ligands)

    def display_complexes(self, complexes):
        # clear ui and state
        self.ls_complexes.items = []
        self.ls_ligands.items = []
        self.index_to_complex = {}
        # populate ui and state
        for complex in complexes:
            self.index_to_complex[complex.index] = complex
            ln_complex = nanome.ui.LayoutNode()
            btn_complex = ln_complex.add_new_button(complex.name)
            btn_complex.complex_index = complex.index
            btn_complex.ln = ln_complex
            btn_complex.register_pressed_callback(self.toggle_complex)
            self.ls_complexes.items.append(ln_complex)

        # update ui
        self.update_content(self.ls_complexes)

    def display_ligands(self, complex):
        complex = complex[0]

        # clear ligands list
        self.ls_ligands.items = []

        # update the complex map for the actual request
        self.index_to_complex[complex.index] = complex

        # populate ligand list
        complex.io.to_pdb(self.pdb_file.name, PDBOPTIONS)
        ligs = ligands(self.pdb_file)
        for lig in ligs:
            ln_ligand = nanome.ui.LayoutNode()
            btn_ligand = ln_ligand.add_new_button(lig.resname)
            btn_ligand.ligand = lig
            btn_ligand.ln = ln_ligand
            btn_ligand.register_pressed_callback(self.toggle_ligand)
            self.ls_ligands.items.append(ln_ligand)

        # update ui
        self.update_content(self.ls_ligands)

    def get_complexes(self, callback, btn=None):
        self.request_complexes([item.get_content().complex_index for item in self.ls_complexes.items], callback)

    def get_interactions(self, complexes):
        selected_complex_indices = [c.get_content().complex_index for c in self.ls_complexes.items if c.get_content().selected]

        # validation
        if len(selected_complex_indices):
            complex = self.index_to_complex.get(selected_complex_indices[0])
        else:
            self.send_notification(nanome.util.enums.NotificationTypes.error, "Please select a complex")
            return

        if not self.residue:
            self.send_notification(nanome.util.enums.NotificationTypes.error, "Please select a ligand")
            return

        # create the request files
        pdb_path = path.join(self.temp_dir.name, complex.name)
        complex.io.to_pdb(pdb_path, PDBOPTIONS)
        with open(pdb_path, 'r') as pdb_stream:
            pdb_contents = pdb_stream.read()
        files = {'input_file': pdb_contents}

        atom_path_list = []
        chain_name = self.residue.parent.id
        residue_number = self.residue.id[1]
        for atom in self.residue.get_atoms():
            atom_name = atom.fullname.strip()
            atom_path = f'{chain_name}/{residue_number}/{atom_name}'
            atom_path_list.append(atom_path)

        data = {
            'atom_paths': ','.join(atom_path_list)
        }

        # make the request with the data and file
        interactions_url = os.environ['INTERACTIONS_URL']
        res = requests.post(interactions_url, data=data, files=files)

        if not res.status_code == 200:
            self.send_notification(NotificationTypes.error, 'Error =(')
            return

        self.send_notification(nanome.util.enums.NotificationTypes.message, "Interaction data retrieved!")
        # interaction_data = ''.join([str(chr(c)) for c in res.json()['data']['files'][f'{complex.name}.contacts']['data']])
        # self.parse_and_upload(interaction_data, complex)

    def parse_and_upload(self, interaction_data, complex):
        residues = {residue.serial: residue for residue in complex.residues}
        interactions = {}
        # cplx/res/atm/intrxions:c1    r1     a1        c2    r2     a2        i
        for m in re.finditer(r'(\w+)/(\d+)/([\w\d]+)\t(\w+)/(\d+)/([\w\d]+)([\t01]+)', interaction_data):
            # add interaction terms to atoms by residue
            _, r1, a1, _, r2, a2, i = m.groups()
            terms = list(filter(lambda e: e != '', i.split('\t')))
            atom1 = [atom for atom in residues[int(r1)].atoms if atom.name == a1].pop()
            atom2 = [atom for atom in residues[int(r2)].atoms if atom.name == a2].pop()
            # create interactions (lines)
            line = Line()
            colors = [k for i, k in enumerate(self.interaction_types.keys()) if terms[i] == '1']
            line.color = self.interaction_types[colors[0]]
            line.thickness = 0.1
            line.dash_length = 0.25
            line.dash_distance = 0.25
            line.anchors[0].anchor_type = line.anchors[1].anchor_type = nanome.util.enums.ShapeAnchorType.Atom
            line.anchors[0].target, line.anchors[1].target = atom1.index, atom2.index
            line.upload()
        Logs.debug(interactions)


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



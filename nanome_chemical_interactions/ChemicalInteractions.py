from functools import partial
from os import environ, path
import csv
import requests
import tempfile
import shutil

import nanome
from nanome.api.structure import Complex
from nanome.api.shapes import Line
from nanome.util.enums import NotificationTypes
from nanome.util import async_callback
from utils.common import ligands
from forms import ChemicalInteractionsForm


BASE_PATH = path.dirname(path.realpath(__file__))
MENU_PATH = path.join(BASE_PATH, 'menus', 'json', 'menu.json')

PDBOPTIONS = Complex.io.PDBSaveOptions()
PDBOPTIONS.write_bonds = True


class ChemicalInteractions(nanome.AsyncPluginInstance):

    def start(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.pdb_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdb", dir=self.temp_dir.name)

        self.interactions_url = environ.get('INTERACTIONS_URL')

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

    @async_callback
    async def on_run(self):
        self.menu.enabled = True
        self.update_menu(self.menu)
        complexes = await self.request_complex_list()
        self.display_complexes(complexes)

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

    def clean_complex(self, complex):
        """Clean complex to prep for arpeggio."""
        pdb_path = path.join(self.temp_dir.name, complex.name)
        complex.io.to_pdb(pdb_path, PDBOPTIONS)
        with open(pdb_path, 'r') as pdb_stream:
            pdb_contents = pdb_stream.read()

        files = {'input_file.pdb': pdb_contents}
        clean_url = f'{self.interactions_url}/clean'
        response = requests.post(clean_url, files=files)

        cleaned_file = tempfile.NamedTemporaryFile(suffix='.pdb')
        with open(cleaned_file.name, 'wb') as f:
            f.write(response.content)
        return cleaned_file

    def get_interactions(self, complexes):
        
        complex_indices = [c.get_content().complex_index for c in self.ls_complexes.items]
        selected_complex_indices = [c.get_content().complex_index for c in self.ls_complexes.items if c.get_content().selected]
        residue_index = self.residue.id[1]
        data = {
            "complexes": selected_complex_indices,
            "residue": residue_index
        }
        form = ChemicalInteractionsForm(data=data, complex_choices=complex_indices)
        form.validate()
        if form.errors:
            self.send_notification(nanome.util.enums.NotificationTypes.error, form.errors.items())
        else:
            form.submit()

        cleaned_file = self.clean_complex(complex)
        # Get equivalent residue to selected residue in cleaned complex
        clean_residue = next(iter(ligands(cleaned_file)))

        atom_path_list = []
        chain_name = self.residue.parent.id
        residue_number = clean_residue.id[1]
        for atom in clean_residue.get_atoms():
            atom_name = atom.fullname.strip()
            atom_path = f'/{chain_name}/{residue_number}/{atom_name}'
            atom_path_list.append(atom_path)

        cleaned_data = ''
        with open(cleaned_file.name, 'r') as f:
            cleaned_data = f.read()

        # create the request files
        files = {'input_file.pdb': cleaned_data}
        data = {
            # 'atom_paths': ','.join(atom_path_list)
        }

        # make the request with the data and file
        response = requests.post(self.interactions_url, data=data, files=files)

        if not response.status_code == 200:
            self.send_notification(NotificationTypes.error, 'Error =(')
            return

        self.send_notification(nanome.util.enums.NotificationTypes.message, "Interaction data retrieved!")

        zipfile = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        with open(zipfile.name, 'wb') as f:
            f.write(response.content)

        # Unpack the archive file
        extract_dir = tempfile.mkdtemp()
        archive_format = "zip"
        shutil.unpack_archive(zipfile.name, extract_dir, archive_format)
        contacts_file = f'{extract_dir}/input_file.contacts'
        self.parse_and_upload(contacts_file, complex)

    @staticmethod
    def get_atom(complex, atom_path):
        """Return atom corresponding to atom path"""
        chain_name, res_id, atom_name = atom_path.split('/')
        chain = next(iter([chain for chain in complex.chains if chain.name == chain_name]))
        residue = next(iter([rez for rez in chain.residues if str(rez.serial) == res_id]))
        atom = next(iter([at for at in residue.atoms if at.name == atom_name]))
        return atom

    def parse_and_upload(self, interactions_file, complex):
        # Enumerate columns denoting each type of interaction
        interaction_data = []
        with open(interactions_file, 'r') as f:
            reader = csv.reader(f, delimiter="\t")
            for row in reader:
                interaction_data.append(row)

        interaction_type_index = {
            'clash': 2,
            'covalent': 3,
            'vdw_clash': 4,
            'vdw': 5,
            'proximal': 6,
            'hbond': 7,
            'weak_hbond': 8,
            'xbond': 9,
            'ionic': 10,
            'metal_complex': 11,
            'aromatic': 12,
            'hydrophobic': 13,
            'carbonyl': 14,
            'polar': 15,
            'weak_polar': 16,
        }
        for row in interaction_data:
            # Use atom paths to get matching atoms on Nanome Structure
            a1 = row[0]
            a2 = row[1]
            try:
                atom1 = self.get_atom(complex, a1)
            except Exception:
                print(f'invalid atom path {a1}')
                continue
            try:
                atom2 = self.get_atom(complex, a2)
            except Exception:
                print(f'invalid atom path {a2}')
                continue

            # create interactions (lines)
            # Iterate through columns and draw relevant lines
            for i, col in enumerate(row[2:], 2):
                if col == '1':
                    line = Line()
                    interaction_type = next(iter([key for key, val in interaction_type_index.items() if val == i]))
                    color = self.interaction_types[interaction_type]
                    line.color = color
                    line.thickness = 0.1
                    line.dash_length = 0.25
                    line.dash_distance = 0.25
                    line.anchors[0].anchor_type = line.anchors[1].anchor_type = nanome.util.enums.ShapeAnchorType.Atom
                    line.anchors[0].target, line.anchors[1].target = atom1.index, atom2.index
                    line.upload()
        self.send_notification(nanome.util.enums.NotificationTypes.message, "Finished Calculating Interactions!")

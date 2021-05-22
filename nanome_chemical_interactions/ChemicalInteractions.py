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
from menus import ChemInteractionsMenu

BASE_PATH = path.dirname(path.realpath(__file__))
MENU_PATH = path.join(BASE_PATH, 'menus', 'json', 'menu.json')

PDBOPTIONS = Complex.io.PDBSaveOptions()
PDBOPTIONS.write_bonds = True


class ChemicalInteractions(nanome.AsyncPluginInstance):

    def start(self):
        self.index_to_complex = {}
        self.residue = ''
        self.interactions_url = environ.get('INTERACTIONS_URL')

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

        self.menu = ChemInteractionsMenu(self, MENU_PATH)

    @async_callback
    async def on_run(self):
        self.menu.enabled = True
        self.update_menu(self.menu._menu)
        complexes = await self.request_complex_list()
        self.menu.display_complexes(complexes)

    def clean_complex(self, complex):
        """Clean complex to prep for arpeggio."""
        temp_file = tempfile.NamedTemporaryFile()
        complex.io.to_pdb(temp_file.name, PDBOPTIONS)
        with open(temp_file.name, 'r') as pdb_stream:
            pdb_contents = pdb_stream.read()

        files = {'input_file.pdb': pdb_contents}
        clean_url = f'{self.interactions_url}/clean'
        response = requests.post(clean_url, files=files)

        cleaned_file = tempfile.NamedTemporaryFile(suffix='.pdb')
        with open(cleaned_file.name, 'wb') as f:
            f.write(response.content)
        return cleaned_file

    def generate_atom_path_list(self, residue):
        # Use biopython version of residue to create atom_paths
        atom_path_list = []
        chain_name = residue.parent.id
        residue_number = residue.id[1]
        for atom in residue.get_atoms():
            atom_name = atom.fullname.strip()
            atom_path = f'/{chain_name}/{residue_number}/{atom_name}'
            atom_path_list.append(atom_path)
        return atom_path_list

    def get_interactions(self, complexes):
        # Starting with assumption of one comp.
        comp = next(iter(complexes))

        # Clean complex and return as TempFile
        cleaned_file = self.clean_complex(comp)
        clean_residue = next(iter(ligands(cleaned_file)))
        atom_paths = self.generate_atom_path_list(clean_residue)

        cleaned_data = ''
        with open(cleaned_file.name, 'r') as f:
            cleaned_data = f.read()

        # create the request files
        files = {'input_file.pdb': cleaned_data}
        data = {
            # 'atom_paths': ','.join(atom_paths)
        }

        form = ChemicalInteractionsForm(data=data)
        form.validate()
        if form.errors:
            self.send_notification(nanome.util.enums.NotificationTypes.error, form.errors.items())
            return

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
        self.parse_and_upload(contacts_file, comp)

    @staticmethod
    def get_atom(complex, atom_path):
        """Return atom corresponding to atom path"""
        chain_name, res_id, atom_name = atom_path.split('/')
        chain = next(iter([chain for chain in complex.chains if chain.name == chain_name]))
        residue = next(iter([rez for rez in chain.residues if str(rez.serial) == res_id]))
        atom = next(iter([at for at in residue.atoms if at.name == atom_name]))
        return atom

    def parse_and_upload(self, interactions_file, complex):
        # Get atoms corresponding to selected ligand
        # hetchains = [
        #     chain for chain in complex.chains
        #     if any([a for a in chain.atoms if a.is_het])
        # ]

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

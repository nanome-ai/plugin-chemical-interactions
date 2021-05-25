from os import environ, path
import csv
import requests
import tempfile
import shutil
import asyncio

import nanome
from nanome.api.structure import Complex
from nanome.api.shapes import Line
from nanome.util.enums import NotificationTypes
from nanome.util import async_callback
from forms import ChemicalInteractionsForm
from menus.forms import InteractionsForm
from menus import ChemInteractionsMenu

BASE_PATH = path.dirname(path.realpath(__file__))
PDBOPTIONS = Complex.io.PDBSaveOptions()
PDBOPTIONS.write_bonds = True


class ChemicalInteractions(nanome.AsyncPluginInstance):

    def start(self):
        self.index_to_complex = {}
        self.residue = ''
        self.interactions_url = environ.get('INTERACTIONS_URL')
        self.menu = ChemInteractionsMenu(self)
        self._interaction_lines = []

    @async_callback
    async def on_run(self):
        self.menu.enabled = True
        complexes = await self.request_complex_list()
        self.menu.display_complexes(complexes)
        self.update_menu(self.menu._menu)

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

    @async_callback
    async def get_interactions(self, complex_indices, interaction_data):
        """Collect Form data, and render Interactions in nanome.

        complexes: List of indices
        interactions data: Data accepted by InteractionsForm.
        """
        # Starting with assumption of one complex.
        complexes = await self.request_complexes(complex_indices)
        comp = complexes[0]

        # Clean complex and return as TempFile
        cleaned_file = self.clean_complex(comp)
        # clean_residue = next(iter(ligands(cleaned_file)))
        # atom_paths = self.generate_atom_path_list(clean_residue)

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
        if response.status_code != 200:
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

        self.parse_and_upload(contacts_file, comp, interaction_data)

    @staticmethod
    def get_atom(complex, atom_path):
        """Return atom corresponding to atom path"""
        # hetchains = [
        #     chain for chain in complex.chains
        #     if any([a for a in chain.atoms if a.is_het])
        # ]
        chain_name, res_id, atom_name = atom_path.split('/')
        # for ch in hetchains:
        #     if ch.name.startswith('H'):
        #         ch.name = ch.name[1:]
        chain = next(chain for chain in complex.chains if chain.name == chain_name)
        residue = next(rez for rez in chain.residues if str(rez.serial) == res_id)
        atom = next(at for at in residue.atoms if at.name == atom_name)
        return atom

    def parse_and_upload(self, interactions_file, complex, color_data):
        # Get atoms corresponding to selected ligand
        # Enumerate columns denoting each type of interaction
        interaction_data = []
        with open(interactions_file, 'r') as f:
            reader = csv.reader(f, delimiter="\t")
            for row in reader:
                interaction_data.append(row)

        # Represents the order of the interaction columns in the .contacts file

        interaction_column_index = {
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

        form = InteractionsForm(data=color_data)
        form.validate()

        valid_atom_paths = set()
        invalid_atom_paths = set()
        for i, row in enumerate(interaction_data):
            print(f"row {i}")
            # Use atom paths to get matching atoms on Nanome Structure
            a1 = row[0]
            a2 = row[1]
            try:
                atom1 = self.get_atom(complex, a1)
            except Exception:
                invalid_atom_paths.add(a1)
                continue
            else:
                valid_atom_paths.add(a1)

            try:
                atom2 = self.get_atom(complex, a2)
            except Exception:
                invalid_atom_paths.add(a2)
                continue
            else:
                valid_atom_paths.add(a2)

            # create interactions (lines)
            # Iterate through columns and draw relevant lines
            for i, col in enumerate(row[2:], 2):
                if col == '1':
                    interaction_type = next(
                        key for key, val in interaction_column_index.items() if val == i)
                    form_data = form.data[interaction_type]
                    line = self.draw_interaction_line(atom1, atom2, form_data)
                    self._interaction_lines.append(line)

                    async def upload(line):
                        line.upload()
                    asyncio.create_task(upload(line))

        # TODO: Send this notification after all async tasks are completed.
        async def send_notification(plugin):
            plugin.send_notification(nanome.util.enums.NotificationTypes.message, "Finished Calculating Interactions!")
        asyncio.create_task(send_notification(self))

    def draw_interaction_line(self, atom1, atom2, form_data):
        """Draw line connecting two atoms.

        :arg atom1: Atom
        :arg atom2: Atom
        :arg form_data: Dict {'color': (r,g,b), 'visible': bool}
        """
        line = Line()
        color = form_data['color']
        color.a = 0 if not form_data['visible'] else 255
        line.color = color
        line.thickness = 0.1
        line.dash_length = 0.25
        line.dash_distance = 0.25
        line.anchors[0].anchor_type = line.anchors[1].anchor_type = nanome.util.enums.ShapeAnchorType.Atom
        line.anchors[0].target, line.anchors[1].target = atom1.index, atom2.index
        return line

    def update_interaction_lines(self, interaction_data):
        for line in self._interaction_lines:
            ...

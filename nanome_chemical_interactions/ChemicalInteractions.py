from os import environ, path
import csv
import requests
import tempfile
import shutil
import asyncio

import nanome
from nanome.api.structure import Complex
from nanome.util.enums import NotificationTypes
from nanome.util import async_callback, Color
from menus.forms import InteractionsForm, LineForm
from menus import ChemInteractionsMenu
from utils import extract_ligands, ComplexUtils

BASE_PATH = path.dirname(path.realpath(__file__))
PDBOPTIONS = Complex.io.PDBSaveOptions()
PDBOPTIONS.write_bonds = True


class ChemicalInteractions(nanome.AsyncPluginInstance):

    def start(self):
        self.residue = ''
        self.interactions_url = environ.get('INTERACTIONS_URL')
        self.menu = ChemInteractionsMenu(self)
        self._interaction_lines = []

    @async_callback
    async def on_run(self):
        self.menu.enabled = True
        complex_list = await self.request_complex_list()
        await self.refresh_menu(complexes=complex_list)

    @async_callback
    async def on_complex_list_updated(self, complex_list):
        await self.refresh_menu(complexes=complex_list)

    async def refresh_menu(self, complexes=None, **kwargs):
        complexes = complexes or []
        await self.menu.render(complexes=complexes)

    @async_callback
    async def on_complex_added(self):
        complexes = await self.request_complex_list()
        self.request_complexes([c.index for c in complexes], self.refresh_menu)

    @async_callback
    async def on_complex_removed(self):
        complexes = await self.request_complex_list()
        self.request_complexes([c.index for c in complexes], self.refresh_menu)

    def clean_complex(self, complex):
        """Clean complex to prep for arpeggio."""
        temp_file = tempfile.NamedTemporaryFile(suffix='.pdb')
        complex.io.to_pdb(temp_file.name, PDBOPTIONS)
        with open(temp_file.name, 'r') as pdb_stream:
            pdb_contents = pdb_stream.read()

        temp_file.name.split('/')
        filename = temp_file.name.split('/')[-1]
        file_data = {filename: pdb_contents}

        clean_url = f'{self.interactions_url}/clean'
        response = requests.post(clean_url, files=file_data)

        cleaned_file = tempfile.NamedTemporaryFile(suffix='.pdb')
        with open(cleaned_file.name, 'wb') as f:
            f.write(response.content)
        return cleaned_file

    @async_callback
    async def get_interactions(self, complexes, selected_residue, residue_complex, interaction_data):
        """Collect Form data, and render Interactions in nanome.

        complexes: List of indices
        interactions data: Data accepted by InteractionsForm.
        """ 
        await asyncio.create_task(self.destroy_lines(self._interaction_lines))
        self._interaction_lines = []

        comp = complexes[0]
        # If residue not part of selected complex, we need to combine the complexes into one pdb
        if residue_complex.index != comp.index:
            comp = ComplexUtils.combine_ligands(comp, [residue_complex], comp)

        # Clean complex and return as TempFile
        cleaned_file = self.clean_complex(comp)
        complex_ligands = extract_ligands(cleaned_file)
        clean_residue = next(lig for lig in complex_ligands if lig.id == selected_residue.id)

        # create the request files
        cleaned_data = ''
        with open(cleaned_file.name, 'r') as f:
            cleaned_data = f.read()
        
        filename = cleaned_file.name.split('/')[-1]
        files = {filename: cleaned_data}

        selection = f'RESNAME:{clean_residue.resname}'
        data = {
            'selection': selection
        }

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

        contacts_filename = f"{''.join(filename.split('.')[:-1])}.contacts"
        contacts_file = f'{extract_dir}/{contacts_filename}'
        self.parse_and_upload(contacts_file, comp, interaction_data)

    @staticmethod
    def get_atom(complex, atom_path):
        """Return atom corresponding to atom path.

        complex: nanome.api.Complex object
        atom_path: str (/C/20/O)
        """
        chain_name, res_id, atom_name = atom_path.split('/')
        nanome_residues = [
            r for r in complex.residues if all([
                str(r._serial) == str(res_id),
                r.chain.name in [chain_name, f'H{chain_name}', f'H_{chain_name}']
            ])
        ]
        if len(nanome_residues) != 1:
            raise Exception
        nanome_residue = nanome_residues[0]
        atoms = [a for a in nanome_residue.atoms if a._name == atom_name]
        if len(atoms) != 1:
            raise Exception
        return atoms[0]

    def parse_and_upload(self, interactions_file, complex, interaction_form):
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
        form = InteractionsForm(data=interaction_form)
        form.validate()
        if form.errors:
            raise Exception

        valid_atom_paths = set()
        invalid_atom_paths = set()
        for i, row in enumerate(interaction_data):
            print(f"row {i}")
            # Use atom paths to get matching atoms on Nanome Structure
            atom_paths = row[:2]
            atom_list = []
            for a in atom_paths:
                try:
                    atom = self.get_atom(complex, a)
                    atom_list.append(atom)
                except Exception:
                    invalid_atom_paths.add(a)
                else:
                    valid_atom_paths.add(a)

            if len(atom_list) != 2:
                continue

            atom1, atom2 = atom_list
            # Iterate through columns and draw relevant lines
            for i, col in enumerate(row[2:], 2):
                if col == '1':
                    interaction_type = next(
                        key for key, val in interaction_column_index.items() if val == i)
                    form_data = form.data.get(interaction_type)
                    if not form_data:
                        continue

                    line = self.draw_interaction_line(atom1, atom2, form_data)
                    line.interaction_type = interaction_type
                    self._interaction_lines.append(line)
                    asyncio.create_task(self.upload_line(line))

        print(valid_atom_paths)
        print(invalid_atom_paths)

        async def send_notification(plugin):
            plugin.send_notification(nanome.util.enums.NotificationTypes.message, "Finished Calculating Interactions!")
        asyncio.create_task(send_notification(self))

    def draw_interaction_line(self, atom1, atom2, form_data):
        """Draw line connecting two atoms.

        :arg atom1: Atom
        :arg atom2: Atom
        :arg form_data: Dict {'color': (r,g,b), 'visible': bool}
        """
        lineform = LineForm(data=form_data)
        line = lineform.create()
        line.anchors[0].anchor_type = line.anchors[1].anchor_type = nanome.util.enums.ShapeAnchorType.Atom
        line.anchors[0].target, line.anchors[1].target = atom1.index, atom2.index
        return line

    @staticmethod
    async def upload_line(line):
        line.upload()

    async def destroy_lines(self, line_list):
        for line in line_list:
            line.destroy()

    def update_interaction_lines(self, interaction_data):
        for line in self._interaction_lines:
            line_type = line.interaction_type
            form_data = interaction_data[line_type]
            line.color = Color(*form_data['color'])
            line.color.a = 0 if not form_data['visible'] else 255
            asyncio.create_task(self.upload_line(line))

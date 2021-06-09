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
from utils import ComplexUtils

BASE_PATH = path.dirname(path.realpath(__file__))
PDBOPTIONS = Complex.io.PDBSaveOptions()
PDBOPTIONS.write_bonds = True


class ChemicalInteractions(nanome.AsyncPluginInstance):

    def start(self):
        self.residue = ''
        self.interactions_url = environ.get('INTERACTIONS_URL')
        self.menu = ChemInteractionsMenu(self)
        self._interaction_lines = []
        # TODO: Make advanced Setting
        self.frames_mode = True


    @async_callback
    async def on_run(self):
        self.menu.enabled = True
        complexes = await self.request_complex_list()
        self.menu.render(complexes=complexes)

    @async_callback
    async def on_complex_list_updated(self, complexes):
        self.menu.render(complexes=complexes)

    @async_callback
    async def on_complex_added(self):
        complexes = await self.request_complex_list()
        await self.menu.render(complexes=complexes)

    @async_callback
    async def on_complex_removed(self):
        complexes = await self.request_complex_list()
        await self.menu.render(complexes=complexes)

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
    async def get_interactions(self, comp, selected_ligand, ligand_complex, interaction_data):
        """Collect Form data, and render Interactions in nanome.

        comp: Nanome Complex object
        selected_ligand: Biopython Residue object. Can be None
        ligand_complex: Complex object. Can be the same as comp.
        interactions data: Data accepted by InteractionsForm.
        """
        # await asyncio.create_task(self.destroy_lines(self._interaction_lines))
    
        # Convert complexes to frames if that setting is enabled
        if self.frames_mode:
            update_required = []
            if len(list(comp.molecules)) <= 1:
                comp = ComplexUtils.convert_complex_to_frames(comp)
                update_required.append(comp)
            if len(list(ligand_complex.molecules)) <= 1 and ligand_complex.index != comp.index:
                ligand_complex = ComplexUtils.convert_complex_to_frames(ligand_complex)
                update_required.append(ligand_complex)
            if update_required:
                await self.update_structures_deep(update_required)
                updates = await self.request_complexes([c.index for c in update_required])
                for c in updates:
                    if c.index == comp.index:
                        comp = c
                    elif c.index == ligand_complex.index:
                        ligand_complex = c

        # If residue not part of selected complex, we need to combine the complexes into one pdb
        if ligand_complex.index != comp.index:
            comp = ComplexUtils.combine_ligands(comp, [ligand_complex], comp)

        # Clean complex and return as TempFile
        cleaned_file = self.clean_complex(comp)
        cleaned_data = ''
        with open(cleaned_file.name, 'r') as f:
            cleaned_data = f.read()

        filename = cleaned_file.name.split('/')[-1]
        files = {filename: cleaned_data}

        if selected_ligand:
            # Biopython Residue
            resnames = [selected_ligand.resname]
        else:
            # Parse all residues from ligand complex
            resnames = []
            for residue in ligand_complex.residues:
                resnames.append(residue.name)
        
        selection = ','.join([f'RESNAME:{resname}' for resname in resnames])
        data = {
            'selection': selection
        }

        # make the request with the data and file
        response = requests.post(self.interactions_url, data=data, files=files)
        if response.status_code != 200:
            self.send_notification(NotificationTypes.error, 'Error =(')
            return

        self.send_notification(nanome.util.enums.NotificationTypes.message, "Interaction data retrieved!")

        # Unpack the zip file from response
        zipfile = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        with open(zipfile.name, 'wb') as f:
            f.write(response.content)

        extract_dir = tempfile.mkdtemp()
        archive_format = "zip"
        shutil.unpack_archive(zipfile.name, extract_dir, archive_format)
        contacts_filename = f"{''.join(filename.split('.')[:-1])}.contacts"
        contacts_file = f'{extract_dir}/{contacts_filename}'
        self.parse_and_upload(contacts_file, comp, ligand_complex, interaction_data)

    @staticmethod
    def get_atom(complex, atom_path):
        """Return atom corresponding to atom path.

        complex: nanome.api.Complex object
        atom_path: str (/C/20/O)
        """
        chain_name, res_id, atom_name = atom_path.split('/')

        current_molecule = list(complex.molecules)[complex.current_frame]
        nanome_residues = [
            r for r in current_molecule.residues if all([
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

    def parse_and_upload(self, interactions_file, complex, ligand_complex, interaction_form):
        """Parse .contacts file, and draw relevant interaction lines in workspace."""
        interaction_data = []
        with open(interactions_file, 'r') as f:
            reader = csv.reader(f, delimiter="\t")
            for row in reader:
                interaction_data.append(row)

        # Represents the column number of the interactions in the .contacts file
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
            # Iterate through csv data and draw relevant lines
            for i, col in enumerate(row[2:], 2):
                if col == '1':
                    interaction_type = next(
                        key for key, val in interaction_column_index.items() if val == i)
                    form_data = form.data.get(interaction_type)
                    if not form_data:
                        continue

                    line = self.draw_interaction_line(atom1, atom2, form_data)
                    line.interaction_type = interaction_type
                    line.frames = {
                        atom1.index: atom1.complex.current_frame,
                        atom2.index: atom2.complex.current_frame,
                    }
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

    async def update_interaction_lines(self, interaction_data):
        stream_type = nanome.api.streams.Stream.Type.shape_color.value
        line_indices = [line.index for line in self._interaction_lines]
        stream, _ = await self.create_writing_stream(line_indices, stream_type)

        new_colors = []
        for line in self._interaction_lines:
            # Get atoms connected to line
            atom1_index = line.anchors[0].target
            atom2_index = line.anchors[1].target

            atom1 = atom2 = None
            for comp in self.menu.complexes:
                filtered_atoms = filter(lambda atom: atom.index in [atom1_index, atom2_index], comp.atoms)
                for atom in filtered_atoms:
                    if atom.index == atom1_index:
                        atom1 = atom
                    elif atom.index == atom2_index:
                        atom2 = atom
        
            line_type = line.interaction_type
            form_data = interaction_data[line_type]
            
            line_in_frame = False
            atoms_found = atom1 is not None and atom2 is not None
            if atoms_found:
                line_in_frame = all([
                    line.frames.get(atom1_index, None) == atom1.complex.current_frame,
                    line.frames.get(atom2_index, None) == atom2.complex.current_frame
                ])

            # Hide interaction if marked not visible, or if complex frames don't line up.
            hide_interaction = not form_data['visible'] or not line_in_frame
            color = Color(*form_data['color'])
            color.a = 0 if hide_interaction else 255
            new_colors.extend([color.r, color.g, color.b, color.a])

        if stream and new_colors:
            stream.update(new_colors)
        self.send_notification(nanome.util.enums.NotificationTypes.message, "Interaction Lines updated!")

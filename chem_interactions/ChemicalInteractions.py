import csv
import requests
import tempfile
import shutil
import asyncio
from os import environ, path

import nanome
from nanome.api.structure import Complex
from nanome.util.enums import NotificationTypes
from nanome.util import async_callback, Color, Logs
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
    async def get_interactions(self, selected_complex, ligand_complex, interaction_data, ligand=None):
        """Collect Form data, and render Interactions in nanome.

        selected_complex: Nanome Complex object
        ligand_complex: Complex object containing the ligand. Often is the same as comp.
        interactions data: Data accepted by InteractionsForm.
        ligand: Biopython Residue object. Can be None
        """
        # If the ligand is not part of selected complex, merge it in.
        if ligand_complex.index != selected_complex.index:
            full_complex = ComplexUtils.combine_ligands(selected_complex, [selected_complex, ligand_complex])
        else:
            full_complex = selected_complex

        # Clean complex and return as tempfile
        cleaned_file = self.clean_complex(full_complex)
        cleaned_data = ''
        with open(cleaned_file.name, 'r') as f:
            cleaned_data = f.read()

        filename = cleaned_file.name.split('/')[-1]
        files = {filename: cleaned_data}

        # Set up data for request to interactions service
        if ligand:
            resnames = [ligand.resname]
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
        self.parse_and_upload(contacts_file, selected_complex, ligand_complex, interaction_data)

    @staticmethod
    def get_atom_from_path(complex, atom_path):
        """Return atom corresponding to atom path.

        :arg complex: nanome.api.Complex object
        :arg atom_path: str (/C/20/O)

        rtype: nanome.api.Atom object, or None
        """
        chain_name, res_id, atom_name = atom_path.split('/')
        complex_molecule = list(complex.molecules)[complex.current_frame]

        # Chain naming seems inconsistent, so we need to check the provided name,
        # as well as heteroatom variations
        atoms = [
            a for a in complex_molecule.atoms
            if a.name == atom_name
            and str(a.residue.serial) == str(res_id)
            and a.chain.name in [chain_name, f'H{chain_name}', f'H_{chain_name}']
        ]
        if len(atoms) > 1:
            raise Exception(f'Too many Atoms found for {atom_path}')
        if not atoms:
            return 
        atom = atoms[0]
        return atom

    def parse_and_upload(self, interactions_file, complex, ligand_complex, interaction_form):
        """Parse .contacts file, and draw relevant interaction lines in workspace.

        interactions_file: Path to .contacts file containing interactions data
        complex: main complex selected.
        ligand_complex: complex containing the ligand. May be same as complex arg
        interaction_form. InteractionsForms data describing color and visibility of interactions.
        """
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
            raise Exception(form.errors)

        new_lines = []

        for i, row in enumerate(interaction_data):
            # print(f"row {i}")
            # Use atom paths to get matching atoms on Nanome Structure
            atom_paths = row[:2]
            atom_list = []
            for atompath in atom_paths:
                atom = self.get_atom_from_path(complex, atompath)
                if not atom and ligand_complex.index != complex.index:
                    atom = self.get_atom_from_path(ligand_complex, atompath)

                if not atom:
                    raise Exception(f'Atom {atompath} not found')

                if atom.index == -1:
                    raise Exception(f'Somehow ended up with uninstantiated Atom')

                atom_list.append(atom)

            if len(atom_list) != 2:
                continue

            atom1, atom2 = atom_list

            # For some reason atom.complex.current_frame returns the wrong frame number.
            # Look in top level complexes for frame.
            atom1_comp = next(
                comp for comp in [ligand_complex, complex]
                if atom1.index in (a.index for a in comp.atoms)
            )
            atom2_comp = next(
                comp for comp in [ligand_complex, complex]
                if atom2.index in (a.index for a in comp.atoms)
            )

            atom1_frame = atom1_comp.current_frame
            atom2_frame = atom2_comp.current_frame

            # Iterate through csv data and draw relevant lines
            for i, col in enumerate(row[2:], 2):
                if col != '1':
                    continue

                interaction_type = next(key for key, val in interaction_column_index.items() if val == i)
                form_data = form.data.get(interaction_type)
                if not form_data:
                    continue

                # See if we've already drawn this line
                line_exists = False
                for lin in self._interaction_lines:
                    if all([
                        lin.frames.get(atom1.index) == atom1_frame,
                        lin.frames.get(atom2.index) == atom2_frame,
                            lin.interaction_type == interaction_type]):
                        line_exists = True
                        break

                if line_exists:
                    continue

                # Draw line and add data about interaction types and frames.
                line = self.draw_interaction_line(atom1, atom2, form_data)
                line.interaction_type = interaction_type
                line.frames = {
                    atom1.index: atom1_frame,
                    atom2.index: atom2_frame,
                }
                new_lines.append(line)
                asyncio.create_task(self.upload_line(line))

        Logs.debug(f'adding {len(new_lines)} new lines')
        self._interaction_lines.extend(new_lines)

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

    async def update_interaction_lines(self, interaction_data, complexes=None):
        complexes = complexes or []
        stream_type = nanome.api.streams.Stream.Type.shape_color.value
        line_indices = [line.index for line in self._interaction_lines]
        stream, _ = await self.create_writing_stream(line_indices, stream_type)
        if not stream:
            return

        new_colors = []
        in_frame_count = 0
        out_of_frame_count = 0

        for line in self._interaction_lines:
            # Make sure that both atoms connected by line are in frame.
            line_atoms = [anchor.target for anchor in line.anchors]

            line_in_frame = True
            atoms_found = 0
            # Loop through all complexes, and make sure both atoms are in frame
            for comp in complexes:
                try:
                    current_mol = list(comp.molecules)[comp.current_frame]
                except IndexError:
                    # In case of empty complex, its safe to continue
                    continue

                filtered_atoms = filter(lambda atom: atom.index in line_atoms, current_mol.atoms)
                # As soon as we find an atom not in frame, we can stop looping
                for atom in filtered_atoms:
                    atoms_found += 1
                    line_in_frame = line.frames[atom.index] == comp.current_frame
                    if not line_in_frame:
                        break

                if not line_in_frame or atoms_found == 2:
                    break

            if atoms_found != 2:
                Logs.debug(f'{2 - atoms_found} atom(s) missing')
                line_in_frame = False

            if line_in_frame:
                in_frame_count += 1
            else:
                out_of_frame_count += 1

            # Parse forms, and add line data to stream
            line_type = line.interaction_type
            form_data = interaction_data[line_type]
            hide_interaction = not form_data['visible'] or not line_in_frame
            color = Color(*form_data['color'])
            color.a = 0 if hide_interaction else 255
            new_colors.extend([color.r, color.g, color.b, color.a])

        Logs.debug(f'in frame: {in_frame_count}')
        Logs.debug(f'out of frame: {out_of_frame_count}')
        if stream:
            stream.update(new_colors)

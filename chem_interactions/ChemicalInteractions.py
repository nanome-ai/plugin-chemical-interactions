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

    @async_callback
    async def calculate_interactions(self, selected_complex, ligand_complex, interaction_data, ligand=None, selected_atoms_only=False):
        """Calculate interactions between complexes, and upload interaction lines to Nanome.

        selected_complex: Nanome Complex object
        ligand_complex: Complex object containing the ligand. Often is the same as comp.
        interactions data: Data accepted by InteractionsForm.
        ligand: Biopython Residue object. Can be None
        selected_atoms_only: bool. show interactions only for selected atoms.
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

        # Set up data for request to interactions service
        filename = cleaned_file.name.split('/')[-1]
        files = {filename: cleaned_data}
        data = {}
        selection = self.get_interaction_selections(selected_complex, ligand_complex, ligand, selected_atoms_only)
        if selection:
            data['selection'] = selection

        # make the request to get interactions
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

        self.create_new_lines(contacts_file, selected_complex, ligand_complex, interaction_data, selected_atoms_only)

        # Send notification indicating calculations completed.
        async def send_notification(plugin):
            plugin.send_notification(nanome.util.enums.NotificationTypes.message, "Finished Calculating Interactions!")
        asyncio.create_task(send_notification(self))

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

    def get_selected_atom_paths(self, comp):
        """Return a set of atom paths for the selected atoms in the complex."""
        selected_atoms = filter(lambda atom: atom.selected, comp.atoms)
        selections = set()
        for a in selected_atoms:
            chain_name = a.chain.name
            # Clean up chain name
            if chain_name.startswith('H'):
                chain_name = chain_name[1:]
            elif chain_name.startswith('H_'):
                chain_name = chain_name[2:]
            selections.add(f'/{chain_name}/{a.residue.serial}/')
        return selections

    def get_interaction_selections(self, selected_complex, ligand_complex, ligand, selected_atoms_only):
        """Generate valid list of selections to send to interactions service.

        selected_complex: Nanome Complex object
        ligand_complex: Complex object containing the ligand. Often is the same as comp.
        interactions data: Data accepted by InteractionsForm.
        ligand: Biopython Residue object. Can be None
        selected_atoms_only: bool. show interactions only for selected atoms.

        :rtype: str, comma separated list of atom paths (eg /C/20/O,/A/60/C2)
        """
        selection = None
        if ligand and not selected_atoms_only:
            # If a ligand has been specified, get all interactions for residue
            selections = [f'RESNAME:{ligand.resname}']
        elif ligand and selected_atoms_only:
            # If we only want specific atoms on the ligand, parse ligand complex
            selections = self.get_selected_atom_paths(ligand_complex)
        elif selected_atoms_only:
            # Get all selected atoms from both the selected complex and ligand complex
            selections = self.get_selected_atom_paths(selected_complex)
            if ligand_complex.index != selected_complex.index:
                ligand_selections = self.get_selected_atom_paths(ligand_complex)
                selections = selections.union(ligand_selections)
        elif selected_complex.index != ligand_complex.index:
            # If comparing two different complexes, get interactions related to ligand complex.
            selections = self.get_selected_atom_paths(ligand_complex)
        else:
            # Get all interactions for all atoms (provide no selections)
            selections = []

        selection = ','.join(selections)
        return selection

    @staticmethod
    def get_atom_from_path(complex, atom_path):
        """Return atom corresponding to atom path.

        :arg complex: nanome.api.Complex object
        :arg atom_path: str (e.g C/20/O)

        rtype: nanome.api.Atom object, or None
        """
        chain_name, res_id, atom_name = atom_path.split('/')
        complex_molecule = list(complex.molecules)[complex.current_frame]

        # Chain naming seems inconsistent, so we need to check the provided name,
        # as well as heteroatom variations
        atoms = [
            a for a in complex_molecule.atoms
            if all([
                a.name == atom_name,
                str(a.residue.serial) == str(res_id),
                a.chain.name in [chain_name, f'H{chain_name}', f'H_{chain_name}']
            ])
        ]
        if not atoms:
            return

        if len(atoms) > 1:
            # If too many atoms found, only look at specified chain name (No heteroatoms)
            atoms = [
                a for a in complex_molecule.atoms
                if all([
                    a.name == atom_name,
                    str(a.residue.serial) == str(res_id),
                    a.chain.name == chain_name
                ])
            ]
            if not atoms:
                raise Exception(f"Error finding atom {atom_path}")

            if len(atoms) > 1:
                # Just pick the first one? :grimace:
                Logs.error(f'Too many Atoms found for {atom_path}')
                atoms = atoms[:1]
        atom = atoms[0]
        return atom

    def parse_atoms_from_atompaths(self, atom_paths, complex, ligand_complex):
        """Return a list of atoms from the complexes based on the atom_paths."""
        atom_list = []
        for atompath in atom_paths:
            atom = self.get_atom_from_path(complex, atompath)
            if not atom and ligand_complex.index != complex.index:
                atom = self.get_atom_from_path(ligand_complex, atompath)

            if not atom:
                raise Exception(f'Atom {atompath} not found')
            atom_list.append(atom)
        return atom_list

    def create_new_lines(self, contacts_file, complex, ligand_complex, interaction_form, selected_atoms_only=False):
        """Parse .contacts file, and return list of new lines to render.

        contacts_file: Path to .contacts file containing interactions data.
            For data format, see https://github.com/harryjubb/arpeggio#contacts
        complex: main complex selected.
        ligand_complex: complex containing the ligand. May be same as complex arg
        interaction_form. InteractionsForms data describing color and visibility of interactions.
        """
        # Convert tsv into list of dicts for each row
        contacts_data = []
        with open(contacts_file, 'r') as f:
            reader = csv.reader(f, delimiter="\t")
            for row in reader:
                contacts_data.append(row)

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
        # Each row represents all the interactions between two atoms.
        for i, row in enumerate(contacts_data):
            self.menu.update_loading_bar(i, len(contacts_data))

            # Atom paths that current row is describing interactions between
            atom_paths = row[:2]
            atom_list = self.parse_atoms_from_atompaths(atom_paths, complex, ligand_complex)

            if len(atom_list) != 2:
                continue

            # if selected_atoms_only = True, and neither of the atoms are selected, don't draw line
            if selected_atoms_only and not any([a.selected for a in atom_list]):
                continue

            atom1, atom2 = atom_list
            # Get the current frame of the complex corresponding to each atom
            atom1_frame = atom2_frame = None
            for comp in [complex, ligand_complex]:
                if atom1.index in (a.index for a in comp.atoms):
                    atom1_frame = comp.current_frame
                if atom2.index in (a.index for a in comp.atoms):
                    atom2_frame = comp.current_frame

            # For all the interactions between atom1 and atom2, draw interaction line
            for j, col in enumerate(row[2:], 2):
                if col != '1':
                    continue

                interaction_type = next(key for key, val in interaction_column_index.items() if val == j)
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

                # Draw line and add data about interaction type and frames.
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

    async def update_interaction_lines(self, interactions_data, complexes=None):
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
                    if len(list(comp.molecules)) == 0:
                        continue
                    raise

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
            form_data = interactions_data[line_type]
            hide_interaction = not form_data['visible'] or not line_in_frame
            color = Color(*form_data['color'])
            color.a = 0 if hide_interaction else 255
            new_colors.extend([color.r, color.g, color.b, color.a])

        Logs.debug(f'in frame: {in_frame_count}')
        Logs.debug(f'out of frame: {out_of_frame_count}')
        if stream:
            stream.update(new_colors)

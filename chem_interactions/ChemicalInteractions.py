import asyncio
import requests
import tempfile
import time
from os import environ, path

import nanome
from nanome.api.structure import Complex
from nanome.api.shapes import Shape
from nanome.util.enums import NotificationTypes
from nanome.util import async_callback, Color, Logs

from forms import InteractionsForm, LineForm
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
        self.interaction_lines = []

    @async_callback
    async def on_run(self):
        self.menu.enabled = True
        complexes = await self.request_complex_list()
        self.menu.render(complexes=complexes, default_values=True)

    @async_callback
    async def on_complex_list_updated(self, complexes):
        self.menu.render(complexes=complexes)

    @async_callback
    async def on_complex_added(self):
        complexes = await self.request_complex_list()
        await self.menu.render(complexes=complexes, default_values=True)

    @async_callback
    async def on_complex_removed(self):
        complexes = await self.request_complex_list()
        await self.menu.render(complexes=complexes)

    @property
    def interaction_lines(self):
        """Maintain a list of all interaction lines stored in memory."""
        if not hasattr(self, '_interaction_lines'):
            self._interaction_lines = []
        return self._interaction_lines

    @interaction_lines.setter
    def interaction_lines(self, value):
        self._interaction_lines = value

    @async_callback
    async def calculate_interactions(self, selected_complex, ligand_complexes, interaction_data, ligands=None, selected_atoms_only=False):
        """Calculate interactions between complexes, and upload interaction lines to Nanome.

        selected_complex: Nanome Complex object
        ligand_complex: Complex object containing the ligand. Often is the same as comp.
        interactions data: Data accepted by InteractionsForm.
        ligands: List: Biopython Residue object. Can be None
        selected_atoms_only: bool. show interactions only for selected atoms.
        """
        ligands = ligands or []
        ligand_complexes = ligand_complexes or []
        Logs.message('Starting Interactions Calculation')
        start_time = time.time()

        # Let's make sure we have deep complexes
        if len(list(selected_complex.molecules)) == 0:
            selected_complex = await self.request_complexes([selected_complex.index])

        for i, lig_comp in enumerate(ligand_complexes):
            if len(list(lig_comp.molecules)) == 0:
                ligand_complexes[i] = (await self.request_complexes([lig_comp.index]))[0]

        complexes = [selected_complex, *ligand_complexes]

        # If the ligands are not part of selected complex, merge into one complex.
        if any([lc.index != selected_complex.index for lc in ligand_complexes]):
            full_complex = ComplexUtils.combine_ligands(selected_complex, complexes)
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

        selection = self.get_interaction_selections(selected_complex, ligand_complexes, ligands, selected_atoms_only)
        Logs.debug(f'Selections: {selection}')

        if selection:
            data['selection'] = selection

        # make the request to get interactions
        response = requests.post(self.interactions_url, data=data, files=files)
        if response.status_code != 200:
            self.send_notification(NotificationTypes.error, response.json()['error'])
            return

        msg = "Interaction data retrieved!"
        Logs.debug(msg)
        contacts_data = response.json()
        complexes = [selected_complex, *ligand_complexes]
        new_lines = await self.parse_contacts_data(contacts_data, complexes, interaction_data, selected_atoms_only)

        msg = f'Adding {len(new_lines)} interactions'
        Logs.message(msg)
        Shape.upload_multiple(new_lines)
        self.interaction_lines.extend(new_lines)

        async def log_elapsed_time(start_time):
            """Log the elapsed time since start time.

            Done async to make sure elapsed time accounts for async tasks.
            """
            end_time = time.time()
            elapsed_time = end_time - start_time
            Logs.message(f'Interactions Calculation completed in {elapsed_time} seconds')

        asyncio.create_task(log_elapsed_time(start_time))

        notification_txt = f"Finished Calculating Interactions!\n{len(new_lines)} lines added"
        asyncio.create_task(self.send_async_notification(notification_txt))

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

    @staticmethod
    def clean_chain_name(original_name):
        chain_name = str(original_name)
        if chain_name.startswith('H'):
            chain_name = chain_name[1:]
        elif chain_name.startswith('H_'):
            chain_name = chain_name[2:]
        return chain_name

    def get_residue_path(self, residue):
        chain_name = residue.chain.name
        chain_name = self.clean_chain_name(chain_name)
        path = f'/{chain_name}/{residue.serial}/'
        return path

    def get_atom_path(self, atom):
        chain_name = self.clean_chain_name(atom.chain.name)
        path = f'/{chain_name}/{atom.residue.serial}/{atom.name}'
        return path

    def get_selected_atom_paths(self, comp):
        """Return a set of atom paths for the selected atoms in a complex."""
        selected_atoms = filter(lambda atom: atom.selected, comp.atoms)
        selections = set()
        for a in selected_atoms:
            atompath = self.get_atom_path(a)
            selections.add(atompath)
        return selections

    def get_interaction_selections(self, selected_complex, ligand_complexes, ligands, selected_atoms_only):
        """Generate valid list of selections to send to interactions service.

        selected_complex: Nanome Complex object
        ligand_complexes: List of Complex objects containing ligands interacting with selected complex.
        interactions data: Data accepted by InteractionsForm.
        ligands: List, Biopython Residue object. Can be empty
        selected_atoms_only: bool. show interactions only for selected atoms.

        :rtype: str, comma separated string of atom paths (eg '/C/20/O,/A/60/C2')
        """
        selections = set()
        complexes = [selected_complex, *ligand_complexes]
        if ligands:
            # If a ligand has been specified, get residue path based on residue serial.
            for lig in ligands:
                chain_name = lig.parent.id
                # Find complexes that contain selected lig.
                for comp in complexes:
                    residues = (
                        res for res in comp.residues
                        if res.serial == lig._id[1] and res.chain.name in [chain_name, f"H{chain_name}", f"H_{chain_name}"]
                    )
                    for residue in residues:
                        residue_path = self.get_residue_path(residue)
                        selections.add(residue_path)
        elif selected_atoms_only:
            # Get all selected atoms from both the selected complex and ligand complex
            for comp in complexes:
                new_selection = self.get_selected_atom_paths(comp)
                selections = selections.union(new_selection)
        else:
            # Add all residues from ligand complexes to the seletion list.
            # Unless the selected complex is also the ligand, in which case don't add anything.
            for comp in ligand_complexes:
                if comp.index == selected_complex.index:
                    continue
                for res in comp.residues:
                    selections.add(self.get_residue_path(res))

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
                Logs.warning(f'Too many Atoms found for {atom_path}')
                atoms = atoms[:1]
        atom = atoms[0]
        return atom

    def parse_atoms_from_atompaths(self, atom_paths, complexes):
        """Return a list of atoms from the complexes based on the atom_paths."""
        atom_list = []
        for atompath in atom_paths:
            for comp in complexes:
                atom = self.get_atom_from_path(comp, atompath)
                if atom:
                    break

            if not atom:
                raise Exception(f'Atom {atompath} not found')
            atom_list.append(atom)
        return atom_list

    async def parse_contacts_data(self, contacts_data, complexes, interaction_data, selected_atoms_only=False):
        """Parse .contacts file into list of Lines to be rendered in Nanome.

        contacts_data: Data returned by Chemical Interaction Service.
        complex: main complex selected.
        ligand_complexes: List. complex containing the ligand. May contain same complex as complex arg
        interaction_data. InteractionsForms data describing color and visibility of interactions.
        """
        form = InteractionsForm(data=interaction_data)
        form.validate()
        if form.errors:
            raise Exception(form.errors)

        contact_data_len = len(contacts_data)
        new_lines = []
        self.menu.set_update_text("Updating Workspace")
        for i, row in enumerate(contacts_data):
            # Each row represents all the interactions between two atoms.
            self.menu.update_loading_bar(i, contact_data_len)
            # Atom paths that current row is describing interactions between
            a1_data = row['bgn']
            a2_data = row['end']
            interaction_types = row['contact']

            atom1_path = f"{a1_data['auth_asym_id']}/{a1_data['auth_seq_id']}/{a1_data['auth_atom_id']}"
            atom2_path = f"{a2_data['auth_asym_id']}/{a2_data['auth_seq_id']}/{a2_data['auth_atom_id']}"
            atom_paths = [atom1_path, atom2_path]

            # Ones with commas are Pi-Pi Interactions? I'll have to investigate further. Skip for now
            if ',' in atom1_path or ',' in atom2_path:
                continue

            atom_list = self.parse_atoms_from_atompaths(atom_paths, complexes)

            if len(atom_list) != 2:
                continue

            # if selected_atoms_only = True, and neither of the atoms are selected, don't draw line
            if selected_atoms_only and not any([a.selected for a in atom_list]):
                continue

            atom1, atom2 = atom_list
            # Get the current frame of the complex corresponding to each atom
            atom1_frame = atom2_frame = None
            for comp in complexes:
                if atom1_frame and atom2_frame:
                    break
                relevant_atoms = [a.index for a in comp.atoms if a.index in [atom1.index, atom2.index]]
                if atom1.index in relevant_atoms:
                    atom1_frame = comp.current_frame
                if atom2.index in relevant_atoms:
                    atom2_frame = comp.current_frame

            atom1.frame = atom1_frame
            atom2.frame = atom2_frame
            new_lines.extend(await self.create_new_lines(atom1, atom2, interaction_types, form.data))
        return new_lines
        
    async def create_new_lines(self, atom1, atom2, interaction_types, line_settings):
        """Parse rows of data from .contacts file into Line objects.

        atom1: nanome.api.structure.Atom
        atom2: nanome.api.structure.Atom
        interaction_types: list of interaction types that exist between atom1 and atom2
        line_settings: Color and shape information for each type of Interaction.
        """
        new_lines = []
        for interaction_type in interaction_types:
            form_data = line_settings.get(interaction_type)
            if not form_data:
                continue

            # See if we've already drawn this line
            line_exists = False
            for lin in self.interaction_lines:
                if all([
                    # Frame attribute is snuck onto the atom before passed into the function.
                    # This isn't great, we should find a better way to do it.
                    lin.frames.get(atom1.index) == atom1.frame,
                    lin.frames.get(atom2.index) == atom2.frame,
                        lin.interaction_type == interaction_type]):
                    line_exists = True
                    break
            if line_exists:
                continue

            form_data['interaction_type'] = interaction_type
            # Draw line and add data about interaction type and frames.
            line = self.draw_interaction_line(atom1, atom2, form_data)
            new_lines.append(line)

        return new_lines

    def draw_interaction_line(self, atom1, atom2, form_data):
        """Draw line connecting two atoms.

        :arg atom1: Atom
        :arg atom2: Atom
        :arg form_data: Dict {'color': (r,g,b), 'visible': bool}
        """
        # Add atom information to form_data
        lineform = LineForm(data=form_data)
        line = lineform.create()
        line.anchors[0].anchor_type = line.anchors[1].anchor_type = nanome.util.enums.ShapeAnchorType.Atom
        line.anchors[0].target, line.anchors[1].target = atom1.index, atom2.index

        line.frames = {
            atom1.index: atom1.frame,
            atom2.index: atom2.frame,
        }
        return line

    async def update_interaction_lines(self, interactions_data, complexes=None):
        complexes = complexes or []
        stream_type = nanome.api.streams.Stream.Type.shape_color.value
        line_indices = [line.index for line in self.interaction_lines]
        stream, _ = await self.create_writing_stream(line_indices, stream_type)
        if not stream:
            return

        new_colors = []
        in_frame_count = 0
        out_of_frame_count = 0

        for line in self.interaction_lines:
            # Make sure that both atoms connected by line are in frame.
            line_in_frame = self.line_in_frame(line, complexes)
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

    def line_in_frame(self, line, complexes):
        """Return boolean stating whether both atoms connected by line are in frame.

        :arg line: Line object. The line in question.
        :arg complexes: List of complexes in workspace that can contain atoms.
        """
        line_in_frame = True
        line_atoms = [anchor.target for anchor in line.anchors]

        atoms_found = 0
        for comp in complexes:
            try:
                current_mol = list(comp.molecules)[comp.current_frame]
            except IndexError:
                # In case of empty complex, its safe to continue
                if len(list(comp.molecules)) == 0:
                    continue
                raise

            filtered_atoms = filter(lambda atom: atom.index in line_atoms, current_mol.atoms)
            for atom in filtered_atoms:
                # As soon as we find an atom not in frame, we can break from loop.
                atoms_found += 1
                line_in_frame = line.frames[atom.index] == comp.current_frame
                if not line_in_frame:
                    break
            if not line_in_frame:
                break

        # If either of the atoms is not found, then line is not in frame
        if atoms_found != 2:
            line_in_frame = False

        return line_in_frame

    def clear_visible_lines(self, complexes):
        """Clear all interaction lines that are currently visible."""
        line_count = len(self.interaction_lines)
        lines_to_destroy = []
        for i in range(line_count - 1, -1, -1):
            line = self.interaction_lines[i]
            if self.line_in_frame(line, complexes):
                lines_to_destroy.append(line)
                self.interaction_lines.remove(line)

        destroyed_line_count = len(lines_to_destroy)
        Shape.destroy_multiple(lines_to_destroy)

        message = f'Deleted {destroyed_line_count} interactions'
        Logs.message(message)
        asyncio.create_task(self.send_async_notification(message))

    async def send_async_notification(self, message):
        """Send notification asynchronously."""
        notifcation_type = nanome.util.enums.NotificationTypes.message
        self.send_notification(notifcation_type, message)

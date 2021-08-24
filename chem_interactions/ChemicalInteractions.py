import asyncio
import requests
import tempfile
import time
from os import environ

import nanome
from nanome.api.structure import Atom, Complex
from nanome.api.shapes import Label, Shape
from nanome.util.enums import NotificationTypes
from nanome.util import async_callback, Color, Logs, Vector3

from forms import LineSettingsForm
from menus import ChemInteractionsMenu
from models import InteractionLine, LineManager, LabelManager
from utils import ComplexUtils

PDBOPTIONS = Complex.io.PDBSaveOptions()
PDBOPTIONS.write_bonds = True


class ChemicalInteractions(nanome.AsyncPluginInstance):

    def start(self):
        self.residue = ''
        self.interactions_url = environ.get('INTERACTIONS_URL')
        self.menu = ChemInteractionsMenu(self)
        self.show_distance_labels = False

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
    def line_manager(self):
        """Maintain a dict of all interaction lines stored in memory."""
        if not hasattr(self, '_line_manager'):
            self._line_manager = LineManager()
        return self._line_manager

    @line_manager.setter
    def line_manager(self, value):
        self._line_manager = value

    @property
    def label_manager(self):
        """Maintain a dict of all labels stored in memory."""
        if not hasattr(self, '_label_manager'):
            self._label_manager = LabelManager()
        return self._label_manager

    @label_manager.setter
    def label_manager(self, value):
        self._label_manager = value

    @async_callback
    async def calculate_interactions(
            self, selected_complex, ligand_complexes, line_settings, ligands=None,
            selected_atoms_only=False, distance_labels=False):
        """Calculate interactions between complexes, and upload interaction lines to Nanome.

        selected_complex: Nanome Complex object
        ligand_complex: Complex object containing the ligand. Often is the same as comp.
        line_settings: Data accepted by LineSettingsForm.
        ligands: List: Biopython Residue object. Can be None
        selected_atoms_only: bool. show interactions only for selected atoms.
        distance_labels: bool. States whether we want distance labels on or off
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

        complexes = [selected_complex, *[lig for lig in ligand_complexes if lig.index != selected_complex.index]]

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
        new_line_manager = await self.parse_contacts_data(contacts_data, complexes, line_settings, selected_atoms_only)

        all_new_lines = new_line_manager.all_lines()
        msg = f'Adding {len(all_new_lines)} interactions'
        Logs.message(msg)
        Shape.upload_multiple(all_new_lines)

        self.line_manager.update(new_line_manager)

        if distance_labels:
            self.render_distance_labels(complexes)

        async def log_elapsed_time(start_time):
            """Log the elapsed time since start time.

            Done async to make sure elapsed time accounts for async tasks.
            """
            end_time = time.time()
            elapsed_time = end_time - start_time
            Logs.message(f'Interactions Calculation completed in {round(elapsed_time, 2)} seconds')

        asyncio.create_task(log_elapsed_time(start_time))

        notification_txt = f"Finished Calculating Interactions!\n{len(all_new_lines)} lines added"
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
        interactions data: Data accepted by LineSettingsForm.
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

    def parse_ring_atompaths(self, atom_path, complexes):
        """Parse aromatic ring path into a list of Atoms.

        e.g 'C/100/C1,C2,C3,C4,C5,C6' --> C/100/C1, C/100/C2, C/100/C3, etc
        :rtype: List of Atoms.
        """
        chain_name, res_id, atom_names = atom_path.split('/')
        atom_names = atom_names.split(',')
        atom_paths = [f'{chain_name}/{res_id}/{atomname}' for atomname in atom_names]

        atoms = []
        for atompath in atom_paths:
            for comp in complexes:
                atom = self.get_atom_from_path(comp, atompath)
                if atom:
                    break
            if not atom:
                raise Exception(f'Atom {atompath} not found')
            atoms.append(atom)
        return atoms

    def parse_atoms_from_atompaths(self, atom_paths, complexes):
        """Return a list of atoms from the complexes based on the atom_paths."""
        atom_list = []
        for atompath in atom_paths:
            if ',' in atompath:
                # Parse aromatic ring, and add list of atoms to atom_list
                ring_atoms = self.parse_ring_atompaths(atompath, complexes)
                atom_list.append(ring_atoms)
            else:
                # Parse single atom
                for comp in complexes:
                    atom = self.get_atom_from_path(comp, atompath)
                    if atom:
                        break

                if not atom:
                    raise Exception(f'Atom {atompath} not found')
                atom_list.append(atom)
        return atom_list

    async def parse_contacts_data(self, contacts_data, complexes, line_settings, selected_atoms_only=False):
        """Parse .contacts file into list of Lines to be rendered in Nanome.

        contacts_data: Data returned by Chemical Interaction Service.
        complex: main complex selected.
        ligand_complexes: List. complex containing the ligand. May contain same complex as complex arg
        interaction_data. LineSettingsForm data describing color and visibility of interactions.

        :rtype: LineManager object containing new lines to be uploaded to Nanome workspace.
        """
        form = LineSettingsForm(data=line_settings)
        form.validate()
        if form.errors:
            raise Exception(form.errors)

        contact_data_len = len(contacts_data)
        new_line_manager = LineManager()
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

            # A struct can be either an atom or a list of atoms, indicating an aromatic ring.
            struct_list = self.parse_atoms_from_atompaths(atom_paths, complexes)

            if len(struct_list) != 2:
                continue

            struct1, struct2 = struct_list
            # if selected_atoms_only = True, and neither of the structures contain selected atoms, don't draw line
            all_atoms = []
            for struct in struct_list:
                if isinstance(struct, list):
                    all_atoms.extend(struct)
                else:
                    all_atoms.append(struct)

            if selected_atoms_only and not any([a.selected for a in all_atoms]):
                continue

            for struct in struct_list:
                # struct can either be a single atom, or a list of atoms in an aromatic ring.
                # For simplicity, make everything a list.
                if not isinstance(struct, list):
                    struct = [struct]

                # Set `frame` attribute for every atom in the structure
                # `frame` attribute required for create_new_lines to work.
                # Sneaking it in here is less than ideal
                for comp in complexes:
                    struct_indices = [a.index for a in struct]
                    relevant_atoms = [a.index for a in comp.atoms if a.index in struct_indices]
                    if relevant_atoms:
                        for atom in struct:
                            atom.frame = comp.current_frame
                        break

            # Create new lines and save them in memory
            atompair_lines = await self.create_new_lines(struct1, struct2, interaction_types, form.data)
            new_line_manager.add_lines(atompair_lines)
        return new_line_manager

    async def create_new_lines(self, struct1, struct2, interaction_types, line_settings):
        """Parse rows of data from .contacts file into Line objects.

        struct1: nanome.api.structure.Atom, or list of atoms in an aromatic ring.
        struct2: nanome.api.structure.Atom, or list of atoms in an aromatic ring.
        interaction_types: list of interaction types that exist between struct1 and struct2
        line_settings: Color and shape information for each type of Interaction.
        """
        new_lines = []
        for interaction_type in interaction_types:
            form_data = line_settings.get(interaction_type)
            if not form_data:
                continue

            # See if we've already drawn this line
            line_exists = False
            atompair_lines = self.line_manager.get_lines_for_atompair(struct1, struct2)
            for lin in atompair_lines:
                if all([
                    # Frame attribute is snuck onto the atom before passed into the function.
                    # This isn't great, we should find a better way to do it.
                    lin.frames.get(struct1.index) == struct1.frame,
                    lin.frames.get(struct2.index) == struct2.frame,
                        lin.interaction_type == interaction_type]):
                    line_exists = True
                    break
            if line_exists:
                continue

            form_data['interaction_type'] = interaction_type
            # Draw line and add data about interaction type and frames.
            line = self.draw_interaction_line(struct1, struct2, form_data)
            new_lines.append(line)

        return new_lines

    def draw_interaction_line(self, struct1, struct2, line_settings):
        """Draw line connecting two structs.

        :arg struct1: struct
        :arg struct2: struct
        :arg line_settings: Dict describing shape and color of line based on interaction_type
        """
        line = InteractionLine(struct1, struct2, **line_settings)
        anchor1, anchor2 = line.anchors
        anchor1.anchor_type = anchor2.anchor_type = nanome.util.enums.ShapeAnchorType.Atom

        for struct, anchor in zip([struct1, struct2], line.anchors):
            anchor.anchor_type = nanome.util.enums.ShapeAnchorType.Atom

            if isinstance(struct, Atom):
                anchor.target = struct.index
            elif isinstance(struct, list):
                atom = struct[0]
                anchor.target = atom.index
                struct_position = atom.position

                # Calculate offset to move anchor to center of ring
                ring_center = line.centroid([a.position for a in struct])
                offset_vector = Vector3(
                    ring_center.x - struct_position.x,
                    ring_center.y - struct_position.y,
                    ring_center.z - struct_position.z
                )
                anchor.local_offset = offset_vector

        return line

    async def update_interaction_lines(self, interactions_data, complexes=None):
        complexes = complexes or []
        stream_type = nanome.api.streams.Stream.Type.shape_color.value

        all_lines = self.line_manager.all_lines()
        line_indices = [line.index for line in all_lines]
        stream, _ = await self.create_writing_stream(line_indices, stream_type)
        if not stream:
            return

        new_colors = []
        in_frame_count = 0
        out_of_frame_count = 0

        for line in all_lines:
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
            new_colors.extend(color.rgba)
            line.color = color
            self.line_manager.update_line(line)

        Logs.debug(f'in frame: {in_frame_count}')
        Logs.debug(f'out of frame: {out_of_frame_count}')
        if stream:
            stream.update(new_colors)

        if self.show_distance_labels:
            # Refresh label manager
            self.label_manager.clear()
            self.render_distance_labels(complexes)

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
                try:
                    line_in_frame = line.frames[atom.index] == comp.current_frame
                except KeyError:
                    # Find ring frame.
                    index = next(key for key in line.frames.keys() if str(atom.index) in str(key))
                    line_in_frame = line.frames[index] == comp.current_frame
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
        lines_to_destroy = []
        labels_to_destroy = []
        for atom1_index, atom2_index in self.line_manager.get_atom_pairs():
            line_list = self.line_manager.get_lines_for_atompair(atom1_index, atom2_index)
            line_count = len(line_list)
            for i in range(line_count - 1, -1, -1):
                line = line_list[i]
                if self.line_in_frame(line, complexes):
                    lines_to_destroy.append(line)
                    line_list.remove(line)
                    # Remove any labels that have been created corresponding to this atompair
                    atom1_index, atom2_index = [anchor.target for anchor in line.anchors]
                    label = self.label_manager.remove_label_for_atompair(atom1_index, atom2_index)
                    if label:
                        labels_to_destroy.append(label)
        destroyed_line_count = len(lines_to_destroy)
        Shape.destroy_multiple([*lines_to_destroy, *labels_to_destroy])

        message = f'Deleted {destroyed_line_count} interactions'
        Logs.message(message)
        asyncio.create_task(self.send_async_notification(message))

    async def send_async_notification(self, message):
        """Send notification asynchronously."""
        notifcation_type = nanome.util.enums.NotificationTypes.message
        self.send_notification(notifcation_type, message)

    def render_distance_labels(self, complexes):
        Logs.message('Distance Labels enabled')
        self.show_distance_labels = True
        for atom1_index, atom2_index in self.line_manager.get_atom_pairs():
            # If theres any visible lines between the two atoms in atompair, add a label.
            line_list = self.line_manager.get_lines_for_atompair(atom1_index, atom2_index)
            for line in line_list:
                if self.line_in_frame(line, complexes) and line.color.a > 0:
                    label = Label()
                    label.text = str(round(line.length, 2))
                    label.font_size = 0.08
                    label.anchors = line.anchors
                    for anchor in label.anchors:
                        anchor.viewer_offset = Vector3(0, 0, -.01)
                    self.label_manager.add_label(label)
                    break
        Shape.upload_multiple(self.label_manager.all_labels())

    def clear_distance_labels(self):
        Logs.message('Clearing distance labels')
        self.show_distance_labels = False
        Shape.destroy_multiple(self.label_manager.all_labels())

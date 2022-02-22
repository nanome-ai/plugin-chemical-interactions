import asyncio
import json
import math
import os
import tempfile
import time
import uuid

import nanome
from nanome.api.structure import Complex
from nanome.api.shapes import Label, Shape
from nanome.util import async_callback, Color, enums, Logs, Process, Vector3

from .forms import LineSettingsForm
from .menus import ChemInteractionsMenu
from .models import InteractionLine, LineManager, LabelManager, InteractionStructure
from .utils import merge_complexes

PDBOPTIONS = Complex.io.PDBSaveOptions()
PDBOPTIONS.write_bonds = True


class ChemicalInteractions(nanome.AsyncPluginInstance):

    def start(self):
        self.residue = ''
        self.menu = ChemInteractionsMenu(self)
        self.show_distance_labels = False
        Logs.message('Chemical Interactions Started')

    @async_callback
    async def on_run(self):
        self.menu.enabled = True
        complexes = await self.request_complex_list()
        Logs.message('Chemical Interactions Run.')
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
            self, target_complex, ligand_residues, line_settings,
            selected_atoms_only=False, distance_labels=False):
        """Calculate interactions between complexes, and upload interaction lines to Nanome.

        target_complex: Nanome Complex object
        ligand_residues: List of residues to be used as selection.
        line_settings: Data accepted by LineSettingsForm.
        selected_atoms_only: bool. show interactions only for selected atoms.
        distance_labels: bool. States whether we want distance labels on or off
        """
        ligand_residues = ligand_residues or []
        Logs.message('Starting Interactions Calculation')
        selection_mode = 'Selected Atoms' if selected_atoms_only else 'Specific Structures'
        Logs.message(f'Selection Mode = {selection_mode}')
        start_time = time.time()

        # Let's make sure we have a deep target complex and ligand complexes
        ligand_complexes = []
        for rez in ligand_residues:
            if rez.complex:
                ligand_complexes.append(rez.complex)
            else:
                raise Exception('No Complex associated with Residue')
        
        # make sure at least one atom in the ligand complexes is selected.
        if selected_atoms_only:
            atom_selected = False
            for comp in ligand_complexes:
                if sum(1 for atom in comp.atoms if atom.selected) > 0:
                    atom_selected = True
                    break
            if not atom_selected:
                msg = "Please select at least one atom in the workspace."
                Logs.warning(msg)
                self.send_notification(enums.NotificationTypes.error, msg)
                return

        complexes = [target_complex, *[lig_comp for lig_comp in ligand_complexes if lig_comp.index != target_complex.index]]

        # If the ligands are not part of selected complex, merge into one complex.
        if len(complexes) > 1:
            full_complex = merge_complexes(complexes, align_reference=target_complex)
        else:
            full_complex = target_complex

        # Clean complex and return as tempfile
        cleaned_file = await self.clean_complex(full_complex)

        cleaned_data = ''
        with open(cleaned_file.name, 'r') as f:
            cleaned_data = f.read()

        size_in_kb = os.path.getsize(cleaned_file.name) / 1000
        Logs.message(f'Complex File Size (KB): {size_in_kb}')

        # Set up data for request to interactions service
        filename = cleaned_file.name.split('/')[-1]
        files = {filename: cleaned_data}
        data = {}
        selection = self.get_interaction_selections(target_complex, ligand_residues, selected_atoms_only)
        Logs.debug(f'Selections: {selection}')

        if selection:
            data['selection'] = selection

        # make the request to get interactions
        files = [cleaned_file]
        contacts_data = await self.run_arpeggio_process(data, files)

        msg = "Interaction data retrieved!"
        Logs.debug(msg)
        if not contacts_data:
            notification_message = "Arpeggio call failed. Please check Logs."
            self.send_notification(enums.NotificationTypes.error, notification_message)
            return

        new_line_manager = await self.parse_contacts_data(contacts_data, complexes, line_settings, selected_atoms_only)

        all_new_lines = new_line_manager.all_lines()
        msg = f'Adding {len(all_new_lines)} interactions'
        Logs.message(msg)
        Shape.upload_multiple(all_new_lines)

        self.line_manager.update(new_line_manager)

        if distance_labels:
            await self.render_distance_labels(complexes)

        async def log_elapsed_time(start_time):
            """Log the elapsed time since start time.

            Done async to make sure elapsed time accounts for async tasks.
            """
            end_time = time.time()
            elapsed_time = end_time - start_time
            msg = f'Interactions Calculation completed in {round(elapsed_time, 2)} seconds'
            Logs.message(msg)

        asyncio.create_task(log_elapsed_time(start_time))

        notification_txt = f"Finished Calculating Interactions!\n{len(all_new_lines)} lines added"
        asyncio.create_task(self.send_async_notification(notification_txt))

    @staticmethod
    async def clean_complex(complex):
        """Clean complex to prep for arpeggio."""
        input_file = tempfile.NamedTemporaryFile(suffix='.pdb', delete=False)
        complex.io.to_pdb(input_file.name, PDBOPTIONS)

        input_filename = input_file.name.split('/')[-1]
        clean_pdb_script = 'clean_pdb.py'
        exe_path = 'conda'
        args = [
            'run', '-n', 'arpeggio', 'python', clean_pdb_script, input_file.name
        ]
        p = Process(exe_path, args, True)
        p.on_error = Logs.error
        p.on_output = Logs.debug
        exit_code = await p.start()
        Logs.debug(f'Clean Complex Exit code: {exit_code}')
        cleaned_filename = '{}.clean.pdb'.format(input_filename.split('.')[0])
        cleaned_filepath = input_file.name.replace(input_filename, cleaned_filename)
        cleaned_file = tempfile.NamedTemporaryFile(suffix='.pdb')

        with open(cleaned_file.name, 'wb') as output_file, open(cleaned_filepath, 'r') as input_file:
            output_file.write(input_file.read().encode())
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

    def get_selected_atom_paths(self, struc):
        """Return a set of atom paths for the selected atoms in a structure (Complex/Residue)."""
        selected_atoms = filter(lambda atom: atom.selected, struc.atoms)
        selections = set()
        for a in selected_atoms:
            atompath = self.get_atom_path(a)
            selections.add(atompath)
        return selections

    def get_interaction_selections(self, target_complex, ligand_residues, selected_atoms_only):
        """Generate valid list of selections to send to interactions service.

        target_complex: Nanome Complex object
        ligand_residues: List of Residue objects containing ligands interacting with target complex.
        interactions data: Data accepted by LineSettingsForm.
        selected_atoms_only: bool. show interactions only for selected atoms.

        :rtype: str, comma separated string of atom paths (eg '/C/20/O,/A/60/C2')
        """
        selections = set()
        if selected_atoms_only:
            # Get all selected atoms from both the selected complex and ligand complex
            comp_selections = self.get_selected_atom_paths(target_complex)
            selections = selections.union(comp_selections)
            for rez in ligand_residues:
                rez_selections = self.get_selected_atom_paths(rez)
                selections = selections.union(rez_selections)
        else:
            # Add all residues from ligand residues to the selection list.
            # Unless the selected complex is also the ligand, in which case don't add anything.
            for rez in ligand_residues:
                rez_selections = self.get_residue_path(rez)
                selections.add(rez_selections)
        selection_str = ','.join(selections)
        return selection_str

    @staticmethod
    def get_atom_from_path(complex, atom_path):
        """Return atom corresponding to atom path.

        :arg complex: nanome.api.Complex object
        :arg atom_path: str (e.g C/20/O)

        rtype: nanome.api.Atom object, or None
        """
        chain_name, res_id, atom_name = atom_path.split('/')
        # Use the molecule from the current frame
        complex_molecule = next(
            mol for i, mol in enumerate(complex.molecules)
            if i == complex.current_frame
        )
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

    def parse_ring_atoms(self, atom_path, complexes):
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
        struct_list = []
        for atompath in atom_paths:
            if ',' in atompath:
                # Parse aromatic ring, and add list of atoms to struct_list
                ring_atoms = self.parse_ring_atoms(atompath, complexes)
                struct = InteractionStructure(ring_atoms)
            else:
                # Parse single atom
                for comp in complexes:
                    atom = self.get_atom_from_path(comp, atompath)
                    if atom:
                        break

                if not atom:
                    raise Exception(f'Atom {atompath} not found')
                struct = InteractionStructure(atom)
            struct_list.append(struct)
        return struct_list

    async def parse_contacts_data(self, contacts_data, complexes, line_settings, selected_atoms_only=False):
        """Parse .contacts file into list of Lines to be rendered in Nanome.

        contacts_data: Data returned by Chemical Interaction Service.
        complex: main complex selected.
        ligand_residues: List. complex containing the ligand. May contain same complex as complex arg
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

        # We update the menu bar to keep the user notified on progress.
        # Every 3% seems to work well.
        data_len = len(contacts_data)
        loading_bar_increment = math.ceil(data_len * 0.03)

        for i, row in enumerate(contacts_data):
            # Each row represents all the interactions between two atoms.
            if i % loading_bar_increment == 0:
                self.menu.update_loading_bar(i, contact_data_len)

            # Atom paths that current row is describing interactions between
            a1_data = row['bgn']
            a2_data = row['end']
            interaction_types = row['contact']

            # If we dont have line settings for any of the interactions in the row, we can continue
            # Typically this filters out rows with only `proximal` interactions.
            if not set(interaction_types).intersection(set(form.data.keys())):
                continue

            atom1_path = f"{a1_data['auth_asym_id']}/{a1_data['auth_seq_id']}/{a1_data['auth_atom_id']}"
            atom2_path = f"{a2_data['auth_asym_id']}/{a2_data['auth_seq_id']}/{a2_data['auth_atom_id']}"
            atom_paths = [atom1_path, atom2_path]

            # A struct can be either an atom or a list of atoms, indicating an aromatic ring.
            struct_list = self.parse_atoms_from_atompaths(atom_paths, complexes)

            if len(struct_list) != 2:
                continue

            # if selected_atoms_only = True, and neither of the structures contain selected atoms, don't draw line
            all_atoms = []
            for struct in struct_list:
                all_atoms.extend(struct.atoms)

            if selected_atoms_only and not any([a.selected for a in all_atoms]):
                continue

            for struct in struct_list:
                # Set `frame` attribute for InteractionStructure.
                for comp in complexes:
                    atom_indices = [a.index for a in struct.atoms]
                    relevant_atoms = [a.index for a in comp.atoms if a.index in atom_indices]
                    if relevant_atoms:
                        struct.frame = comp.current_frame

            # Create new lines and save them in memory
            struct1, struct2 = struct_list
            structpair_lines = await self.create_new_lines(struct1, struct2, interaction_types, form.data)
            new_line_manager.add_lines(structpair_lines)
        return new_line_manager

    async def create_new_lines(self, struct1, struct2, interaction_types, line_settings):
        """Parse rows of data from .contacts file into Line objects.

        struct1: InteractionStructure
        struct2: InteractionStructure
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
            structpair_lines = self.line_manager.get_lines_for_structure_pair(struct1, struct2)
            for lin in structpair_lines:
                if all([
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

        for struct, anchor in zip([struct1, struct2], line.anchors):
            anchor.anchor_type = nanome.util.enums.ShapeAnchorType.Atom
            anchor.target = struct.line_anchor.index
            # This nudges the line anchor to the center of the structure
            anchor.local_offset = struct.calculate_local_offset()
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
            await self.render_distance_labels(complexes)

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
                current_mol = next(
                    mol for i, mol in enumerate(comp.molecules)
                    if i == comp.current_frame)
            except StopIteration:
                # In case of empty complex, its safe to continue
                mol_count = sum(1 for _ in comp.molecules)
                if mol_count == 0:
                    continue
                raise

            filtered_atoms = filter(lambda atom: atom.index in line_atoms, current_mol.atoms)
            for atom in filtered_atoms:
                atoms_found += 1
                struct_index = None
                atom_index = str(atom.index)

                # Get the structure index from the line corresponding to the current atom,
                if atom_index in line.structure_indices:
                    struct_index = str(atom.index)
                else:
                    struct_index = next(key for key in line.structure_indices if atom_index in key)
                line_in_frame = line.frames[struct_index] == comp.current_frame
                if not line_in_frame:
                    # As soon as we find an atom not in frame, we can break from loop.
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

        # Make sure we have deep complexes.
        shallow_complexes = [comp for comp in complexes if len(list(comp.molecules)) == 0]
        if shallow_complexes:
            deep_complexes = self.request_complexes([comp.index for comp in shallow_complexes])
            for i, comp in enumerate(deep_complexes):
                if complexes[i].index == comp.index:
                    complexes[i] = comp

        for struct1_index, struct2_index in self.line_manager.get_struct_pairs():
            line_list = self.line_manager.get_lines_for_structure_pair(struct1_index, struct2_index)
            line_count = len(line_list)
            line_removed = False
            for i in range(line_count - 1, -1, -1):
                line = line_list[i]
                if self.line_in_frame(line, complexes):
                    lines_to_destroy.append(line)
                    line_list.remove(line)
                    line_removed = True
            # Remove any labels that have been created corresponding to this structpair
            if line_removed:
                label = self.label_manager.remove_label_for_structpair(struct1_index, struct2_index)
                if label:
                    labels_to_destroy.append(label)

        destroyed_line_count = len(lines_to_destroy)
        Shape.destroy_multiple([*lines_to_destroy, *labels_to_destroy])

        message = f'Deleted {destroyed_line_count} interactions'
        Logs.message(message)
        asyncio.create_task(self.send_async_notification(message))

    async def send_async_notification(self, message):
        """Send notification asynchronously."""
        notifcation_type = enums.NotificationTypes.message
        self.send_notification(notifcation_type, message)

    async def render_distance_labels(self, complexes):
        # Make sure we have deep complexes.
        shallow_complexes = [comp for comp in complexes if len(list(comp.molecules)) == 0]
        if shallow_complexes:
            deep_complexes = await self.request_complexes([comp.index for comp in shallow_complexes])
            for i, comp in enumerate(deep_complexes):
                if complexes[i].index == comp.index:
                    complexes[i] = comp

        self.show_distance_labels = True
        for struct1_index, struct2_index in self.line_manager.get_struct_pairs():
            # If theres any visible lines between the two structs in structpair, add a label.
            line_list = self.line_manager.get_lines_for_structure_pair(struct1_index, struct2_index)
            for line in line_list:
                if self.line_in_frame(line, complexes) and line.color.a > 0:
                    label = Label()
                    label.text = str(round(line.length, 2))
                    label.font_size = 0.08
                    label.anchors = line.anchors
                    for anchor in label.anchors:
                        anchor.viewer_offset = Vector3(0, 0, -.01)
                    self.label_manager.add_label(label, struct1_index, struct2_index)
                    break

        label_count = len(self.label_manager.all_labels())
        Shape.upload_multiple(self.label_manager.all_labels())
        Logs.message(f'Uploaded {label_count} distance labels')

    def clear_distance_labels(self):
        self.show_distance_labels = False
        label_count = len(self.label_manager.all_labels())
        Shape.destroy_multiple(self.label_manager.all_labels())
        Logs.message(f'Deleted {label_count} distance labels')

    @staticmethod
    async def run_arpeggio_process(data, files):
        if len(files) != 1:
            raise Exception("Invalid data")

        input_file = files[0]
        input_filepath = input_file.name

        output_data = {}
        # Set up and run arpeggio command
        exe_path = 'conda'
        arpeggio_path = 'arpeggio'
        args = [
            'run', '-n', 'arpeggio',
            arpeggio_path,
            '--mute',
            input_filepath
        ]
        if 'selection' in data:
            selections = data['selection'].split(',')
            args.append('-s')
            args.extend(selections)

        # Create directory for output
        temp_uuid = uuid.uuid4()
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = f'{temp_dir}/{temp_uuid}'
            args.extend(['-o', output_dir])

            p = Process(exe_path, args, True)
            p.on_error = Logs.error
            p.on_output = Logs.debug
            exit_code = await p.start()
            Logs.debug(f'Arpeggio Exit code: {exit_code}')

            try:
                output_filename = next(fname for fname in os.listdir(output_dir))
            except Exception:
                Logs.error('Arpeggio results not found.')
                return

            output_filepath = f'{output_dir}/{output_filename}'
            with open(output_filepath, 'r') as f:
                output_data = json.load(f)
            return output_data

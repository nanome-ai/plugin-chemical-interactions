import asyncio
import itertools
import json
import math
import os
import tempfile
import time
import uuid
import nanome
from concurrent.futures import ThreadPoolExecutor
from nanome.api.structure import Complex
from nanome.api.shapes import Label, Shape
from nanome.util import async_callback, Color, enums, Logs, Process, Vector3, ComplexUtils

from .forms import LineSettingsForm
from .menus import ChemInteractionsMenu, SettingsMenu
from .models import InteractionLine, LineManager, LabelManager, InteractionStructure
from .utils import merge_complexes, chunks
from .clean_pdb import clean_pdb

PDBOPTIONS = Complex.io.PDBSaveOptions()
PDBOPTIONS.write_bonds = True

DEFAULT_MAX_SELECTED_ATOMS = 1000
MAX_SELECTED_ATOMS = int(os.environ.get('MAX_SELECTED_ATOMS', 0) or DEFAULT_MAX_SELECTED_ATOMS)


class AtomNotFoundException(Exception):
    pass


class ChemicalInteractions(nanome.AsyncPluginInstance):

    def start(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.residue = ''
        self.menu = ChemInteractionsMenu(self)
        self.settings_menu = SettingsMenu(self)
        self.show_distance_labels = False

    def on_stop(self):
        self.temp_dir.cleanup()

    @async_callback
    async def on_run(self):
        self.menu.enabled = True
        complexes = await self.request_complex_list()
        self.menu.render(complexes=complexes, default_values=True)

    @async_callback
    async def on_complex_list_changed(self):
        complexes = await self.request_complex_list()
        await self.menu.render(complexes=complexes, default_values=True)

    def on_advanced_settings(self):
        self.settings_menu.render()

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
            self, target_complex: Complex, ligand_residues: list, line_settings: dict,
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
        extra = {"atom_selection_mode": selection_mode}
        Logs.message(f'Selection Mode = {selection_mode}', extra=extra)
        start_time = time.time()

        # Let's make sure we have a deep target complex and ligand complexes
        ligand_complexes = []
        for res in ligand_residues:
            if res.complex:
                ligand_complexes.append(res.complex)
            else:
                raise Exception('No Complex associated with Residue')

        settings = self.settings_menu.get_settings()
        if settings['recalculate_on_update']:
            self.setup_previous_run(
                target_complex, ligand_residues, ligand_complexes, line_settings,
                selected_atoms_only, distance_labels)

        complexes = set([target_complex, *[lig_comp for lig_comp in ligand_complexes if lig_comp.index != target_complex.index]])

        # If the ligands are not part of selected complex, merge into one complex.
        if len(complexes) > 1:
            full_complex = merge_complexes(complexes, align_reference=target_complex, selected_atoms_only=selected_atoms_only)
        else:
            full_complex = target_complex

        # Clean complex and return as tempfile
        self.menu.set_update_text("Prepping...")
        cleaned_filepath = self.get_clean_pdb_file(full_complex)
        size_in_kb = os.path.getsize(cleaned_filepath) / 1000
        Logs.message(f'Complex File Size (KB): {size_in_kb}')

        # Set up data for request to interactions service
        data = {}
        selection = self.get_interaction_selections(
            target_complex, ligand_residues, selected_atoms_only)
        Logs.debug(f'Selections: {selection}')

        if selection:
            data['selection'] = selection

        # make the request to get interactions
        self.menu.set_update_text("Calculating...")
        contacts_data = await self.run_arpeggio_process(data, cleaned_filepath)

        Logs.debug("Interaction data retrieved!")
        if not contacts_data:
            notification_message = "Arpeggio run failed. Please make sure source files are valid."
            self.send_notification(enums.NotificationTypes.error, notification_message)
            return
        Logs.message(f'Contacts Count: {len(contacts_data)}')

        interacting_entities_to_render = settings['interacting_entities']
        contacts_per_thread = 1000
        thread_count = max(len(contacts_data) // contacts_per_thread, 1)
        futs = []
        self.total_contacts_count = len(contacts_data)
        self.loading_bar_i = 0
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            for chunk in chunks(contacts_data, len(contacts_data) // thread_count):
                fut = executor.submit(self.parse_contacts_data, chunk, complexes, line_settings, selected_atoms_only, interacting_entities_to_render)
                futs.append(fut)
        new_line_manager = LineManager()
        for fut in futs:
            new_line_manager.update(fut.result())
        all_new_lines = new_line_manager.all_lines()
        Logs.message(f'Adding {len(all_new_lines)} interactions')
        Shape.upload_multiple(all_new_lines)

        # Make sure complexes are locked
        # Skip if user has recalculate on update turned on
        # Causes cycles of continuous recalculation.
        comps_to_lock = [cmp for cmp in complexes if not cmp.locked]
        if any(comps_to_lock) and not settings['recalculate_on_update']:
            for comp in comps_to_lock:
                # Make sure we don't inadvertantly move the complex
                ComplexUtils.reset_transform(comp)
                comp.locked = True
            self.update_structures_shallow(comps_to_lock)

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
            Logs.message(msg, extra={'calculation_time': float(elapsed_time)})

        asyncio.create_task(log_elapsed_time(start_time))

        notification_txt = f"Finished Calculating Interactions!\n{len(all_new_lines)} lines added"
        asyncio.create_task(self.send_async_notification(notification_txt))

    def get_clean_pdb_file(self, complex):
        """Clean complex to prep for arpeggio."""
        Logs.debug("Cleaning complex for arpeggio")
        complex_file = tempfile.NamedTemporaryFile(suffix='.pdb', delete=False, dir=self.temp_dir.name)
        complex.io.to_pdb(complex_file.name, PDBOPTIONS)

        cleaned_filepath = clean_pdb(complex_file.name, self)
        if os.path.getsize(cleaned_filepath) / 1000 == 0:
            message = 'Complex file is empty, unable to clean =(.'
            Logs.error(message)
            raise Exception(message)
        if not os.path.exists(cleaned_filepath):
            # If clean_pdb fails, just try sending the uncleaned
            # complex to arpeggio
            # Not sure how effective that is, but :shrug:
            Logs.warning('Clean Complex failed. Sending uncleaned file to arpeggio.')
            cleaned_filepath = complex_file.name
        else:
            complex_file.close()
        return cleaned_filepath

    @staticmethod
    def clean_chain_name(original_name):
        chain_name = str(original_name)
        if chain_name.startswith('H') and len(chain_name) > 1:
            chain_name = chain_name[1:]
        return chain_name

    @classmethod
    def get_residue_path(cls, residue):
        chain_name = residue.chain.name
        chain_name = cls.clean_chain_name(chain_name)
        path = f'/{chain_name}/{residue.serial}/'
        return path

    @classmethod
    def get_atom_path(cls, atom):
        chain_name = cls.clean_chain_name(atom.chain.name)
        path = f'/{chain_name}/{atom.residue.serial}/{atom.name}'
        return path

    @classmethod
    def get_complex_selection_paths(cls, comp):
        selections = set()
        for res in comp.residues:
            res_selections = cls.get_residue_selection_paths(res)
            if res_selections:
                selections = selections.union(res_selections)
        return selections

    @classmethod
    def get_residue_selection_paths(cls, residue):
        """Return a set of atom paths for the selected atoms in a structure (Complex/Residue)."""
        selections = set()
        unselected_atoms = filter(lambda atom: not atom.selected, residue.atoms)
        if sum(1 for _ in unselected_atoms) == 0:
            selections.add(cls.get_residue_path(residue))
        else:
            selected_atoms = filter(lambda atom: atom.selected, residue.atoms)
            for atom in selected_atoms:
                selections.add(cls.get_atom_path(atom))
        return selections

    @classmethod
    def get_interaction_selections(cls, target_complex, ligand_residues, selected_atoms_only):
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
            comp_selections = cls.get_complex_selection_paths(target_complex)
            selections = selections.union(comp_selections)
            for rez in ligand_residues:
                rez_selections = cls.get_residue_selection_paths(rez)
                selections = selections.union(rez_selections)
        else:
            # Add all residues from ligand residues to the selection list.
            # Unless the selected complex is also the ligand, in which case don't add anything.
            for rez in ligand_residues:
                rez_selections = cls.get_residue_path(rez)
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
        # Use the molecule corresponding to current frame
        complex_molecule = next(
            mol for i, mol in enumerate(complex.molecules)
            if i == complex.current_frame
        )
        # Chain naming seems inconsistent, so we need to check the provided name,
        # as well as heteroatom variation
        atoms = [
            a for a in complex_molecule.atoms
            if all([
                a.name == atom_name,
                str(a.residue.serial) == str(res_id),
                a.chain.name in [chain_name, f'H{chain_name}']
            ])
        ]
        if not atoms:
            return

        if len(atoms) > 1:
            # If multiple atoms found, check exact matches (no heteroatoms)
            atoms = [
                a for a in complex_molecule.atoms
                if all([
                    a.name == atom_name,
                    str(a.residue.serial) == str(res_id),
                    a.chain.name == chain_name
                ])
            ]
            if not atoms:
                msg = f"Error finding atom {atom_path}. Please ensure atoms are uniquely named."
                Logs.warning(msg)
                raise AtomNotFoundException(msg)

            if len(atoms) > 1:
                # Just pick the first one? :grimace:
                Logs.warning(f'Too many Atoms found for {atom_path}')
                atoms = atoms[:1]
        atom = atoms[0]
        return atom

    @classmethod
    def parse_ring_atoms(cls, atom_path, complexes):
        """Parse aromatic ring path into a list of Atoms.

        e.g 'C/100/C1,C2,C3,C4,C5,C6' --> C/100/C1, C/100/C2, C/100/C3, etc
        :rtype: List of Atoms.
        """
        chain_name, res_id, atom_names = atom_path.split('/')
        atom_names = atom_names.split(',')
        atom_paths = [f'{chain_name}/{res_id}/{atomname}' for atomname in atom_names]

        atoms = []
        for atompath in atom_paths:
            atom = None
            for comp in complexes:
                atom = cls.get_atom_from_path(comp, atompath)
                if atom:
                    break
            if atom:
                atoms.append(atom)
        return atoms

    @classmethod
    def parse_atoms_from_atompaths(cls, atom_paths, complexes):
        """Return a list of atoms from the complexes based on the atom_paths.

        :rtype: List of Atoms
        """
        struct_list = []
        for atompath in atom_paths:
            atom = None
            if ',' in atompath:
                # Parse aromatic ring, and add list of atoms to struct_list
                ring_atoms = cls.parse_ring_atoms(atompath, complexes)
                struct = InteractionStructure(ring_atoms)
            else:
                # Parse single atom
                for comp in complexes:
                    atom = cls.get_atom_from_path(comp, atompath)
                    if atom:
                        break
                if not atom:
                    continue
                struct = InteractionStructure(atom)
            struct_list.append(struct)
        return struct_list

    def parse_contacts_data(self, contacts_data, complexes, line_settings, selected_atoms_only=False, interacting_entities=None):
        """Parse .contacts file into list of Lines to be rendered in Nanome.

        contacts_data: Data returned by Chemical Interaction Service.
        complexes: strucutre.Complex objects that can contain atoms in contacts_data.
        line_settings: dict. Data to populate LineSettingsForm.
        interaction_data. LineSettingsForm data describing color and visibility of interactions.

        :rtype: LineManager object containing new lines to be uploaded to Nanome workspace.
        """
        interacting_entities = interacting_entities or ['INTER', 'INTRA_SELECTION', 'SELECTION_WATER']
        form = LineSettingsForm(data=line_settings)
        form.validate()
        if form.errors:
            raise Exception(form.errors)
        # Set variables used to track loading bar progress across threads.
        if not hasattr(self, 'loading_bar_i'):
            self.loading_bar_i = 0
        if not hasattr(self, 'total_contacts_count'):
            self.total_contacts_count = len(contacts_data)

        new_line_manager = LineManager()
        self.menu.set_update_text("Updating Workspace...")
        # Update loading bar every 5% of contacts completed
        update_percentages = list(range(100, 0, -5))
        for row in contacts_data:
            self.loading_bar_i += 1
            current_percentage = math.ceil((self.loading_bar_i / self.total_contacts_count) * 100)
            if update_percentages and current_percentage > update_percentages[-1]:
                Logs.debug(f"{self.loading_bar_i} / {self.total_contacts_count} contacts processed")
                self.menu.update_loading_bar(self.loading_bar_i, self.total_contacts_count)
                update_percentages.pop()

            # Atom paths that current row is describing interactions between
            a1_data = row['bgn']
            a2_data = row['end']
            interaction_types = row['contact']

            # If we dont have line settings for any of the interactions in the row, we can continue
            # Typically this filters out rows with only `proximal` interactions.
            if not set(interaction_types).intersection(set(form.data.keys())):
                continue

            # If structure's relationship is not included, continue
            if row['interacting_entities'] not in interacting_entities:
                continue

            atom1_path = f"{a1_data['auth_asym_id']}/{a1_data['auth_seq_id']}/{a1_data['auth_atom_id']}"
            atom2_path = f"{a2_data['auth_asym_id']}/{a2_data['auth_seq_id']}/{a2_data['auth_atom_id']}"
            atom_paths = [atom1_path, atom2_path]

            # A struct can be either an atom or a list of atoms, indicating an aromatic ring.
            try:
                struct_list = self.parse_atoms_from_atompaths(atom_paths, complexes)
            except AtomNotFoundException:
                message = (
                    f"Failed to parse interactions between {atom1_path} and {atom2_path} "
                    f"skipping {len(interaction_types)} interactions"
                )
                Logs.warning(message)
                continue
            if len(struct_list) != 2:
                Logs.warning("Failed to parse atom paths, skipping")
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
            structpair_lines = self.create_new_lines(struct1, struct2, interaction_types, form.data)
            new_line_manager.add_lines(structpair_lines)
        return new_line_manager

    def create_new_lines(self, struct1, struct2, interaction_types, line_settings):
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

    @staticmethod
    def draw_interaction_line(struct1, struct2, line_settings):
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

        # Logs.debug(f'in frame: {in_frame_count}')
        # Logs.debug(f'out of frame: {out_of_frame_count}')
        if stream:
            stream.update(new_colors)

        if self.show_distance_labels:
            # Refresh label manager
            self.label_manager.clear()
            await self.render_distance_labels(complexes)

    @staticmethod
    def line_in_frame(line, complexes):
        """Return boolean stating whether both atoms connected by line are in frame.

        :arg line: Line object. The line in question.
        :arg complexes: List of complexes in workspace that can contain atoms.
        """
        line_atom_indices = [anchor.target for anchor in line.anchors]
        atom_generators = []
        for comp in complexes:
            try:
                current_mol = next(
                    mol for i, mol in enumerate(comp.molecules)
                    if i == comp.current_frame)
            except StopIteration:
                # In case of empty complex, its safe to continue
                if sum(1 for _ in comp.molecules) == 0:
                    continue
                raise
            atom_generators.append(current_mol.atoms)
        current_atoms = itertools.chain(*atom_generators)
        atoms_found = 0
        for atom in current_atoms:
            if atom.index not in line_atom_indices:
                continue
            # Make sure atom is in the correct conformer
            comp = atom.complex
            mol = next(
                ml for i, ml in enumerate(comp.molecules)
                if i == comp.current_frame)
            current_conformer = mol.current_conformer
            correct_conformer = line.conformers.get(comp.index) != current_conformer
            if correct_conformer:
                atoms_found += 1

            if atoms_found == 2:
                break
        line_in_frame = atoms_found == 2
        return line_in_frame

    async def clear_visible_lines(self, complexes, send_notification=True):
        """Clear all interaction lines that are currently visible."""
        lines_to_destroy = []
        labels_to_destroy = []

        # Make sure we have deep complexes.
        shallow_complexes = [comp for comp in complexes if len(list(comp.molecules)) == 0]
        if shallow_complexes:
            deep_complexes = await self.request_complexes([comp.index for comp in shallow_complexes])
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
        if send_notification:
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
            # Not sure how, but theres errors where a NoneType ends up in deep_complexes
            # This is a quick fix for that.
            deep_complexes = [comp for comp in deep_complexes if comp]
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
    async def run_arpeggio_process(data, input_filepath):
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

            p = Process(exe_path, args, True, label="arpeggio")
            p.on_error = Logs.warning
            p.on_output = Logs.message
            exit_code = await p.start()
            Logs.message(f'Arpeggio Exit code: {exit_code}')

            if not os.path.exists(output_dir) or not os.listdir(output_dir):
                Logs.error('Arpeggio run failed.')
                return

            output_filename = next(fname for fname in os.listdir(output_dir))
            output_filepath = f'{output_dir}/{output_filename}'
            with open(output_filepath, 'r') as f:
                output_data = json.load(f)
            return output_data

    def setup_previous_run(
        self, target_complex: Complex, ligand_residues: list, ligand_complexes: list, line_settings: dict,
            selected_atoms_only=False, distance_labels=False):
        self.previous_run = {
            'target_complex': target_complex,
            'ligand_residues': ligand_residues,
            'ligand_complexes': ligand_complexes,
            'line_settings': line_settings,
            'selected_atoms_only': selected_atoms_only,
            'distance_labels': distance_labels
        }
        res_complexes = [res.complex for res in ligand_residues]
        all_complexes = [target_complex] + res_complexes
        for comp in all_complexes:
            comp.register_complex_updated_callback(self.recalculate_interactions)

    @async_callback
    async def recalculate_interactions(self, updated_comp: Complex):
        """Recalculate interactions from the previous run."""
        if not hasattr(self, 'previous_run'):
            return

        Logs.message("Recalculating previous run with updated structures.")
        await self.send_async_notification('Recalculating interactions...')
        target_complex = self.previous_run['target_complex']
        ligand_residues = self.previous_run['ligand_residues']
        ligand_complexes = self.previous_run['ligand_complexes']
        line_settings = self.previous_run['line_settings']
        selected_atoms_only = self.previous_run['selected_atoms_only']
        distance_labels = self.previous_run['distance_labels']

        # Clear visible lines
        previous_comps = [target_complex] + ligand_complexes
        previous_comps = [cmp for cmp in previous_comps if cmp.index != updated_comp.index]
        all_complexes = [updated_comp] + previous_comps
        await self.clear_visible_lines(all_complexes, send_notification=False)

        comp_indices_to_update = [
            comp.index for comp in all_complexes
            if comp.index != updated_comp.index
        ]
        if comp_indices_to_update:
            updated_comps = await self.request_complexes(comp_indices_to_update)
            updated_comps.append(updated_comp)
        else:
            updated_comps = [updated_comp]

        updated_target_comp = next(
            cmp for cmp in updated_comps if cmp.index == target_complex.index)

        lig_comp_indices = [cmp.index for cmp in ligand_complexes]
        updated_lig_comps = [
            cmp for cmp in updated_comps if cmp.index in lig_comp_indices]

        updated_residues = []
        for comp in updated_lig_comps:
            updated_residues.extend([
                res for res in comp.residues
                if res.index in [r.index for r in ligand_residues]
            ])

        await self.menu.run_calculation(
            updated_target_comp, updated_residues, line_settings,
            selected_atoms_only=selected_atoms_only,
            distance_labels=distance_labels
        )

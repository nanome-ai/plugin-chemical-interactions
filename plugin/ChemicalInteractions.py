import asyncio
import itertools
import json
import math
import os
import tempfile
import time
import uuid
import nanome
import numpy as np
# from concurrent.futures import ThreadPoolExecutor
from nanome._internal.serializer_fields import TypeSerializer
from nanome.api.structure import Complex
from nanome.api.shapes import Label, Shape, Anchor
from nanome.api.interactions import Interaction
from nanome.util import async_callback, enums, Logs, Process, Vector3, ComplexUtils
from typing import List

from .forms import LineSettingsForm
from .menus import ChemInteractionsMenu, SettingsMenu
from .models import LineManager, LabelManager, InteractionStructure
from .utils import merge_complexes, interaction_type_map, calculate_interaction_length  # , chunks
from .clean_pdb import clean_pdb


PDBOPTIONS = Complex.io.PDBSaveOptions()
PDBOPTIONS.write_bonds = True

# By default Arpeggio times out after 10 minutes (600 seconds)
ARPEGGIO_TIMEOUT = int(os.environ.get('ARPEGGIO_TIMEOUT', 0) or 600)


class AtomNotFoundException(Exception):
    pass


class ChemicalInteractions(nanome.AsyncPluginInstance):

    def start(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.residue = ''
        self.menu = ChemInteractionsMenu(self)
        self.settings_menu = SettingsMenu(self)
        self.show_distance_labels = False
        self.__complex_cache = {}

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
        for cmp in complexes:
            self.__complex_cache[cmp.index] = cmp
            cmp.register_complex_updated_callback(self.on_complex_updated)

        # If the ligands are not part of selected complex, merge into one complex
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
        # contacts_per_thread = 1000
        # thread_count = max(len(contacts_data) // contacts_per_thread, 1)
        # futs = []
        self.total_contacts_count = len(contacts_data)
        self.loading_bar_i = 0

        new_lines = await self.parse_contacts_data(
            contacts_data, complexes, line_settings, selected_atoms_only, interacting_entities_to_render)
        Logs.message(f'Added {len(new_lines)} interactions')
        # with ThreadPoolExecutor(max_workers=thread_count) as executor:
        #     for chunk in chunks(contacts_data, len(contacts_data) // thread_count):
        #         fut = executor.submit(self.parse_contacts_data, chunk, complexes, line_settings, selected_atoms_only, interacting_entities_to_render)
        #         futs.append(fut)
        # new_line_manager = LineManager()
        # for fut in futs:
        #     new_line_manager.update(fut.result())

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

        # self.line_manager.update(new_line_manager)
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

        notification_txt = f"Finished Calculating Interactions! {len(new_lines)} lines added"
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
                # Get frame and conformer from first atom in ring
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

    async def parse_contacts_data(self, contacts_data, complexes, line_settings, selected_atoms_only=False, interacting_entities=None):
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

        # new_line_manager = LineManager()
        new_lines = []
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
                # Set `frame` and `conformer` attribute for InteractionStructure.
                for comp in complexes:
                    atom_indices = [a.index for a in struct.atoms]
                    relevant_atoms = [a.index for a in comp.atoms if a.index in atom_indices]
                    if relevant_atoms:
                        struct.frame = comp.current_frame
                        struct.conformer = list(comp.molecules)[comp.current_frame].current_conformer
            # Create new lines and save them in memory
            struct1, struct2 = struct_list
            structpair_lines = await self.create_new_lines(struct1, struct2, interaction_types, form.data)
            new_lines += structpair_lines
        await Interaction.upload_multiple(new_lines)
        return new_lines

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
            try:
                structpair_lines = await self.line_manager.get_lines_for_structure_pair(struct1.index, struct2.index)
            except AttributeError:
                continue

            struct1_atom_index = int(struct1.index.split('/')[0])
            # struct2_atom_index = int(struct2.index.split('/')[0])
            for lin in structpair_lines:
                struct1_is_atom1 = struct1_atom_index in lin.atom1_idx_arr
                interaction_kind = interaction_type_map[interaction_type]
                # struct2_is_atom1 = struct2_atom_index in lin.atom1_index
                if struct1_is_atom1:
                    struct1_conformer_in_frame = struct1.conformer == lin.atom1_conformation
                    struct2_conformer_in_frame = struct2.conformer == lin.atom2_conformation
                else:
                    struct1_conformer_in_frame = struct1.conformer == lin.atom2_conformation
                    struct2_conformer_in_frame = struct2.conformer == lin.atom1_conformation
                if all([
                    struct1_conformer_in_frame,
                    struct2_conformer_in_frame,
                        lin.kind == interaction_kind]):
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
    def draw_interaction_line(struct1: InteractionStructure, struct2: InteractionStructure, line_settings):
        """Draw line connecting two structs.

        :arg struct1: struct
        :arg struct2: struct
        :arg line_settings: Dict describing shape and color of line based on interaction_type
        """
        struct1_indices = []
        struct2_indices = []
        for struct1_index in struct1.index.split(','):
            struct1_indices.append(int(struct1_index))
        for struct2_index in struct2.index.split(','):
            struct2_indices.append(int(struct2_index))

        interaction_kind = interaction_type_map[line_settings['interaction_type']]
        # TODO: Don't hardcode this
        atom1_conformation = 0
        atom2_conformation = 0
        line = Interaction(
            interaction_kind,
            struct1_indices,
            struct2_indices,
            atom1_conf=atom1_conformation,
            atom2_conf=atom2_conformation
        )
        line.visible = line_settings['visible']
        return line

    async def update_interaction_lines(self, interactions_data, complexes=None):
        interactions = await Interaction.get()
        lines_to_update = []
        for line in interactions:
            interaction_type = next(key for key, val in interaction_type_map.items() if val == line.kind)
            interaction_visible = interactions_data[interaction_type]['visible']
            if line.visible != interaction_visible:
                line.visible = interaction_visible
                lines_to_update.append(line)
        Logs.debug(f'Updating {len(lines_to_update)} lines')
        Interaction.upload_multiple(lines_to_update)
        if self.show_distance_labels:
            # Refresh label manager
            self.label_manager.clear()
            await self.render_distance_labels(complexes)

    @classmethod
    def line_in_frame(cls, line: Interaction, complexes):
        """Return boolean stating whether both structures connected by line are in frame.

        :arg line: Line object. The line in question.
        :arg complexes: List of complexes in workspace that can contain atoms.
        """
        all_atoms = itertools.chain(*[comp.atoms for comp in complexes])
        # Find the atoms from the comp by their id, and make sure  they're in the same conformer.
        atom1_in_frame = None
        atom2_in_frame = None
        for atom in all_atoms:
            if atom.index in line.atom1_idx_arr:
                mol = atom.molecule
                atom1_in_frame = mol.current_conformer == line.atom1_conformation
            elif atom.index in line.atom2_idx_arr:
                mol = atom.molecule
                atom2_in_frame = mol.current_conformer == line.atom2_conformation
            if atom1_in_frame is not None and atom2_in_frame is not None:
                break

        line_in_frame = atom1_in_frame and atom2_in_frame
        return line_in_frame

    @classmethod
    def check_struct_key(cls, struct_key, atom):
        # key_hash = struct_key.split('_')
        # parse key_hash
        atom_pos_strs = struct_key.split(',')
        has_matches = False
        for atom_pos_str in atom_pos_strs:
            atom_index, x, y, z = atom_pos_str.split('/')
            if atom_index != str(atom.index):
                continue
            pos = Vector3(float(x), float(y), float(z))
            if np.allclose(atom.position.unpack(), pos.unpack()):
                has_matches = True
                break
        return has_matches

    async def clear_lines_in_frame(self, complexes, send_notification=True):
        """Clear all interaction lines in the current set of frames and conformers."""
        shallow_complexes = [comp for comp in complexes if len(list(comp.molecules)) == 0]
        if shallow_complexes:
            deep_complexes = await self.request_complexes([comp.index for comp in shallow_complexes])
            deep_complexes = [comp for comp in deep_complexes if comp]
            for i, comp in enumerate(deep_complexes):
                if complexes[i].index == comp.index:
                    complexes[i] = comp
        all_lines = await Interaction.get()

        lines_to_delete = []
        for line in all_lines:
            if self.line_in_frame(line, complexes):
                lines_to_delete.append(line)
            else:
                pass
        if lines_to_delete:
            Interaction.destroy_multiple(lines_to_delete)
        self.label_manager.clear()

        destroyed_line_count = len(lines_to_delete)
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
        all_lines = await Interaction.get()
        for line in all_lines:
            # If theres any visible lines between the two structs in structpair, add a label.
            struct1_index = line.atom1_idx_arr[0]
            struct2_index = line.atom2_idx_arr[0]
            if line.visible and self.line_in_frame(line, complexes):
                label = Label()
                interaction_distance = calculate_interaction_length(line, complexes)
                label.text = str(round(interaction_distance, 2))
                label.font_size = 0.06
                anchor1 = Anchor()
                anchor2 = Anchor()
                anchor1.target = struct1_index
                anchor2.target = struct2_index
                anchor1.anchor_type = enums.ShapeAnchorType.Atom
                anchor2.anchor_type = enums.ShapeAnchorType.Atom
                viewer_offset = Vector3(0, 0, -.01)
                anchor1.viewer_offset = viewer_offset
                anchor2.viewer_offset = viewer_offset
                label.anchors = [anchor1, anchor2]
                self.label_manager.add_label(label, struct1_index, struct2_index)

        label_count = len(self.label_manager.all_labels())
        await Shape.upload_multiple(self.label_manager.all_labels())
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

            p = Process(exe_path, args, True, label="arpeggio", timeout=ARPEGGIO_TIMEOUT)
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

    @async_callback
    async def on_complex_updated(self, updated_comp: Complex):
        """Callback for when a complex is updated."""
        # Get all updated complexes
        cached_complexes = [cmp for cmp in self.__complex_cache.values() if cmp.index != updated_comp.index]
        updated_comp_list = [updated_comp] + cached_complexes

        # Redraw lines
        interactions_data = self.menu.collect_interaction_data()
        await self.update_interaction_lines(interactions_data, complexes=updated_comp_list)

        # Recalculate interactions if that setting is enabled.
        recalculate_enabled = self.settings_menu.get_settings()['recalculate_on_update']
        if recalculate_enabled and hasattr(self, 'previous_run'):
            await self.recalculate_interactions(updated_comp_list)

    async def recalculate_interactions(self, updated_comps: List[Complex]):
        """Recalculate interactions from the previous run."""
        Logs.message("Recalculating previous run with updated structures.")
        await self.send_async_notification('Recalculating interactions...')
        target_complex = self.previous_run['target_complex']
        ligand_residues = self.previous_run['ligand_residues']
        ligand_complexes = self.previous_run['ligand_complexes']
        line_settings = self.previous_run['line_settings']
        selected_atoms_only = self.previous_run['selected_atoms_only']
        distance_labels = self.previous_run['distance_labels']

        updated_target_comp = next(
            cmp for cmp in updated_comps
            if cmp.index == target_complex.index)

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
            distance_labels=distance_labels)

    @staticmethod
    def supports_persistent_interactions():
        # Currently this always return True
        # TODO: "GetInteractions" should return 0 if not supported, else 1
        version_table = TypeSerializer.get_version_table()
        return version_table.get('GetInteractions', -1) > 0

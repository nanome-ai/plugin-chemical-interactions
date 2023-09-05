from collections import defaultdict
from operator import attrgetter

from .utils import interaction_type_map
from nanome.api.shapes import Label, Line, Shape
from nanome.api.structure import Atom
from nanome.api.interactions import Interaction


class InteractionStructure:
    """Abstraction representing one end of a chemical interaction.

    Is either a single Atom, or a ring of atoms.
    """

    # Records the frame and conformer of the complex that the Structure is a part of.
    frame = None
    conformer = None

    def __init__(self, atom_or_atoms, frame=None, conformer=None):
        """Pass in either a single Atom object or a list of Atoms."""
        if isinstance(atom_or_atoms, Atom):
            self.atoms.append(atom_or_atoms)
        elif isinstance(atom_or_atoms, list):
            self.atoms.extend(atom_or_atoms)
        self.frame = frame
        self.conformer = conformer

    @property
    def atoms(self):
        if not hasattr(self, '_atoms'):
            self._atoms = []
        return self._atoms

    @property
    def index(self):
        """Unique index based on atoms in structure and their positions.
        examples
        single atom structure -> '5432591673'
        ring structures -> '5432591673,75462591674,943234535'
        """
        atom_strs = []
        for a in sorted(self.atoms, key=attrgetter('index')):
            atom_strs.append(str(a.index))
        index = ','.join(atom_strs)
        return index


class StructurePairManager:
    """Functions used by Managers to create keys to uniquely identify pairs of InteractionStructures."""

    def __init__(self):
        super().__init__()
        self._data = defaultdict(list)

    @staticmethod
    def get_structpair_key(struct1_key, struct2_key):
        """Return a string key for the given atom indices."""
        structpair_key = '|'.join(sorted([str(struct1_key), str(struct2_key)]))
        return structpair_key

    @staticmethod
    def get_structpair_key_for_line(line):
        """Return a string key for the given atom indices."""
        struct1_key = ','.join(line.atom1_idx_arr)
        struct2_key = ','.join(line.atom2_idx_arr)
        structpair_key = '|'.join(sorted([struct1_key, struct2_key]))
        return structpair_key

    def get_struct_pairs(self):
        """Return a list of structure pairs being tracked by manager."""
        struct_pairs = []
        for structpair_key in self._data:
            struct1_key, struct2_key = structpair_key.split('|')
            # struct1_index, struct1_frame, struct1_conformer = struct1_key.split('_')
            struct_pairs.append((struct1_key, struct2_key))
        return struct_pairs


class LineManager(StructurePairManager):
    """Organizes Interaction lines by atom pairs."""

    async def all_lines(self):
        """Return a flat list of all lines being stored."""
        interactions = await Interaction.get()
        return interactions

    def add_lines(self, line_list):
        for line in line_list:
            self.add_line(line)

    def add_line(self, line):
        if not isinstance(line, Interaction):
            raise TypeError(f'add_line() expected Interaction, received {type(line)}')

        structpair_key = self.get_structpair_key_for_line(line)
        self._data[structpair_key].append(line)

    async def get_lines_for_structure_pair(self, struct1_index: str, struct2_index: str):
        """Given two InteractionStructures, return all interaction lines connecting them.

        :arg struct1: InteractionStructure, or index str
        :arg struct2: InteractionStructure, or index str
        """
        struct1_indices_str = struct1_index.split(',')
        struct2_indices_str = struct2_index.split(',')
        struct1_indices = [int(idx) for idx in struct1_indices_str]
        struct2_indices = [int(idx) for idx in struct2_indices_str]
        interactions = await Interaction.get(atom_idx=[*struct1_indices, *struct2_indices])
        return interactions

    def update_line(self, line):
        """Replace line stored in manager with updated version passed as arg."""
        structpair_key = self.get_structpair_key(*line.structure_indices)
        line_list = self._data[structpair_key]
        for i, stored_line in enumerate(line_list):
            if stored_line.index == line.index:
                line_list[i] = line
                break

    def update(self, line_manager):
        """"Merge another LineManager into self."""
        self._data.update(line_manager._data)

    async def persist_lines(self, interaction_data):
        """Persist lines in workspace."""
        current_lines = await Interaction.get()
        Interaction.destroy_multiple(current_lines)
        persistent_lines = []
        all_lines = await self.all_lines()
        for line in all_lines:
            atom1_index, atom2_index = [anchor.target for anchor in line.anchors]
            interaction_visible = interaction_data[line.interaction_type]['visible']
            if interaction_visible:
                interaction_kind = interaction_type_map[line.interaction_type]
                new_interaction = Interaction(interaction_kind, [atom1_index], [atom2_index])
                persistent_lines.append(new_interaction)
        await Interaction.upload_multiple(persistent_lines)
        Line.destroy_multiple(await self.all_lines())


class LabelManager(StructurePairManager):

    def all_labels(self):
        """Return a flat list of all lines being stored."""
        all_lines = []
        for structpair_key, label in sorted(self._data.items(), key=lambda keyval: keyval[0]):
            all_lines.append(self._data[structpair_key])
        return all_lines

    def add_label(self, label, struct1_index, struct2_index):
        if not isinstance(label, Label):
            raise TypeError(f'add_label() expected Label, received {type(label)}')
        structpair_key = self.get_structpair_key(struct1_index, struct2_index)
        self._data[structpair_key] = label

    def remove_label_for_structpair(self, struct1_index, struct2_index):
        """Remove all lines from data structure.

        Note that Shape.destroy() is not called, so lines still exist in workspace if uploaded.
        The label is returned, so that it can be destroyed at a later time.
        """
        key = self.get_structpair_key(struct1_index, struct2_index)
        label = None
        if key in self._data:
            label = self._data[key]
            del self._data[key]
        return label

    def clear(self):
        # Destroy all labels in workspace, and clear dict that's tracking them.
        Shape.destroy_multiple(self.all_labels())
        keys = list(self._data.keys())
        for key in keys:
            del self._data[key]

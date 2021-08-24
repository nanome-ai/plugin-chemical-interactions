from collections import defaultdict
from operator import attrgetter

from nanome.api.shapes import Label, Line, Shape
from nanome.api.structure import Atom
from nanome.util import Vector3


class InteractionStructure:
    """Abstraction representing one end of a chemical interaction.

    Typically is either a single Atom, or a ring of atoms.
    """

    def __init__(self, atom_or_atoms):
        """Pass in either a single Atom object or a list of Atoms."""
        if isinstance(atom_or_atoms, Atom):
            self.atoms.append(atom_or_atoms)
        elif isinstance(atom_or_atoms, list):
            self.atoms.extend(atom_or_atoms)

    @property
    def atoms(self):
        if not hasattr(self, '_atoms'):
            self._atoms = []
        return self._atoms

    def __iter__(self):
        return iter(self.atoms)

    @property
    def line_anchor(self):
        """Arbitrary atom in structure, but consistent."""
        return next(iter(sorted(self.atoms, key=attrgetter('index'))))

    @property
    def centroid(self):
        """Calculate center of the structure."""
        coords = [a.position.unpack() for a in self.atoms]
        sum_x = sum([vec[0] for vec in coords])
        sum_y = sum([vec[1] for vec in coords])
        sum_z = sum([vec[2] for vec in coords])
        len_coord = len(coords)
        centroid = Vector3(sum_x / len_coord, sum_y / len_coord, sum_z / len_coord)
        return centroid

    def calculate_local_offset(self):
        """Calculate offset to move line anchor to center of ring."""
        ring_center = self.centroid
        anchor_position = self.line_anchor.position
        offset_vector = Vector3(
            ring_center.x - anchor_position.x,
            ring_center.y - anchor_position.y,
            ring_center.z - anchor_position.z
        )
        return offset_vector


class InteractionLine(Line):
    """A Line with additional properties needed for representing interactions."""

    @staticmethod
    def centroid(coords):
        for i in range(0, len(coords)):
            vec = coords[i]
            coords[i] = vec.unpack()
        sum_x = sum([vec[0] for vec in coords])
        sum_y = sum([vec[1] for vec in coords])
        sum_z = sum([vec[2] for vec in coords])
        len_coord = len(coords)
        centroid = Vector3(sum_x / len_coord, sum_y / len_coord, sum_z / len_coord)
        return centroid

    def __init__(self, struct1, struct2, **kwargs):
        super().__init__()

        for kwarg, value in kwargs.items():
            if hasattr(self, kwarg):
                setattr(self, kwarg, value)

        if kwargs.get('visible') is False:
            self.color.a = 0

        self.frames = {}
        self.positions = {}
        # Set up frames and positions dict.
        # Skeptical if I need this. Revisit why this exists.
        for struct in [struct1, struct2]:
            struct_index = None
            struct_frame = None
            struct_position = None
            if isinstance(struct, Atom):
                struct_index = struct.index
                struct_frame = struct.frame
                struct_position = struct.position
            elif isinstance(struct, list):
                # Start by pointing to arbitrary atom in list
                struct_index = ','.join([str(a.index) for a in struct])
                # Frame should be the same on every Atom.
                struct_frame = struct[0].frame
                # Set an arbitrary atom position from the ring as the indicator here
                # When we render the line, we will account for offsetting to the ring center
                struct_position = struct[0].position
            self.frames[struct_index] = struct_frame
            self.atom_positions[struct_index] = struct_position

    @property
    def interaction_type(self):
        """The type of interaction this line is representing. See forms.InteractionsForm for valid values."""
        if not hasattr(self, '_interaction_type'):
            self._interaction_type = ''
        return self._interaction_type

    @interaction_type.setter
    def interaction_type(self, value):
        self._interaction_type = value

    @property
    def frames(self):
        """Dict where key is atom index and value is current frame of the atom's complex."""
        if not hasattr(self, '_frames'):
            self._frames = {}
        return self._frames

    @frames.setter
    def frames(self, value):
        if not isinstance(value, dict):
            raise AttributeError(f'InteractionLine.frames expects dict, received {type(value)}')
        self._frames = value

    @property
    def atom_positions(self):
        """Dict where key is atom index and value is last known (x, y, z) coordinates of atom."""
        if not hasattr(self, '_atom_positions'):
            self._atom_positions = {}
        return self._atom_positions

    @atom_positions.setter
    def atom_positions(self, value):
        """Dict where key is atom index and value is a Vector3 of last known coordinates of atom."""
        if not isinstance(value, dict) or len(value) != 2 or not all([isinstance(pos, Vector3) for pos in value.values()]):
            raise AttributeError('Invalid atom positions provided: {value}')
        self._atom_positions = value

    @property
    def length(self):
        """Determine length of line using the distance between the atoms."""
        positions = self.atom_positions.values()
        distance = Vector3.distance(*positions)
        return distance


class AtomPairManager:

    @staticmethod
    def get_atompair_key(*atom_indices):
        """Return a string key for the given atom indices."""
        atom_key = '-'.join(sorted([str(index) for index in atom_indices]))
        return atom_key

    def get_atom_pairs(self):
        """Return a list of atom_pairs being tracked by manager."""
        atom_pairs = []
        for atompair_key in self._data:
            atom1_index, atom2_index = atompair_key.split('-')
            atom_pairs.append((atom1_index, atom2_index))
        return atom_pairs


class LineManager(AtomPairManager):
    """Organizes Interaction lines by atom pairs."""

    def __init__(self):
        super().__init__()
        self._data = defaultdict(list)

    def all_lines(self):
        """Return a flat list of all lines being stored."""
        all_lines = []
        for atompair_key, line_list in sorted(self._data.items(), key=lambda keyval: keyval[0]):
            all_lines.extend(line_list)
        return all_lines

    def add_lines(self, line_list):
        for line in line_list:
            self.add_line(line)

    def add_line(self, line):
        if not isinstance(line, InteractionLine):
            raise TypeError(f'add_line() expected InteractionLine, received {type(line)}')
        targets = [anchor.target for anchor in line.anchors]

        for i in range(0, len(targets)):
            if isinstance(targets[i], Atom):
                targets[i] = str(targets[i].index)
            if isinstance(targets[i], list):
                targets[i] = ','.join([str(a.index) for a in targets[i]])
        atompair_key = self.get_atompair_key(*targets)
        self._data[atompair_key].append(line)

    def get_lines_for_atompair(self, struct1, struct2):
        """Given two InteractionStructures, return all interaction lines connecting them.

        Accepts either Atom objects or index values, or a list of Atoms representing an aromatic ring.
        """
        indices = []
        for struct in [struct1, struct2]:
            struct_index = None
            atom_indices = sorted([str(a.index) for a in struct])
            struct_index = ','.join(atom_indices)
            indices.append(struct_index)
        key = self.get_atompair_key(*indices)
        return self._data[key]

    def update_line(self, line):
        """Replace line stored in manager with updated version passed as arg."""
        atom1_index, atom2_index = [anchor.target for anchor in line.anchors]
        atompair_key = self.get_atompair_key(atom1_index, atom2_index)
        line_list = self._data[atompair_key]
        for i, stored_line in enumerate(line_list):
            if stored_line.index == line.index:
                line_list[i] = line
                break

    def update(self, line_manager):
        """"Merge another LineManager into self."""
        self._data.update(line_manager._data)


class LabelManager(AtomPairManager):

    def __init__(self):
        super().__init__()
        self._data = defaultdict(None)

    def all_labels(self):
        """Return a flat list of all lines being stored."""
        all_lines = []
        for atompair_key, label in sorted(self._data.items(), key=lambda keyval: keyval[0]):
            all_lines.append(self._data[atompair_key])
        return all_lines

    def add_label(self, label):
        if not isinstance(label, Label):
            raise TypeError(f'add_label() expected Label, received {type(label)}')
        atom1_index, atom2_index = [anchor.target for anchor in label.anchors]
        atompair_key = self.get_atompair_key(atom1_index, atom2_index)
        self._data[atompair_key] = label

    def remove_label_for_atompair(self, atom1_index, atom2_index):
        """Remove all lines from data structure.

        Note that Shape.destroy() is not called, so lines still exist in workspace if uploaded.
        The label is returned, so that it can be destroyed at a later time.
        """
        key = self.get_atompair_key(atom1_index, atom2_index)
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

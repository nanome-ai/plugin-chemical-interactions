from collections import defaultdict

from nanome.api.shapes import Line
from nanome.util import Color, Vector3


class InteractionLine(Line):
    """A Line with additional properties needed for representing interactions."""

    def __init__(
        self, atom1, atom2, **kwargs):
        super().__init__()

        for kwarg, value in kwargs.items():
            if hasattr(self, kwarg):
                setattr(self, kwarg, value)

        if kwargs.get('visible') is False:
            self.color.a = 0

        self.frames = {
            atom1.index: atom1.frame,
            atom2.index: atom2.frame,
        }

        self.atom_positions = {
            atom1.index: atom1.position,
            atom2.index: atom2.position
        }
        pass

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


class LineManager(defaultdict):
    """Organizes Interaction lines by atom pairs."""
    
    def __init__(self):
        default_val = list
        self.labels = []
        super().__init__(default_val)

    @staticmethod
    def get_atompair_key(atom1_index, atom2_index):
        atom_key = '-'.join(sorted([str(atom1_index), str(atom2_index)]))
        return atom_key

    def all_lines(self):
        """Return a flat list of all lines being stored."""
        all_lines = []
        for key, val in self.items():
            all_lines.extend(val)
        return all_lines

    def add_lines(self, line_list):
        for line in line_list:
            self.add_line(line)

    def add_line(self, line):
        if not isinstance(line, InteractionLine):
            raise TypeError(f'add_line() expected InteractionLine, received {type(line)}')
        atom1_index, atom2_index = [anchor.target for anchor in line.anchors]
        atompair_key = self.get_atompair_key(atom1_index, atom2_index)
        self[atompair_key].append(line)

    def get_lines_for_atompair(self, atom1, atom2):
        key = self.get_atompair_key(atom1.index, atom2.index)
        return self[key]

    def update_line(self, line):
        """Replace line stored in manager with updated version passed as arg."""
        atom1_index, atom2_index = [anchor.target for anchor in line.anchors]
        atompair_key = self.get_atompair_key(atom1_index, atom2_index)
        line_list = self[atompair_key]
        for i, stored_line in enumerate(line_list):
            if stored_line.index == line.index:
                line_list[i] = line
                break
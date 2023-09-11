from operator import attrgetter

from nanome.api.shapes import Line
from nanome.api.structure import Atom
from nanome.util import Vector3, Logs


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
    def line_anchor(self):
        """Arbitrary atom in structure, but consistent."""
        return next(iter(sorted(self.atoms, key=attrgetter('index'))))

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


class InteractionShapesLine(Line):
    """A Line with additional properties needed for representing interactions."""

    def __init__(self, struct1, struct2, **kwargs):
        super().__init__()

        for kwarg, value in kwargs.items():
            if hasattr(self, kwarg):
                setattr(self, kwarg, value)

        if kwargs.get('visible') is False:
            self.color.a = 0

        # Set up frames, conformers, and positions dict.
        for struct in [struct1, struct2]:
            struct_position = struct.line_anchor.position
            self.frames[struct.index] = struct.frame
            self.conformers[struct.index] = struct.conformer
            self.struct_positions[struct.index] = struct_position
        # Save atom_indices to be interchangeable with Interaction objects
        self.atom1_idx_arr = [str(atm.index) for atm in struct1.atoms]
        self.atom2_idx_arr = [str(atm.index) for atm in struct2.atoms]

    @property
    def kind(self):
        """The type of interaction this line is representing. See forms.LineSettingsForm for valid values."""
        if not hasattr(self, '_kind'):
            self._kind = ''
        return self._kind

    @kind.setter
    def kind(self, value):
        self._kind = value

    @property
    def frames(self):
        """Dict where key is structure index and value is current frame of the atom's complex."""
        if not hasattr(self, '_frames'):
            self._frames = {}
        return self._frames

    @property
    def conformers(self):
        """Dict where key is structure index and value is current conformer of the atom's molecule."""
        if not hasattr(self, '_conformers'):
            self._conformers = {}
        return self._conformers

    @property
    def struct_positions(self):
        """Dict where key is structure index and value is last known (x, y, z) coordinates of Structure."""
        if not hasattr(self, '_struct_positions'):
            self._struct_positions = {}
        return self._struct_positions

    @property
    def length(self):
        """Determine length of line using the distance between the structures."""
        positions = []
        for anchor in self.anchors:
            struct_key = next(struc_key for struc_key in self.structure_indices if str(anchor.target) in struc_key)
            position = self.struct_positions[struct_key] + anchor.local_offset
            positions.append(position)
        distance = Vector3.distance(*positions)
        return distance

    @property
    def structure_indices(self):
        """Return a list of struture indices."""
        return self.frames.keys()

    @property
    def visible(self):
        return self.color.a > 0

    @visible.setter
    def visible(self, value: bool):
        if value:
            self.color.a = 1
        else:
            self.color.a = 0

    @property
    def atom1_conformation(self):
        """Return the conformer of the atom in the second structure."""
        try:
            atom_index = str(self.atom1_idx_arr[0])
            conformer_key = next(key for key in self.conformers.keys() if str(atom_index) in key)
            return self.conformers[conformer_key]
        except IndexError:
            Logs.warning("atom1_idx_arr is empty")

    @property
    def atom2_conformation(self):
        """Return the conformer of the atom in the second structure."""
        try:
            atom_index = str(self.atom2_idx_arr[0])
            conformer_key = next(key for key in self.conformers.keys() if str(atom_index) in key)
            return self.conformers[conformer_key]
        except IndexError:
            Logs.warning("atom2_idx_arr is empty")

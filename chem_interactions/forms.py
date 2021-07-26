from os import path
from nanome.api.shapes import Line
from nanome.util import Color, Vector3
from wtforms import BooleanField, Field, FloatField, Form, FormField
from wtforms.fields.core import StringField


BASE_PATH = path.dirname(path.realpath(__file__))


class InteractionLine(Line):
    """A Line with additional properties needed for tracking interactions."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._interaction_type = None
        self._frames = {}
        self._atom_positions = {}

    @property
    def interaction_type(self):
        """The type of interaction this line is representing. See forms.InteractionsForm for valid values."""
        return self._interaction_type
    
    @interaction_type.setter
    def interaction_type(self, value):
        self._interaction_type = value

    @property
    def frames(self):
        """Dict where key is atom index and value is current frame of the atom's complex."""
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
        distance = Vector3.distance(positions[0], positions[1])
        return distance

color_map = {
    "red": (255, 0, 0),
    "orange": (255, 128, 0),
    "yellow": (255, 255, 0),
    "green": (0, 128, 0),
    "blue": (0, 0, 255),
    "indigo": (75, 0, 130),
    "violet": (238, 130, 238),
    "black": (0, 0, 0),
    "plum": (221, 160, 221),
    "white": (255, 255, 255),
    "maroon": (128, 0, 0),
    "cyan": (0, 204, 230),
    "slategrey": (112, 128, 144),
    "purple": (177, 156, 217),
    "grey": (192, 192, 192),
    "sienna": (160, 82, 45),
    "brown": (165, 42, 42),
    "lavender": (230, 230, 250),
    "magenta": (255, 0, 255),
    "steelblue": (88, 88, 167)
}


class NanomeColorField(Field):

    def process(self, *args, **kwargs):
        super().process(*args, **kwargs)
        if self.data and not isinstance(self.data, Color):
            self.data = Color(*self.data)


class LineForm(Form):
    """Settings used to create a Line shape."""

    visible = BooleanField(default=True)
    color = NanomeColorField()
    thickness = FloatField(default=0.1)
    dash_length = FloatField(default=0.25)
    dash_distance = FloatField(default=0.25)
    interaction_type = StringField()

    def create(self):
        line = InteractionLine()
        for attr, value in self.data.items():
            if hasattr(line, attr):
                setattr(line, attr, value)

        if not self.data['visible']:
            line.color.a = 0
        return line


# If you want to change the default line settings, update here
default_line_settings = {
    'covalent': {'visible': True, 'color': color_map['yellow']},
    'hbond': {'visible': True, 'color': color_map['cyan']},
    'ionic': {'visible': True, 'color': color_map['red']},
    'xbond': {'visible': True, 'color': color_map['green']},
    'metal_complex': {'visible': True, 'color': color_map['grey']},
    'aromatic': {'visible': True, 'color': color_map['magenta']},
    'hydrophobic': {'visible': False, 'color': color_map['purple'], 'dash_length': .1},
    'vdw': {'visible': False, 'color': color_map['sienna']},
    'vdw_clash': {'visible': False, 'color': color_map['maroon']},
    'weak_hbond': {'visible': False, 'color': color_map['orange']},
    'polar': {'visible': False, 'color': color_map['blue']},
    'weak_polar': {
        'visible': False,
        'color': color_map['steelblue'],
        'dash_thickness': .8,
        'dash_distance': .4,
        'dash_length': .1
    },
    'clash': {'visible': False, 'color': color_map['white']},
    'carbonyl': {'visible': False, 'color': color_map['slategrey']},
    # 'proximal': {'visible': False, 'color': color_map['lavender']},
}


class InteractionsForm(Form):
    """Set colors and visibility for supported Interaction types."""
    covalent = FormField(LineForm, label='Covalent', default=default_line_settings['covalent'])
    hbond = FormField(LineForm, label='Hydrogen Bond', default=default_line_settings['hbond'])
    ionic = FormField(LineForm, label='Ionic', default=default_line_settings['ionic'])
    xbond = FormField(LineForm, label='Halogen', default=default_line_settings['xbond'])
    metal_complex = FormField(LineForm, label='Metal Complex', default=default_line_settings['metal_complex'])
    aromatic = FormField(LineForm, label='Pi-Pi Aromatic', default=default_line_settings['aromatic'])
    hydrophobic = FormField(LineForm, label='Hydrophobic', default=default_line_settings['hydrophobic'])
    vdw = FormField(LineForm, label='VDW', default=default_line_settings['vdw'])
    vdw_clash = FormField(LineForm, label='VDW Clash', default=default_line_settings['vdw_clash'])
    weak_hbond = FormField(LineForm, label='Weak Hydrogen', default=default_line_settings['weak_hbond'])
    polar = FormField(LineForm, label='Polar', default=default_line_settings['polar'])
    weak_polar = FormField(LineForm, label='Weak Polar', default=default_line_settings['weak_polar'])
    clash = FormField(LineForm, label='Clash', default=default_line_settings['clash'])
    carbonyl = FormField(LineForm, label='Carbonyl', default=default_line_settings['carbonyl'])
    # proximal = FormField(LineForm, label='Proximal', default=default_line_settings['proximal'])

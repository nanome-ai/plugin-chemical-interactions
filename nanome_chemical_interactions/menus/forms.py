from os import path
from nanome.api.shapes import Line
from nanome.util import Color
from wtforms import BooleanField, Field, FloatField, Form, FormField


BASE_PATH = path.dirname(path.realpath(__file__))

color_map = {
    "red": (255, 0, 0),
    "orange": (217, 91, 0),
    "yellow": (255, 255, 0),
    "green": (0, 128, 0),
    "blue": (0, 0, 255),
    "indigo": (75, 0, 130),
    "violet": (238, 130, 238),
    "black": (0, 0, 0),
    "plum": (221, 160, 221),
    "white": (255, 255, 255),
    "maroon": (128, 0, 0),
    "cyan": (0, 255, 255),
    "slategrey": (112, 128, 144),
    "purple": (104, 0, 104),
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

    def create(self):
        line = Line()
        for attr, value in self.data.items():
            if hasattr(line, attr):
                setattr(line, attr, value)
        return line


disc_line_settings = dict(thickness=0.2, dash_length=0.1, dash_distance=0.25)
interaction_settings = {
    'covalent': {'visible': True, 'color': color_map['yellow']},
    'hbond': {'visible': True, 'color': color_map['blue']},
    'ionic': {'visible': True, 'color': color_map['red']},
    'xbond': {'visible': True, 'color': color_map['green']},
    'metal_complex': {'visible': True, 'color': color_map['grey']},
    'aromatic': {'visible': True, 'color': color_map['magenta']},
    'hydrophobic': {'visible': False, 'color': color_map['purple'], **disc_line_settings},
    'vdw': {'visible': False, 'color': color_map['sienna']},
    'vdw_clash': {'visible': False, 'color': color_map['plum']},
    'weak_hbond': {'visible': False, 'color': color_map['orange']},
    'polar': {'visible': False, 'color': color_map['cyan']},
    'weak_polar': {'visible': False, 'color': color_map['steelblue']},
    'clash': {'visible': False, 'color': color_map['white']},
    'carbonyl': {'visible': False, 'color': color_map['slategrey']},
    # 'proximal': {'visible': True, 'color': color_map['lavender']},
}


class InteractionsForm(Form):
    """Set colors and visibility for supported Interaction types."""
    covalent = FormField(LineForm, label='Covalent', default=interaction_settings['covalent'])
    hbond = FormField(LineForm, label='Hydrogen Bond', default=interaction_settings['hbond'])
    ionic = FormField(LineForm, label='Ionic', default=interaction_settings['ionic'])
    xbond = FormField(LineForm, label='Halogen', default=interaction_settings['xbond'])
    metal_complex = FormField(LineForm, label='Metal Complex', default=interaction_settings['metal_complex'])
    aromatic = FormField(LineForm, label='Pi-Pi Aromatic', default=interaction_settings['aromatic'])
    hydrophobic = FormField(LineForm, label='Hydrophobic', default=interaction_settings['hydrophobic'])
    vdw = FormField(LineForm, label='VDW', default=interaction_settings['vdw'])
    vdw_clash = FormField(LineForm, label='VDW Clash', default=interaction_settings['vdw_clash'])
    weak_hbond = FormField(LineForm, label='Weak Hydrogen', default=interaction_settings['weak_hbond'])
    polar = FormField(LineForm, label='Polar', default=interaction_settings['polar'])
    weak_polar = FormField(LineForm, label='Weak Polar', default=interaction_settings['weak_polar'])
    clash = FormField(LineForm, label='Clash', default=interaction_settings['clash'])
    carbonyl = FormField(LineForm, label='Carbonyl', default=interaction_settings['carbonyl'])
    # proximal = FormField(LineForm, label='Proximal', default=interaction_settings['proximal'])

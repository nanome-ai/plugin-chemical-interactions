from models import InteractionLine
from nanome.util import Color
from wtforms import BooleanField, Field, FloatField, Form, FormField
from wtforms.fields.core import StringField


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
    'aromatic': {
        'visible': True,
        'color': color_map['magenta'],
        'dash_thickness': 0.09,
        'dash_distance': 0.5,
        'dash_length': 0.18
    },
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
    'CARBONPI': {'visible': True, 'dash_thickness': 0.4, 'dash_length': 0.1, 'dash_distance': 0.6, 'color': color_map['red']},
    'CATIONPI': {'visible': True, 'dash_thickness': 0.4, 'dash_length': 0.1, 'dash_distance': 0.6, 'color': color_map['orange']},
    'DONORPI': {'visible': True, 'dash_thickness': 0.4, 'dash_length': 0.1, 'dash_distance': 0.6, 'color': color_map['yellow']},
    'HALOGENPI': {'visible': True, 'dash_thickness': 0.4, 'dash_length': 0.1, 'dash_distance': 0.6, 'color': color_map['green']},
    'METSULPHURPI': {'visible': True, 'dash_thickness': 0.4, 'dash_length': 0.1, 'dash_distance': 0.6, 'color': color_map['blue']},
    # 'proximal': {'visible': False, 'color': color_map['lavender']},
}


class LineSettingsForm(Form):
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
    CARBONPI = FormField(LineForm, label='Carbon-PI', default=default_line_settings['CARBONPI'])
    CATIONPI = FormField(LineForm, label='Cation-PI', default=default_line_settings['CATIONPI'])
    DONORPI = FormField(LineForm, label='Donor-PI', default=default_line_settings['DONORPI'])
    HALOGENPI = FormField(LineForm, label='Halogen-PI', default=default_line_settings['HALOGENPI'])
    METSULPHURPI = FormField(LineForm, label='Sulphur-PI', default=default_line_settings['METSULPHURPI'])
    # proximal = FormField(LineForm, label='Proximal', default=default_line_settings['proximal'])

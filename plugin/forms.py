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
    dash_length = FloatField(default=0.2)
    dash_distance = FloatField(default=0.25)
    kind = StringField()


# If you want to change the default line settings, update here
default_line_settings = {
    'Covalent': {'visible': True, 'color': color_map['yellow']},
    'HydrogenBond': {'visible': True, 'color': color_map['cyan']},
    'Ionic': {'visible': True, 'color': color_map['red']},
    'XBond': {'visible': True, 'color': color_map['green']},
    'MetalComplex': {'visible': True, 'color': color_map['grey']},
    'Aromatic': {
        'visible': True,
        'color': color_map['magenta'],
        'thickness': 0.09,
        'dash_distance': 0.5,
        'dash_length': 0.18
    },
    'Hydrophobic': {'visible': False, 'color': color_map['purple'], 'dash_length': 0.07, 'thickness': 0.12, "dash_distance": 0.4},
    'VanDerWall': {'visible': False, 'color': color_map['sienna']},
    'VanDerWallClash': {'visible': False, 'color': color_map['maroon']},
    'WeakHBond': {'visible': False, 'color': color_map['orange']},
    'Polar': {'visible': False, 'color': color_map['blue']},
    'WeakPolar': {
        'visible': False,
        'color': color_map['steelblue'],
        'thickness': 0.12,
        'dash_distance': 0.4,
        'dash_length': 0.1
    },
    'Clash': {'visible': False, 'color': color_map['white']},
    'Carbonyl': {'visible': False, 'color': color_map['slategrey']},
    'CarbonPi': {'visible': False, 'thickness': 0.07, 'dash_length': 0.1, 'dash_distance': 0.3, 'color': color_map['red']},
    'CationPi': {'visible': False, 'thickness': 0.07, 'dash_length': 0.1, 'dash_distance': 0.3, 'color': color_map['orange']},
    'DonorPi': {'visible': False, 'thickness': 0.07, 'dash_length': 0.1, 'dash_distance': 0.3, 'color': color_map['yellow']},
    'HalogenPi': {'visible': False, 'thickness': 0.07, 'dash_length': 0.1, 'dash_distance': 0.3, 'color': color_map['green']},
    'MetsulphurPi': {'visible': False, 'thickness': 0.07, 'dash_length': 0.1, 'dash_distance': 0.3, 'color': color_map['blue']},
    # 'Proximal': {'visible': False, 'color': color_map['lavender']},
}


class LineSettingsForm(Form):
    """Set colors and visibility for supported Interaction types."""
    Covalent = FormField(LineForm, label='Covalent', default=default_line_settings['Covalent'])
    HydrogenBond = FormField(LineForm, label='Hydrogen Bond', default=default_line_settings['HydrogenBond'])
    Ionic = FormField(LineForm, label='Ionic', default=default_line_settings['Ionic'])
    XBond = FormField(LineForm, label='Halogen', default=default_line_settings['XBond'])
    MetalComplex = FormField(LineForm, label='Metal Complex', default=default_line_settings['MetalComplex'])
    Aromatic = FormField(LineForm, label='Pi-Pi Aromatic', default=default_line_settings['Aromatic'])
    Hydrophobic = FormField(LineForm, label='Hydrophobic', default=default_line_settings['Hydrophobic'])
    VanDerWall = FormField(LineForm, label='VDW', default=default_line_settings['VanDerWall'])
    VanDerWallClash = FormField(LineForm, label='VDW Clash', default=default_line_settings['VanDerWallClash'])
    WeakHBond = FormField(LineForm, label='Weak Hydrogen', default=default_line_settings['WeakHBond'])
    Polar = FormField(LineForm, label='Polar', default=default_line_settings['Polar'])
    WeakPolar = FormField(LineForm, label='Weak Polar', default=default_line_settings['WeakPolar'])
    Clash = FormField(LineForm, label='Clash', default=default_line_settings['Clash'])
    Carbonyl = FormField(LineForm, label='Carbonyl', default=default_line_settings['Carbonyl'])
    CarbonPi = FormField(LineForm, label='Carbon-PI', default=default_line_settings['CarbonPi'])
    CationPi = FormField(LineForm, label='Cation-PI', default=default_line_settings['CationPi'])
    DonorPi = FormField(LineForm, label='Donor-PI', default=default_line_settings['DonorPi'])
    HalogenPi = FormField(LineForm, label='Halogen-PI', default=default_line_settings['HalogenPi'])
    MetsulphurPi = FormField(LineForm, label='Sulphur-PI', default=default_line_settings['MetsulphurPi'])
    # Proximal = FormField(LineForm, label='Proximal', default=default_line_settings['proximal'])

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
    "plum": (221, 160, 22),
    "white": (255, 255, 255),
    "maroon": (128, 0, 0),
    "darkcyan": (0, 139, 139),
    "slategrey": (112, 128, 144),
    "purple": (128, 0, 128),
    "grey": (192, 192, 192),
    "sienna": (160, 82, 45),
    "brown": (165, 42, 42),
    "lavender": (230, 230, 250),
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


def default_data(color_name, visible=True, **kwargs):
    """Set line attributes requested for each interaction type."""
    color_rgb = color_map[color_name]
    data = {
        'visible': visible,
        'color': color_rgb,
        **kwargs
    }
    return data


class InteractionsForm(Form):
    """Set colors and visibility for supported Interaction types."""

    covalent = FormField(LineForm, label='Covalent', default=default_data('yellow'))
    hbond = FormField(LineForm, label='Hydrogen Bond', default=default_data('blue'))
    ionic = FormField(LineForm, label='Ionic', default=default_data('red'))
    xbond = FormField(LineForm, label='Halogen', default=default_data('green'))
    metal_complex = FormField(LineForm, label='Metal Complex', default=default_data('orange'))
    aromatic = FormField(LineForm, label='Pi-Pi Aromatic', default=default_data('grey'))

    hydrophobic = FormField(
        LineForm, label='Hydrophobic',
        default=default_data('purple', thickness=0.2, dash_length=0.1, dash_distance=0.25))

    vdw = FormField(LineForm, label='VDW', default=default_data('sienna'))
    vdw_clash = FormField(LineForm, label='VDW Clash', default=default_data('plum'))
    weak_hbond = FormField(LineForm, label='Weak Hydrogen', default=default_data('black'))
    polar = FormField(LineForm, label='Polar', default=default_data('darkcyan'))
    weak_polar = FormField(LineForm, label='Weak Polar', default=default_data('brown'))
    clash = FormField(LineForm, label='Clash', default=default_data('white'))
    carbonyl = FormField(LineForm, label='Carbonyl', default=default_data('slategrey'))
    proximal = FormField(LineForm, label='Proximal', default=default_data('lavender', False))

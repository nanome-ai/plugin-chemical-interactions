from os import path
from nanome.util import Color
from wtforms import BooleanField, Field, Form, FormField

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
        if self.data:
            self.data = Color(*self.data)


class InteractionSettings(Form):
    """Settings that can be changed for each interaction_type."""
    visible = BooleanField(default=True)
    color = NanomeColorField()


def default_data(color_name, visible=True):
    """Use color name from color_map above to set default colors."""
    color_rgb = color_map[color_name]
    return {
        'visible': visible,
        'color': color_rgb
    }


class InteractionsForm(Form):
    """Set colors and visibility for supported Interaction types."""

    covalent = FormField(InteractionSettings, label='Covalent', default=default_data('yellow'))
    hbond = FormField(InteractionSettings, label='Hydrogen Bond', default=default_data('blue'))
    ionic = FormField(InteractionSettings, label='Ionic', default=default_data('red'))
    xbond = FormField(InteractionSettings, label='Halogen', default=default_data('green'))
    metal_complex = FormField(InteractionSettings, label='Metal Complex', default=default_data('orange'))
    aromatic = FormField(InteractionSettings, label='Pi-Pi Aromatic', default=default_data('grey'))
    hydrophobic = FormField(InteractionSettings, label='Hydrophobic', default=default_data('purple'))
    vdw = FormField(InteractionSettings, label='VDW', default=default_data('sienna'))
    vdw_clash = FormField(InteractionSettings, label='VDW Clash', default=default_data('plum'))
    weak_hbond = FormField(InteractionSettings, label='Weak Hydrogen', default=default_data('black'))
    polar = FormField(InteractionSettings, label='Polar', default=default_data('darkcyan'))
    weak_polar = FormField(InteractionSettings, label='Weak Polar', default=default_data('brown'))
    clash = FormField(InteractionSettings, label='Clash', default=default_data('white'))
    carbonyl = FormField(InteractionSettings, label='Carbonyl', default=default_data('slategrey'))
    proximal = FormField(InteractionSettings, label='Proximal', default=default_data('lavender', False))

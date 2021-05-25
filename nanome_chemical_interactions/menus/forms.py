from os import path
from nanome.util import Color
from wtforms import BooleanField, Field, Form, FormField

BASE_PATH = path.dirname(path.realpath(__file__))
color_map = {
    "red": (255, 0, 0),
    "orange": (255, 165, 0),
    "yellow": (255, 255, 0),
    "green": (0, 128, 0),
    "blue": (0, 0, 255),
    "indigo": (75, 0, 130),
    "violet": (238, 130, 238),
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "mediumspringgreen": (0, 250, 154),
    "maroon": (128, 0, 0),
    "darkcyan": (0, 139, 139),
    "slategray": (112, 128, 144),
    "purple": (128, 0, 128),
    "gray": (128, 128, 128),
    "sienna": (160, 82, 45),
    "brown": (165, 42, 42),
    "lavender": (230, 230, 250),
    "plum": (221, 160, 22)
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


def default_data(color_name):
    """Use color name from color_map above to set default colors."""
    color_rgb = color_map[color_name]
    return {
        'visible': True,
        'color': color_rgb
    }


class InteractionsForm(Form):
    """Set colors and visibility for supported Interaction types."""
    clash = FormField(InteractionSettings, default=default_data('white'))
    covalent = FormField(InteractionSettings, default=default_data('red'))
    vdw_clash = FormField(InteractionSettings, default=default_data('orange'))
    vdw = FormField(InteractionSettings, default=default_data('yellow'))
    proximal = FormField(InteractionSettings, default=default_data('green'))
    hbond = FormField(InteractionSettings, default=default_data('blue'))
    weak_hbond = FormField(InteractionSettings, default=default_data('indigo'))
    xbond = FormField(InteractionSettings, default=default_data('violet'))
    ionic = FormField(InteractionSettings, default=default_data('black'))
    metal_complex = FormField(InteractionSettings, default=default_data('mediumspringgreen'))
    aromatic = FormField(InteractionSettings, default=default_data('maroon'))
    hydrophobic = FormField(InteractionSettings, default=default_data('darkcyan'))
    carbonyl = FormField(InteractionSettings, default=default_data('slategray'))
    polar = FormField(InteractionSettings, default=default_data('purple'))
    weak_polar = FormField(InteractionSettings, default=default_data('brown'))

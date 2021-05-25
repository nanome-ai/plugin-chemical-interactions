from os import path
from nanome.util import Color
from wtforms import BooleanField, Field, Form, FormField
from wtforms_components import ColorField
from colour import Color as ExternalColor

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


def default_values(color_name):
    """Use color name from color_map above to set default colors."""
    color = Color(*color_map[color_name])
    color_rep = (color.r, color.g, color.b)
    return {
        'visible': True,
        'color':  color_rep
    }

 
class InteractionsForm(Form):
    """Set colors and visibility for supported Interaction types."""
    clash = FormField(InteractionSettings, default=default_values('white'))
    covalent = FormField(InteractionSettings, default=default_values('red'))
    vdw_clash = FormField(InteractionSettings, default=default_values('orange'))
    vdw = FormField(InteractionSettings, default=default_values('yellow'))
    proximal = FormField(InteractionSettings, default=default_values('green'))
    hbond = FormField(InteractionSettings, default=default_values('blue'))
    weak_hbond = FormField(InteractionSettings, default=default_values('indigo'))
    xbond = FormField(InteractionSettings, default=default_values('violet'))
    ionic = FormField(InteractionSettings, default=default_values('black'))
    metal_complex = FormField(InteractionSettings, default=default_values('mediumspringgreen'))
    aromatic = FormField(InteractionSettings, default=default_values('maroon'))
    hydrophobic = FormField(InteractionSettings, default=default_values('darkcyan'))
    carbonyl = FormField(InteractionSettings, default=default_values('slategray'))
    polar = FormField(InteractionSettings, default=default_values('purple'))
    weak_polar = FormField(InteractionSettings, default=default_values('brown'))


from os import path
from nanome.util import Color
from wtforms import BooleanField, Field, Form, FormField
from wtforms_components import ColorField
from colour import Color as ExternalColor

BASE_PATH = path.dirname(path.realpath(__file__))


class NanomeColorField(Field):
    """Extend Wtforms  ColorField to convert data into Nanome color class."""

    def process(self, *args, **kwargs):
        super().process(*args, **kwargs)
        external_color = ExternalColor(self.data)
        self.data = Color(*external_color.rgb)
        pass


class InteractionColorForm(Form):
    """Set colors for supported Interaction types."""
    clash = NanomeColorField()


class InteractionSettings(Form):
    """Settings that can be changed for each interaction_type."""
    visible = BooleanField(default=True)
    color = NanomeColorField()

 
class InteractionsForm(Form):
    """Set colors and visibility for supported Interaction types."""
    clash = FormField(InteractionSettings)
    covalent = FormField(InteractionSettings)
    vdw_clash = FormField(InteractionSettings)
    # vdw = FormField(InteractionSettings)
    # proximal = FormField(InteractionSettings)
    # hbond = FormField(InteractionSettings)
    # weak_hbond = FormField(InteractionSettings)
    # xbond = FormField(InteractionSettings)
    # ionic = FormField(InteractionSettings)
    # metal_complex = FormField(InteractionSettings)
    # aromatic = FormField(InteractionSettings)
    # hydrophobic = FormField(InteractionSettings)
    # carbonyl = FormField(InteractionSettings)
    # polar = FormField(InteractionSettings)
    # weak_polar = FormField(InteractionSettings)


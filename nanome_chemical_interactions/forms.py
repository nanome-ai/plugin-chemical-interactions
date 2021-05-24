from wtforms import Form, FileField, StringField
from nanome.util import Color
from wtforms_components import ColorField


class NanomeColorField(ColorField):
    """Extend Wtforms ColorField to convert data into Nanome color class."""

    def process(self, _, value, **kwargs):
        # Leverage ColorField process_formdata to create generic Color object
        self.process_formdata([value])
        # Convert to Nanome color
        self.data = Color(*self.data.rgb)


class InteractionColorForm(Form):
    """Set colors for supported Interaction types."""
    clash = NanomeColorField()
    # covalent = StringField()
    # vdw_clash = StringField()
    # vdw = StringField()
    # proximal = StringField()
    # hbond = StringField()
    # weak_hbond = StringField()
    # xbond = StringField()
    # ionic = StringField()
    # metal_complex = StringField()
    # aromatic = StringField()
    # hydrophobic = StringField()
    # carbonyl = StringField()
    # polar = StringField()
    # weak_polar = StringField()


class ChemicalInteractionsForm(Form):
    input_file = FileField()
    atom_paths = StringField(description='Comma separated list of atom_paths (e.g. /C/100/O,C/45/H)')

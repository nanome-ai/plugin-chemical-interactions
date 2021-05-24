from wtforms import Form, Field, FileField, StringField
from nanome.util import Color
from colour import Color as ExternalColor
from wtforms_components import ColorField


class NanomeColorField(Field):
    """Extend Wtforms  ColorField to convert data into Nanome color class."""

    def process(self, *args, **kwargs):
        import pdb; pdb.set_trace()
        super().process(*args, **kwargs)
        external_color = ExternalColor(self.data)
        self.data = Color(*external_color.rgb)
        pass


class InteractionColorForm(Form):
    """Set colors for supported Interaction types."""
    clash = NanomeColorField()

    def process(self, *args, **kwargs):
        return super().process(*args, **kwargs)
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

from wtforms import Form, FileField, StringField
from wtforms import validators
from wtforms.fields.core import StringField


class ChemicalInteractionsForm(Form):
    input_file = FileField()
    # input_file = FileField('Cleaned PDB file', )
    atom_paths = StringField()

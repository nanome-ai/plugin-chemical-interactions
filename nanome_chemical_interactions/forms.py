from wtforms import Form, FileField, StringField

class ChemicalInteractionsForm(Form):
    input_file = FileField()
    atom_paths = StringField(description='Comma separated list of atom_paths (e.g. /C/100/O,C/45/H)')

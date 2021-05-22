from wtforms import Form, SelectMultipleField, StringField
from wtforms.validators import DataRequired


class ChemicalInteractionsForm(Form):
    complexes = SelectMultipleField(
        coerce=int,
        validators=[DataRequired()],
        description='index of complex we will be analyzing.',
        choices=[(1, 1), (2, 2), (3, 3)])
    atom_paths = StringField(description="comma separated list list atom paths ex `/C/100/O,/A/20/CO`")

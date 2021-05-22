from wtforms import Form, IntegerField, SelectMultipleField
from wtforms.validators import DataRequired


class ChemicalInteractionsForm(Form):

    def __init__(self, *args, complex_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        complex_choices = complex_choices or []
        self.complexes.choices = [(i, i) for i in complex_choices]

    complexes = SelectMultipleField(
        coerce=int,
        validators=[DataRequired()],
        description='index of complex we will be analyzing.',
        choices=[(1, 1), (2, 2), (3, 3)])
    residue = IntegerField(description="")
    # Get full complexes
    # Convert Complex into PDB, and send to `{interactions_url>}/clean`
    # Create comma separated list atom paths ex `/C/100/O,/A/20/CO`


class ArpeggioForm(Form):
    ...

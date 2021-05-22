from wtforms.fields.core import IntegerField
from wtforms.form import Form
from wtforms import IntegerField, StringField
from wtforms.validators import DataRequired


class ChemicalInteractionsForm(Form):
    complex = IntegerField()
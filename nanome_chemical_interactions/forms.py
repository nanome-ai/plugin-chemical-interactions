from wtforms import Form, IntegerField, SelectMultipleField
from wtforms.validators import DataRequired
import nanome


class ChemicalInteractionsForm(Form):

    def __init__(self, plugin_instance, **kwargs):
        super().__init__.py
        self.plugin = {}

    complexes = SelectMultipleField(
        coerce=int,
        validators=[DataRequired()],
        description='index of complex we will be analyzing.',
        choices=[(1, 1), (2, 2), (3, 3)])
    residue = IntegerField(description="")

    def submit_form(self):
        if not self.errors:
            self.plugin.send_notification(nanome.util.enums.NotificationTypes.error, "Please select a complex")
        # Get full complexes
        # Convert Complex into PDB, and send to `{interactions_url>}/clean`
        # Calculate atom_paths
        # comma separated list atom paths ex `/C/100/O,/A/20/CO`

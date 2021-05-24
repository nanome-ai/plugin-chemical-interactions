import unittest

from nanome_chemical_interactions.forms import ChemicalInteractionsForm
from nanome_chemical_interactions.menus.forms import InteractionsForm

from nanome.util import Color


class TestChemicalInteractionForm(unittest.TestCase):

    def test_form_validate(self):
        complexes_in_workspace = [1, 2, 3]
        data = {
            "complexes": [1],
            "residue": 99
        }
        form = ChemicalInteractionsForm(data=data, complex_choices=complexes_in_workspace)
        form.validate()
        self.assertFalse(form.errors)


class TestColorSelectionForm(unittest.TestCase):

    def test_form_validate(self):
        test_color = "#ff0000"
        data = {
            "clash_color": test_color,
        }
        form = InteractionsForm(data=data)
        form.validate()
        form.process(data=data)
        # form.process(data=form.data)
        self.assertFalse(form.errors)
        self.assertTrue(isinstance(form.clash.data, Color))


if __name__ == '__main__':
    unittest.main()

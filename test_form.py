import unittest

from nanome_chemical_interactions.forms import ChemicalInteractionsForm


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
        form.submit()


if __name__ == '__main__':
    unittest.main()

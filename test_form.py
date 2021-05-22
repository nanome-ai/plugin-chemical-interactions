import unittest

from nanome_chemical_interactions.forms import ChemicalInteractionsForm


class TestChemicalInteractionForm(unittest.TestCase):

    def test_form_validate(self):
        data = {
            "complexes": [1, 2, 3],
            "residue": 99
        }
        form = ChemicalInteractionsForm(data=data)
        form.validate()
        self.assertFalse(form.errors)
        form.submit()


if __name__ == '__main__':
    unittest.main()

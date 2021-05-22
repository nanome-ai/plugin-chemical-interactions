import unittest

from nanome_chemical_interactions.forms import ChemicalInteractionsForm


class TestChemicalInteractionForm(unittest.TestCase):

    def test_form_validate(self):

        data = {
            "name": "mike rorogarden",
        }
        form = ChemicalInteractionsForm(data=data)
        form.validate()
        self.assertFalse(form.errors)


if __name__ == '__main__':
    unittest.main()

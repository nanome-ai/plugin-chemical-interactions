import unittest

from nanome_chemical_interactions.forms import ChemicalInteractionsForm


class TestChemicalInteractionForm(unittest.TestCase):

    def test_form_validate(self):

        data = {
            "complexes": [1, 2, 3],
            "atom_paths": '/C/100/O'
        }
        form = ChemicalInteractionsForm(data=data)
        form.validate()
        self.assertFalse(form.errors)


if __name__ == '__main__':
    unittest.main()

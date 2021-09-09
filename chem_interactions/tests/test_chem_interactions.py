import os
import pickle
import unittest

from nanome.api.structure import Complex

from chem_interactions.ChemicalInteractions import ChemicalInteractions

fixtures_dir = f'{os.getcwd()}/chem_interactions/tests/fixtures'


class ChemInteractionsTestCase(unittest.TestCase):

    def setUp(self):
        with open(f'{fixtures_dir}/1a9l.pickle', 'rb') as f:
            self.complex1 = pickle.load(f)

        with open(f'{fixtures_dir}/1fsv.pickle', 'rb') as f:
            self.complex2 = pickle.load(f)

        self.plugin = ChemicalInteractions()

    def test_clean_complex(self):
        breakpoint()
        self.assertTrue(self.complex1, Complex)
        self.assertTrue(self.plugin, ChemicalInteractions)

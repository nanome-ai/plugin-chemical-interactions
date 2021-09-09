import os
import pickle
from unittest import TestCase, mock

from nanome.api.structure import Atom, Complex

from chem_interactions.ChemicalInteractions import ChemicalInteractions

fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures')


mocked_interactions_url = "https://fake-arpeggio-service.com"


class MockRequestResponse:
    def __init__(self, content_data, status_code):
        self.content = content_data
        self.status_code = status_code


class ChemInteractionsTestCase(TestCase):

    def setUp(self):
        with open(f'{fixtures_dir}/1a9l.pickle', 'rb') as f:
            self.complex1 = pickle.load(f)

        with open(f'{fixtures_dir}/1fsv.pickle', 'rb') as f:
            self.complex2 = pickle.load(f)

        self.plugin = ChemicalInteractions()
        with mock.patch.dict(os.environ, {"INTERACTIONS_URL": mocked_interactions_url}):
            self.plugin.start()

    def test_setup(self):
        self.assertTrue(self.complex1, Complex)
        self.assertTrue(self.plugin, ChemicalInteractions)

    def test_clean_complex(self):
        test_data = b"Doesn't really matter what data is returned"
        with mock.patch('requests.post', return_value=MockRequestResponse(test_data, 200)):
            cleaned_file = self.plugin.clean_complex(self.complex1)
        self.assertEqual(open(cleaned_file.name).read(), test_data.decode('utf-8'))

    def test_get_atom_path(self):
        # I think the first atom is always consistent?
        atom = next(self.complex1.atoms)
        expected_atom_path = "/A/1/O5'"
        atom_path = self.plugin.get_atom_path(atom)
        self.assertEqual(atom_path, expected_atom_path)
        pass

    def test_get_residue_path(self):
        # I think the first residue is always consistent?
        res = next(self.complex1.residues)
        expected_residue_path = "/A/1/"
        residue_path = self.plugin.get_residue_path(res)
        self.assertEqual(residue_path, expected_residue_path)
        pass

    def test_get_selected_atom_paths(self):
        atom = next(self.complex1.atoms)
        atom.selected = True
        atom_path = self.plugin.get_atom_path(atom)
        atom_paths = self.plugin.get_selected_atom_paths(self.complex1)
        self.assertEqual(len(atom_paths), 1)
        self.assertTrue(atom_path in atom_paths)

    def test_get_atom_from_path(self):
        atom_path = "A/1/O5'"
        atom = self.plugin.get_atom_from_path(self.complex1, atom_path)
        self.assertTrue(isinstance(atom, Atom))

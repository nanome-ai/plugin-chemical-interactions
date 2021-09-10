import asyncio
import itertools
import json
import os
from unittest import TestCase, mock, skip
from nanome.api.structure import Atom, Complex

from chem_interactions.ChemicalInteractions import ChemicalInteractions
from chem_interactions.forms import default_line_settings

from unittest.mock import MagicMock

fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures')


class MockRequestResponse:
    def __init__(self, content_data, status_code):
        self.content = content_data
        self.status_code = status_code


class ChemInteractionsTestCase(TestCase):

    def setUp(self):
        tyl_pdb = f'{fixtures_dir}/1tyl.pdb'
        self.complex = Complex.io.from_pdb(path=tyl_pdb)

        self.plugin = ChemicalInteractions()
        with mock.patch.dict(os.environ, {"INTERACTIONS_URL": "https://fake-arpeggio-service.com"}):
            self.plugin.start()
        self.plugin._network = MagicMock()

    def test_setup(self):
        self.assertEqual(1, 2)
        self.assertTrue(self.complex, Complex)
        self.assertTrue(self.plugin, ChemicalInteractions)

    def test_clean_complex(self):
        test_data = b"Doesn't really matter what data is returned"
        with mock.patch('requests.post', return_value=MockRequestResponse(test_data, 200)):
            cleaned_file = self.plugin.clean_complex(self.complex)
        self.assertEqual(open(cleaned_file.name).read(), test_data.decode('utf-8'))

    def test_get_atom_path(self):
        # I think the first atom is always consistent?
        atom = next(self.complex.atoms)
        expected_atom_path = "/A/1/N"
        atom_path = self.plugin.get_atom_path(atom)
        self.assertEqual(atom_path, expected_atom_path)

    def test_get_residue_path(self):
        # I think the first residue is always consistent?
        res = next(self.complex.residues)
        expected_residue_path = "/A/1/"
        residue_path = self.plugin.get_residue_path(res)
        self.assertEqual(residue_path, expected_residue_path)

    def test_get_selected_atom_paths(self):
        atom = next(self.complex.atoms)
        atom.selected = True
        atom_path = self.plugin.get_atom_path(atom)
        atom_paths = self.plugin.get_selected_atom_paths(self.complex)
        self.assertEqual(len(atom_paths), 1)
        self.assertTrue(atom_path in atom_paths)

    def test_get_atom_from_path(self):
        atom_path = "A/1/N"
        atom = self.plugin.get_atom_from_path(self.complex, atom_path)
        self.assertTrue(isinstance(atom, Atom))

    def test_get_interaction_selections(self):
        atom_count = 10
        atoms = itertools.islice(self.complex.atoms, atom_count)
        for atom in atoms:
            atom.selected = True
        selection = self.plugin.get_interaction_selections(self.complex, [self.complex], [], True)
        self.assertEqual(len(selection.split(',')), atom_count)

    def test_parse_contacts_data(self):
        contacts_data = json.loads(open(f'{fixtures_dir}/1tyl_contacts_data.json').read())
        # Known value from 1tyl_contacts_data.json
        expected_line_count = 86
        loop = asyncio.get_event_loop()
        line_manager = loop.run_until_complete(self.plugin.parse_contacts_data(contacts_data, [self.complex], default_line_settings))
        self.assertEqual(len(line_manager.all_lines()), expected_line_count)

import asyncio
import itertools
import json
import os
import unittest
from unittest.mock import MagicMock

import nanome
from nanome.api.structure import Atom, Complex

from chem_interactions.ChemicalInteractions import ChemicalInteractions
from chem_interactions.forms import default_line_settings


fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures')


class MockRequestResponse:
    def __init__(self, content_data, status_code):
        self.content = content_data
        self.status_code = status_code


class ChemInteractionsTestCase(unittest.TestCase):

    def setUp(self):
        tyl_pdb = f'{fixtures_dir}/1tyl.pdb'
        self.complex = Complex.io.from_pdb(path=tyl_pdb)

        self.plugin = ChemicalInteractions()
        with unittest.mock.patch.dict(os.environ, {"INTERACTIONS_URL": "https://fake-arpeggio-service.com"}):
            self.plugin.start()
        self.plugin._network = MagicMock()

    def test_setup(self):
        self.assertTrue(self.complex, Complex)
        self.assertTrue(self.plugin, ChemicalInteractions)

    @unittest.skip("TODO: figure out how to test Processes.")
    def test_clean_complex(self):
        # Make sure clean_complex function returns valid pdb can be parsed into a Complex structure.
        loop = asyncio.get_event_loop()
        # clean_call_fut = self.plugin.clean_complex(self.complex)
        nanome.PluginInstance._instance = self.plugin
        nanome.PluginInstance._instance.is_async = True
        result = loop.run_until_complete(self.plugin.clean_complex(self.complex))

        # clean_call_fut.result()
        cleaned_complex = Complex.io.from_pdb(path=result.name)
        self.assertTrue(sum(1 for atom in cleaned_complex.atoms) > 0)

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

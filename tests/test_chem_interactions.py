import asyncio
import itertools
import json
import os
import unittest
from unittest.mock import patch

from unittest.mock import MagicMock
from nanome.api.structure import Atom, Complex
from chem_interactions.ChemicalInteractions import ChemicalInteractions
from chem_interactions.forms import default_line_settings


fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures')


class ChemInteractionsTestCase(unittest.TestCase):

    def setUp(self):
        tyl_pdb = f'{fixtures_dir}/1tyl.pdb'
        self.complex = Complex.io.from_pdb(path=tyl_pdb)
        self.plugin_instance = ChemicalInteractions()
        self.plugin_instance.start()
        self.plugin_instance._network = MagicMock()

    def test_clean_complex(self):
        # Make sure clean_complex function returns valid pdb can be parsed into a Complex structure.
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.plugin_instance.clean_complex(self.complex))
        cleaned_complex = Complex.io.from_pdb(path=result.name)
        self.assertTrue(sum(1 for atom in cleaned_complex.atoms) > 0)

    def test_get_atom_path(self):
        # I think the first atom is always consistent?
        atom = next(self.complex.atoms)
        expected_atom_path = "/A/1/N"
        atom_path = self.plugin_instance.get_atom_path(atom)
        self.assertEqual(atom_path, expected_atom_path)

    def test_get_residue_path(self):
        # I think the first residue is always consistent?
        res = next(self.complex.residues)
        expected_residue_path = "/A/1/"
        residue_path = self.plugin_instance.get_residue_path(res)
        self.assertEqual(residue_path, expected_residue_path)

    def test_get_selected_atom_paths(self):
        atom = next(self.complex.atoms)
        atom.selected = True
        atom_path = self.plugin_instance.get_atom_path(atom)
        atom_paths = self.plugin_instance.get_selected_atom_paths(self.complex)
        self.assertEqual(len(atom_paths), 1)
        self.assertTrue(atom_path in atom_paths)

    def test_get_atom_from_path(self):
        atom_path = "A/1/N"
        atom = self.plugin_instance.get_atom_from_path(self.complex, atom_path)
        self.assertTrue(isinstance(atom, Atom))

    def test_get_interaction_selections(self):
        atom_count = 10
        atoms = itertools.islice(self.complex.atoms, atom_count)
        for atom in atoms:
            atom.selected = True
        selection = self.plugin_instance.get_interaction_selections(self.complex, [self.complex], [], True)
        self.assertEqual(len(selection.split(',')), atom_count)

    def test_parse_contacts_data(self):
        with open(f'{fixtures_dir}/1tyl_contacts_data.json') as f:
            contacts_data = json.loads(f.read())
        # Known value from 1tyl_contacts_data.json
        expected_line_count = 86
        loop = asyncio.get_event_loop()
        line_manager = loop.run_until_complete(
            self.plugin_instance.parse_contacts_data(
                contacts_data, [self.complex], default_line_settings
            )
        )
        self.assertEqual(len(line_manager.all_lines()), expected_line_count)

    def test_run_arpeggio(self):
        with open(f'{fixtures_dir}/1tyl_ligand_selections.json') as f:
            arpeggio_data = json.loads(f.read())
        cleaned_pdb = f'{fixtures_dir}/1tyl_cleaned.pdb'
        loop = asyncio.get_event_loop()
        contacts_data = {}
        with open(cleaned_pdb) as f:
            contacts_data = loop.run_until_complete(self.plugin_instance.run_arpeggio_process(arpeggio_data, [f]))
        self.assertTrue(contacts_data)

    @patch('nanome._internal._network._ProcessNetwork._instance')
    def test_calculate_interactions_selected_atoms(self, patch):
        # Select all atoms on the ligand chain
        chain_name = 'HC'
        ligand_chain = next(ch for ch in self.complex.chains if ch.name == chain_name)
        for atom in ligand_chain.atoms:
            atom.selected = True

        # Set up event loop 
        event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(event_loop)

        async def run_calculate_interactions():
            # Make sure running calculate_interactions with selected atoms adds lines to line manager
            self.assertEqual(len(self.plugin_instance.line_manager.all_lines()), 0)
            await self.plugin_instance.calculate_interactions(
                self.complex, [], default_line_settings, selected_atoms_only=True)
            self.assertTrue(len(self.plugin_instance.line_manager.all_lines()) > 0)
        coro = asyncio.coroutine(run_calculate_interactions)
        event_loop.run_until_complete(coro())
        # event_loop.close()


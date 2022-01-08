import asyncio
import itertools
import json
import os
import unittest
from unittest.mock import patch
from random import randint

from unittest.mock import MagicMock
from nanome.api.structure import Atom, Complex, Molecule
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
        selection = self.plugin_instance.get_interaction_selections(self.complex, [self.complex], True)
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

        target_complex = self.complex
        ligand_residues = list(self.complex.residues)
        selected_atoms_only = True
        self.validate_calculate_interactions(
            target_complex,
            ligand_residues,
            selected_atoms_only=selected_atoms_only)
    @unittest.skip("Ligand and Protein don't align, so no interactions found")
    @patch('nanome._internal._network._ProcessNetwork._instance')
    def test_calculate_interactions_separate_ligand(self, patch):
        # Split ligand out into separate Complex
        target_complex = self.complex
        selected_molecule = next(self.complex.molecules)
        chain_name = 'HC'
        ligand_complex = Complex()
        ligand_molecule = Molecule()
        
        ligand_chain = next(ch for ch in self.complex.chains if ch.name == chain_name)
        ligand_molecule.add_chain(ligand_chain)
        ligand_complex.add_molecule(ligand_molecule)
        selected_molecule.remove_chain(ligand_chain)

        distance_labels = True
        ligand_residues = list(ligand_complex.residues)
        self.validate_calculate_interactions(
            target_complex, ligand_residues, distance_labels=distance_labels)

    @patch('nanome._internal._network._ProcessNetwork._instance')
    def test_calculate_interactions_distance_labels(self, patch):
        """Ensure that distance labels can be added to the InteractionLines."""
        # Select all atoms on the ligand chain
        target_complex = self.complex
        chain_name = 'HC'
        ligand_chain = next(ch for ch in self.complex.chains if ch.name == chain_name)
        for atom in ligand_chain.atoms:
            atom.selected = True

        # Add a random atom indices to every atom
        for atom in target_complex.atoms:
            atom.index = randint(1000000000, 9999999999)
        ligand_residues = list(target_complex.residues)
        selected_atoms_only = True
        distance_labels = True
        self.validate_calculate_interactions(
            target_complex,
            ligand_residues,
            selected_atoms_only=selected_atoms_only,
            distance_labels=distance_labels)

    def validate_calculate_interactions(
            self, target_complex, ligand_residues, selected_atoms_only=False, distance_labels=False):
        """Test async call to calculate interactions."""
        event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(event_loop)

        async def run_calculate_interactions(
            target_complex, ligand_residues, selected_atoms_only=False, distance_labels=False):
            """Run plugin.calculate_interactions with provided args and make sure lines are added to LineManager."""
            line_count = len(self.plugin_instance.line_manager.all_lines())
            self.assertEqual(line_count, 0)
            await self.plugin_instance.calculate_interactions(
                target_complex, ligand_residues, default_line_settings,
                selected_atoms_only=selected_atoms_only,
                distance_labels=distance_labels)

            new_line_count = len(self.plugin_instance.line_manager.all_lines())
            self.assertTrue(new_line_count > 0)
            if distance_labels:
                label_count = len(self.plugin_instance.label_manager.all_labels())
                self.assertTrue(label_count > 0)
        
        coro = asyncio.coroutine(run_calculate_interactions)

        event_loop.run_until_complete(coro(
            target_complex, ligand_residues,
            selected_atoms_only=selected_atoms_only,
            distance_labels=distance_labels))
        # event_loop.close()

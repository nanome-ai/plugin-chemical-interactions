import asyncio
import itertools
import json
import os
import unittest
from unittest.mock import patch
from random import randint

from unittest.mock import MagicMock
from nanome.api import ui, PluginInstance
from nanome.api.structure import Atom, Chain, Complex, Molecule
from plugin.menus import ChemInteractionsMenu
from plugin.ChemicalInteractions import ChemicalInteractions
from plugin.forms import default_line_settings


fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures')


def run_awaitable(awaitable, *args, **kwargs):
    loop = asyncio.get_event_loop()
    if loop.is_running:
        loop = asyncio.new_event_loop()
    loop.run_until_complete(awaitable(*args, **kwargs))
    loop.close()


class PluginFunctionTestCase(unittest.TestCase):

    def setUp(self):
        tyl_pdb = f'{fixtures_dir}/1tyl.pdb'
        self.complex = Complex.io.from_pdb(path=tyl_pdb)
        for atom in self.complex.atoms:
            atom.index = randint(1000000000, 9999999999)
        self.plugin_instance = ChemicalInteractions()
        self.plugin_instance.start()
        self.plugin_instance._network = MagicMock()

    def tearDown(self) -> None:
        self.plugin_instance.on_stop()
        return super().tearDown()

    def test_get_clean_pdb_file(self):
        # Make sure get_clean_pdb_file function returns valid pdb can be parsed into a Complex structure.
        result = self.plugin_instance.get_clean_pdb_file(self.complex)
        cleaned_complex = Complex.io.from_pdb(path=result)
        self.assertTrue(sum(1 for _ in cleaned_complex.atoms) > 0)

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
        expected_line_count = 26
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
        contacts_data = loop.run_until_complete(self.plugin_instance.run_arpeggio_process(arpeggio_data, cleaned_pdb))
        self.assertTrue(contacts_data)


class CalculateInteractionsTestCase(unittest.TestCase):
    """Test different combinations of args for calculate_interactions."""

    def setUp(self):
        tyl_pdb = f'{fixtures_dir}/1tyl.pdb'
        self.complex = Complex.io.from_pdb(path=tyl_pdb)
        for atom in self.complex.atoms:
            atom.index = randint(1000000000, 9999999999)
        self.plugin_instance = ChemicalInteractions()
        self.plugin_instance.start()
        self.plugin_instance._network = MagicMock()

    def tearDown(self) -> None:
        self.plugin_instance.on_stop()
        return super().tearDown()

    @patch('nanome._internal._network.PluginNetwork._instance')
    def test_selected_atoms(self, _):
        """Validate calculate_interactions call using selected atoms."""
        target_complex = self.complex        
        # Select ligand residues
        chain_name = 'HC'
        ligand_chain = next(ch for ch in target_complex.chains if ch.name == chain_name)
        for atom in ligand_chain.atoms:
            atom.selected = True
        ligand_residues = [res for res in ligand_chain.residues]
        
        selected_atoms_only = True
        distance_labels = False
        run_awaitable(
            self.validate_calculate_interactions,
            target_complex,
            ligand_residues,
            selected_atoms_only=selected_atoms_only,
            distance_labels=distance_labels)

    @patch('nanome._internal._network.PluginNetwork._instance')
    def test_separate_ligand_complex(self, _):
        """Validate calculate_interactions call where ligand is on a separate complex."""
        target_complex = self.complex
        chain_name = 'HC'
        residue_name = 'TYL'
        ligand_residue = next(res for res in self.complex.residues if res.name == residue_name)

        # Build new complex containing ligand residue
        ligand_complex = Complex()
        ligand_molecule = Molecule()
        ligand_chain = Chain()
        ligand_chain.name = chain_name

        ligand_chain.add_residue(ligand_residue)
        ligand_molecule.add_chain(ligand_chain)
        ligand_complex.add_molecule(ligand_molecule)

        target_complex.index = 98
        ligand_complex.index = 99
        distance_labels = True
        ligand_residues = list(ligand_complex.residues)
        return run_awaitable(
            self.validate_calculate_interactions,
            target_complex,
            [ligand_residue],
            distance_labels=distance_labels)

    @patch('nanome._internal._network.PluginNetwork._instance')
    def test_specific_structures(self, _):
        """Validate calculate_interactions call with no selections, but a list of residues provided."""
        chain_name = 'HC'
        ligand_chain = next(ch for ch in self.complex.chains if ch.name == chain_name)

        target_complex = self.complex
        ligand_residues = list(ligand_chain.residues)
        selected_atoms_only = False

        return run_awaitable(
            self.validate_calculate_interactions,
            target_complex,
            ligand_residues,
            selected_atoms_only=selected_atoms_only)

    @patch('nanome._internal._network.PluginNetwork._instance')
    def test_distance_labels(self, _):
        """Ensure that distance labels can be added to the InteractionLines."""
        # Select all atoms on the ligand chain
        target_complex = self.complex
        chain_name = 'HC'
        ligand_chain = next(ch for ch in self.complex.chains if ch.name == chain_name)
        for atom in ligand_chain.atoms:
            atom.selected = True

        ligand_residues = list(ligand_chain.residues)
        selected_atoms_only = True
        distance_labels = True
        run_awaitable(
            self.validate_calculate_interactions,
            target_complex,
            ligand_residues,
            selected_atoms_only=selected_atoms_only,
            distance_labels=distance_labels)

    async def validate_calculate_interactions(
            self, target_complex, ligand_residues, selected_atoms_only=False, distance_labels=False):
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

    @patch('nanome.api.plugin_instance.PluginInstance.create_writing_stream')
    @patch('nanome._internal._network.PluginNetwork._instance')
    def test_menu(self, mock_network, create_writing_stream_mock):
        async def _test_menu():
            # Select all atoms on the ligand chain
            chain_name = 'HC'
            ligand_chain = next(ch for ch in self.complex.chains if ch.name == chain_name)
            target_complex = self.complex
            ligand_residues = list(ligand_chain.residues)
            selected_atoms_only = False
            distance_labels = True

            line_count = len(self.plugin_instance.line_manager.all_lines())
            self.assertEqual(line_count, 0)
            await self.validate_calculate_interactions(
                target_complex,
                ligand_residues,
                selected_atoms_only=selected_atoms_only,
                distance_labels=distance_labels)

            line_count = len(self.plugin_instance.line_manager.all_lines())
            self.assertTrue(line_count > 0)
            # Set up mocked result for create_writing_stream_mock
            fut = asyncio.Future()
            fut.set_result((MagicMock(), None))
            create_writing_stream_mock.return_value = fut

            menu = ChemInteractionsMenu(self.plugin_instance)
            self.plugin_instance._menus = [menu]
            await menu.render(complexes=[self.complex])
            updated_line_settings = dict(default_line_settings)
            updated_line_settings['hydrophobic']['dash_length'] = 0.5
            await menu.update_interaction_lines()

            btn = ui.Button()
            menu.toggle_all_interactions(btn)
            menu.reset_calculate_btn()
            menu.toggle_visibility(btn)
            menu.toggle_atom_selection(btn)

            # Test clear_frame()
            self.assertTrue(line_count > 0)
            await menu.clear_frame(MagicMock())
            line_count = len(self.plugin_instance.line_manager.all_lines())
            self.assertEqual(line_count, 0)

        run_awaitable(_test_menu)

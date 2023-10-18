import asyncio
import json
import os
import unittest
from unittest.mock import patch
from random import randint

from unittest.mock import MagicMock
from nanome.api import ui
from nanome.api.structure import Chain, Complex, Molecule, Workspace
from plugin.ChemicalInteractions import ChemicalInteractions
from plugin.forms import default_line_settings


fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures')


class CalculateInteractionsTestCase(unittest.IsolatedAsyncioTestCase):
    """Test different combinations of args for calculate_interactions."""

    def setUp(self):
        tyl_pdb = f'{fixtures_dir}/1tyl.pdb'
        self.complex = Complex.io.from_pdb(path=tyl_pdb)
        for atom in self.complex.atoms:
            atom.index = randint(1000000000, 9999999999)
        self.plugin_instance = ChemicalInteractions()
        self.plugin_instance._network = MagicMock()
        with open(f'{fixtures_dir}/version_table_1_24_2.json') as f:
            self.plugin_instance._network._version_table = json.loads(f.read())
        self.plugin_instance.start()
        self.plugin_instance._network = MagicMock()

        ws = Workspace()
        ws.complexes = [self.complex]
        self.request_workspace_fut = asyncio.Future()
        self.request_workspace_fut.set_result(ws)
        self.plugin_instance.request_workspace = MagicMock()
        self.plugin_instance.request_workspace.return_value = self.request_workspace_fut

    def tearDown(self) -> None:
        self.plugin_instance.on_stop()
        return super().tearDown()

    @patch('nanome._internal.network.PluginNetwork._instance')
    async def test_selected_atoms(self, _):
        """Validate calculate_interactions call using selected atoms."""
        target_complex = self.complex
        # Select ligand residues
        chain_name = 'HC'
        ligand_chain = next(ch for ch in target_complex.chains if ch.name == chain_name)
        for atom in ligand_chain.atoms:
            atom.selected = True

        ligand_residues = list(ligand_chain.residues)
        selected_atoms_only = True
        distance_labels = False
        await self.validate_calculate_interactions(
            target_complex,
            ligand_residues,
            selected_atoms_only=selected_atoms_only,
            distance_labels=distance_labels)

    @patch('nanome._internal.network.PluginNetwork._instance')
    @patch('nanome.api.shapes.shape.Shape.upload_multiple')
    async def test_separate_ligand_complex(self, shape_mock, *mocks):
        """Validate calculate_interactions call where ligand is on a separate complex."""
        target_complex = self.complex
        chain_name = 'HC'
        residue_name = 'TYL'
        ligand_residue = next(res for res in self.complex.residues if res.name == residue_name)

        shape_mock.return_value = asyncio.Future()
        shape_mock.return_value.set_result(None)
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
        await self.validate_calculate_interactions(
            target_complex,
            ligand_residues,
            distance_labels=distance_labels)

    @patch('nanome._internal.network.PluginNetwork._instance')
    async def test_specific_structures(self, _):
        """Validate calculate_interactions call with no selections, but a list of residues provided."""
        chain_name = 'HC'
        ligand_chain = next(ch for ch in self.complex.chains if ch.name == chain_name)

        target_complex = self.complex
        ligand_residues = list(ligand_chain.residues)
        selected_atoms_only = False

        await self.validate_calculate_interactions(
            target_complex,
            ligand_residues,
            selected_atoms_only=selected_atoms_only)

    @patch('nanome._internal.network.PluginNetwork._instance')
    @patch('nanome.api.shapes.shape.Shape.upload_multiple')
    async def test_distance_labels(self, upload_mock, _):
        """Ensure that distance labels can be added to the InteractionLines."""
        upload_mock.return_value = asyncio.Future()
        upload_mock.return_value.set_result([])
        # Select all atoms on the ligand chain
        target_complex = self.complex
        chain_name = 'HC'
        ligand_chain = next(ch for ch in self.complex.chains if ch.name == chain_name)
        for atom in ligand_chain.atoms:
            atom.selected = True

        ligand_residues = list(ligand_chain.residues)
        selected_atoms_only = True
        distance_labels = True
        await self.validate_calculate_interactions(
            target_complex,
            ligand_residues,
            selected_atoms_only=selected_atoms_only,
            distance_labels=distance_labels)

    async def validate_calculate_interactions(
            self, target_complex, ligand_residues, selected_atoms_only=False, distance_labels=False):
        """Run plugin.calculate_interactions with provided args and make sure lines are added to LineManager."""
        line_count = len(await self.plugin_instance.line_manager.all_lines())
        self.assertEqual(line_count, 0)

        await self.plugin_instance.calculate_interactions(
            target_complex, ligand_residues, default_line_settings,
            selected_atoms_only=selected_atoms_only,
            distance_labels=distance_labels)

        new_line_count = len(await self.plugin_instance.line_manager.all_lines())
        self.assertTrue(new_line_count > 0)
        if distance_labels:
            label_count = len(self.plugin_instance.label_manager.all_labels())
            self.assertTrue(label_count > 0)

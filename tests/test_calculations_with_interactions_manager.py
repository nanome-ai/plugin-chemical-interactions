import asyncio
import json
import os
import unittest
from unittest.mock import patch
from random import randint

from unittest.mock import MagicMock
from nanome.api import ui, interactions
from nanome.api.structure import Chain, Complex, Molecule, Workspace
from nanome.util import enums
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
        version_table = {}
        with open(f'{fixtures_dir}/version_table_1_24_2.json') as f:
            version_table = json.loads(f.read())

        # Bump GetInteractions version to 1 so that the InteractionLineManager will be used
        # to use the persistent interactions api.
        version_table['GetInteractions'] = 1
        self.plugin_instance._network._version_table = version_table
        self.plugin_instance.start()
        self.plugin_instance._network = MagicMock()

        atom1 = list(self.complex.atoms)[0]
        atom2 = list(self.complex.atoms)[1]
        interaction = interactions.Interaction(
            kind=enums.InteractionKind.Hydrophobic,
            atom1_idx_arr=[atom1.index],
            atom2_idx_arr=[atom2.index],
            atom1_conf=0,
            atom2_conf=0
        )
        self.get_fut_1 = asyncio.Future()
        self.get_fut_2 = asyncio.Future()
        self.get_fut_1.set_result([])
        self.get_fut_2.set_result([interaction])
        
        ws = Workspace()
        ws.complexes = [self.complex]
        self.request_workspace_fut = asyncio.Future()
        self.request_workspace_fut.set_result(ws)
        self.plugin_instance.request_workspace = MagicMock()
        self.plugin_instance.request_workspace.return_value = self.request_workspace_fut
        

    def tearDown(self) -> None:
        self.plugin_instance.on_stop()
        return super().tearDown()

    @patch('nanome.api.interactions.Interaction.upload_multiple')
    @patch('nanome.api.interactions.Interaction.get')
    @patch('nanome._internal.network.PluginNetwork._instance')
    async def test_selected_atoms(self, _, mock_interaction_get, upload_multiple_interactions):
        """Validate calculate_interactions call using selected atoms."""
        mock_interaction_get.side_effect = [self.get_fut_1, self.get_fut_2, self.get_fut_2]
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
    @patch('nanome.api.interactions.Interaction.upload_multiple')
    @patch('nanome.api.shapes.shape.Shape.upload_multiple')
    @patch('nanome.api.interactions.Interaction.get')
    async def test_separate_ligand_complex(self, mock_interaction_get, mock_shape_upload_multiple, *mocks):
        """Validate calculate_interactions call where ligand is on a separate complex."""
        target_complex = self.complex
        chain_name = 'HC'
        residue_name = 'TYL'
        ligand_residue = next(res for res in self.complex.residues if res.name == residue_name)
        mock_interaction_get.side_effect = [self.get_fut_1, self.get_fut_1, self.get_fut_2, self.get_fut_2]
        mock_shape_upload_multiple.return_value = self.get_fut_1

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
    @patch('nanome.api.interactions.Interaction.upload_multiple')
    @patch('nanome.api.interactions.Interaction.get')
    async def test_specific_structures(self, mock_interaction_gets, *mocks):
        """Validate calculate_interactions call with no selections, but a list of residues provided."""
        chain_name = 'HC'
        ligand_chain = next(ch for ch in self.complex.chains if ch.name == chain_name)
        mock_interaction_gets.side_effect = [self.get_fut_1, self.get_fut_2, self.get_fut_2]

        target_complex = self.complex
        ligand_residues = list(ligand_chain.residues)
        selected_atoms_only = False

        await self.validate_calculate_interactions(
            target_complex,
            ligand_residues,
            selected_atoms_only=selected_atoms_only)

    @patch('nanome._internal.network.PluginNetwork._instance')
    @patch('nanome.api.interactions.Interaction.upload_multiple')
    @patch('nanome.api.shapes.shape.Shape.upload_multiple')
    @patch('nanome.api.interactions.Interaction.get')
    async def test_distance_labels(self, interaction_get_mock, upload_mock, *mocks):
        """Ensure that distance labels can be added to the InteractionLines."""
        upload_mock.return_value = asyncio.Future()
        upload_mock.return_value.set_result([])
        interaction_get_mock.side_effect = [self.get_fut_1, self.get_fut_2, self.get_fut_2, self.get_fut_2]
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

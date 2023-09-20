import asyncio
import nanome
import os
import unittest
from unittest.mock import patch
from random import randint

from unittest.mock import MagicMock
from nanome.api.structure import Complex
from nanome.api.interactions import Interaction
from nanome.util import enums
from plugin.managers import ShapesLineManager, InteractionLineManager
from plugin.models import InteractionShapesLine, InteractionStructure
from plugin.forms import default_line_settings


fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures')


class ShapesLineManagerTestCase(unittest.IsolatedAsyncioTestCase):
    """Test different combinations of args for calculate_interactions."""

    def setUp(self):
        tyl_pdb = f'{fixtures_dir}/1tyl.pdb'
        self.complex = Complex.io.from_pdb(path=tyl_pdb)
        for atom in self.complex.atoms:
            atom.index = randint(1000000000, 9999999999)

        self.manager = ShapesLineManager()

        atom_list = list(self.complex.atoms)
        self.struct1 = InteractionStructure(atom_list[0])
        self.struct2 = InteractionStructure(atom_list[1])
        self.struct3 = InteractionStructure(atom_list[2:7])
        self.interaction_line = InteractionShapesLine(
            self.struct1, self.struct2, kind=enums.InteractionKind.Covalent)
        self.interaction_line_2 = InteractionShapesLine(
            self.struct1, self.struct3, kind=enums.InteractionKind.Aromatic)

    async def test_add_line(self, *mocks):
        line_count = len(await self.manager.all_lines())
        self.assertEqual(line_count, 0)
        self.manager.add_line(self.interaction_line)
        new_line_count = len(await self.manager.all_lines())
        self.assertEqual(new_line_count, 1)

    async def test_add_lines(self, *mocks):
        line_count = len(await self.manager.all_lines())
        self.assertEqual(line_count, 0)
        self.manager.add_lines([self.interaction_line, self.interaction_line_2])
        new_line_count = len(await self.manager.all_lines())
        self.assertEqual(new_line_count, 2)

    async def test_update_line(self):
        """Ensure we can update an existing line in the manager"""
        # add lines to manager
        lines = [self.interaction_line, self.interaction_line_2]
        starting_line_count = len(lines)
        self.manager.add_lines(lines)
        all_lines = await self.manager.all_lines()
        self.assertEqual(len(all_lines), starting_line_count)
        # Update the kind on one of the lines
        line = next(line for line in all_lines if line.kind == enums.InteractionKind.Covalent)
        self.assertEqual(line.kind, enums.InteractionKind.Covalent)
        new_kind = enums.InteractionKind.Clash
        line.kind = new_kind
        self.manager._update_line(line)
        # Ensure update worked
        all_lines = await self.manager.all_lines()
        # Assert we have the same number of lines we started with
        self.assertEqual(len(all_lines), starting_line_count)
        # Make sure one of the lines is a Clash
        updated_line = line = next(line for line in all_lines if line.kind == new_kind)
        self.assertEqual(updated_line.kind, new_kind)

    @patch('nanome.api.shapes.shape.Shape.upload_multiple')
    def test_upload(self, upload_mock):
        line_list = [self.interaction_line, self.interaction_line_2]
        self.manager.upload(line_list)
        upload_mock.assert_called_with(line_list)

    def test_draw_interaction_line(self):
        interaction_kind = enums.InteractionKind.Covalent
        line_settings = default_line_settings[interaction_kind.name]
        line = self.manager.draw_interaction_line(self.struct1, self.struct2, interaction_kind, line_settings)
        self.assertTrue(isinstance(line, InteractionShapesLine))
        self.assertTrue(line.kind, interaction_kind)

    @patch('nanome.api.shapes.shape.Shape.destroy_multiple')
    async def test_destroy_lines(self, destroy_mock):
        lines = [self.interaction_line, self.interaction_line_2]
        self.manager.add_lines(lines)
        line_count = len(await self.manager.all_lines())
        self.assertEqual(line_count, 2)
        self.manager.destroy_lines(lines)
        destroy_mock.assert_called_with(lines)
        line_count = len(await self.manager.all_lines())
        self.assertEqual(line_count, 0)

    async def test_get_lines_for_structure_pair(self):
        lines = [self.interaction_line, self.interaction_line_2]
        self.manager.add_lines(lines)
        line_count = len(await self.manager.all_lines())
        self.assertEqual(line_count, 2)
        structpair_lines_1_2 = self.manager.get_lines_for_structure_pair(
            self.struct1.index, self.struct2.index)
        self.assertEqual(len(structpair_lines_1_2), 1)

        structpair_lines_1_3 = self.manager.get_lines_for_structure_pair(
            self.struct1.index, self.struct3.index)
        self.assertEqual(len(structpair_lines_1_3), 1)

        structpair_lines_2_3 = self.manager.get_lines_for_structure_pair(
            self.struct2.index, self.struct3.index)
        self.assertEqual(len(structpair_lines_2_3), 0)


class InteractionLineManagerTestCase(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        nanome.PluginInstance._instance = MagicMock()

        tyl_pdb = f'{fixtures_dir}/1tyl.pdb'
        self.complex = Complex.io.from_pdb(path=tyl_pdb)
        for atom in self.complex.atoms:
            atom.index = randint(1000000000, 9999999999)

        self.manager = InteractionLineManager()

        atom_list = list(self.complex.atoms)
        self.struct1 = InteractionStructure(atom_list[0])
        self.struct2 = InteractionStructure(atom_list[1])
        self.struct3 = InteractionStructure(atom_list[2:7])
        struct1_atom_indices = [atom.index for atom in self.struct1.atoms]
        struct2_atom_indices = [atom.index for atom in self.struct2.atoms]
        struct3_atom_indices = [atom.index for atom in self.struct3.atoms]
        self.interaction_line = Interaction(
            kind=enums.InteractionKind.Covalent,
            atom1_idx_arr=struct1_atom_indices,
            atom2_idx_arr=struct2_atom_indices,
            atom1_conf=0,
            atom2_conf=0
        )
        self.interaction_line_2 = Interaction(
            kind=enums.InteractionKind.Aromatic,
            atom1_idx_arr=struct1_atom_indices,
            atom2_idx_arr=struct3_atom_indices,
            atom1_conf=0,
            atom2_conf=0
        )

        self.get_fut_empty = asyncio.Future()
        self.get_fut_1_line = asyncio.Future()
        self.get_fut_2_lines = asyncio.Future()
        self.get_fut_empty.set_result([])
        self.get_fut_1_line.set_result([self.interaction_line])
        self.get_fut_2_lines.set_result([self.interaction_line, self.interaction_line_2])

    async def test_add_line(self, *mocks):
        line_count = len(await self.manager.all_lines())
        self.assertEqual(line_count, 0)
        self.manager.add_line(self.interaction_line)
        new_line_count = len(await self.manager.all_lines())
        self.assertEqual(new_line_count, 1)

    async def test_add_lines(self, *mocks):
        line_count = len(await self.manager.all_lines())
        self.assertEqual(line_count, 0)
        self.manager.add_lines([self.interaction_line, self.interaction_line_2])
        new_line_count = len(await self.manager.all_lines())
        self.assertEqual(new_line_count, 2)

    @patch('nanome.api.interactions.interaction.Interaction.upload_multiple')
    def test_upload(self, upload_mock):
        line_list = [self.interaction_line, self.interaction_line_2]
        self.manager.upload(line_list)
        upload_mock.assert_called_with(line_list)

    def test_draw_interaction_line(self):
        interaction_kind = enums.InteractionKind.Covalent
        line_settings = default_line_settings[interaction_kind.name]
        line = self.manager.draw_interaction_line(self.struct1, self.struct2, interaction_kind, line_settings)
        self.assertTrue(isinstance(line, Interaction))
        self.assertTrue(line.kind, interaction_kind)

    @patch('nanome.api.interactions.interaction.Interaction.destroy_multiple')
    async def test_destroy_lines(self, destroy_mock):
        lines = [self.interaction_line, self.interaction_line_2]
        self.manager.add_lines(lines)
        line_count = len(await self.manager.all_lines())
        self.assertEqual(line_count, 2)
        self.manager.destroy_lines(lines)
        destroy_mock.assert_called_with(lines)
        line_count = len(await self.manager.all_lines())
        self.assertEqual(line_count, 0)

    async def test_get_lines_for_structure_pair(self):
        lines = [self.interaction_line, self.interaction_line_2]
        self.manager.add_lines(lines)
        line_count = len(await self.manager.all_lines())
        self.assertEqual(line_count, 2)
        structpair_lines_1_2 = self.manager.get_lines_for_structure_pair(
            self.struct1.index, self.struct2.index, existing_lines=lines)
        self.assertEqual(len(structpair_lines_1_2), 1)

        structpair_lines_1_3 = self.manager.get_lines_for_structure_pair(
            self.struct1.index, self.struct3.index, existing_lines=lines)
        self.assertEqual(len(structpair_lines_1_3), 1)

        structpair_lines_2_3 = self.manager.get_lines_for_structure_pair(
            self.struct2.index, self.struct3.index, existing_lines=lines)
        self.assertEqual(len(structpair_lines_2_3), 0)

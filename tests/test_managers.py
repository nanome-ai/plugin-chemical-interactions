import os
import unittest
from unittest.mock import patch
from random import randint

# from unittest.mock import MagicMock
from nanome.api.structure import Complex
from nanome.util import enums
from plugin.managers import ShapesLineManager
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
        self.manager.update_line(line)
        # Ensure update worked
        all_lines = await self.manager.all_lines()
        self.assertEqual(len(all_lines), starting_line_count)
        updated_line = all_lines[0]
        self.assertEqual(updated_line.kind, new_kind)

    @patch('nanome.api.shapes.shape.Shape.upload_multiple')
    def test_upload(self, upload_mock):
        line_list = [self.interaction_line, self.interaction_line_2]
        self.manager.upload(line_list)
        upload_mock.assert_called_with(line_list)

    def test_draw_interaction_line(self):
        breakpoint()
        interaction_kind = enums.InteractionKind.Covalent
        line_settings = default_line_settings[interaction_kind.name]
        line = self.manager.draw_interaction_line(self.struct1, self.struct2, interaction_kind, line_settings)
        self.assertTrue(isinstance(line, InteractionShapesLine))
        self.assertTrue(line.kind, interaction_kind)

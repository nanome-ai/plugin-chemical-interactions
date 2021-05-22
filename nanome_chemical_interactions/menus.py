import nanome
import tempfile
from utils.common import ligands
from functools import partial
from os import environ, path
from nanome.api.structure import Complex

PDBOPTIONS = Complex.io.PDBSaveOptions()
PDBOPTIONS.write_bonds = True

BASE_PATH = path.dirname(path.realpath(__file__))
MENU_PATH = path.join(BASE_PATH, 'menus', 'json', 'menu.json')


class ChemInteractionsMenu():
    def __init__(self, plugin, menu_path=None):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.pdb_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdb", dir=self.temp_dir.name)

        self.interactions_url = environ.get('INTERACTIONS_URL')

        self.plugin = plugin
        self._menu = nanome.ui.Menu.io.from_json(MENU_PATH)
        self.ls_complexes = self._menu.root.find_node('Complex List').get_content()
        self.ls_ligands = self._menu.root.find_node('Ligands List').get_content()
        self.btn_calculate = self._menu.root.find_node('Button').get_content()
        self.btn_calculate.register_pressed_callback(partial(self.get_complexes, self.plugin.get_interactions))
        self.complex_indices = set()

    @property
    def index(self):
        return self._menu.index

    @index.setter
    def index(self, value):
        self._menu.index = value

    @property
    def enabled(self):
        return self._menu.enabled
    
    @enabled.setter
    def enabled(self, value):
        self._menu.enabled = value

    def get_complexes(self, callback, btn=None):
        self.plugin.request_complexes([item.get_content().complex_index for item in self.ls_complexes.items], callback)

    def display_complexes(self, complexes):
        # clear ui and state
        self.plugin.update_menu(self._menu)
        self.ls_complexes.items = []
        self.ls_ligands.items = []
        self.index_to_complex = {}
        # populate ui and state
        for complex in complexes:
            self.index_to_complex[complex.index] = complex
            ln_complex = nanome.ui.LayoutNode()
            btn_complex = ln_complex.add_new_button(complex.name)
            btn_complex.complex_index = complex.index
            btn_complex.ln = ln_complex
            btn_complex.register_pressed_callback(self.toggle_complex)
            self.ls_complexes.items.append(ln_complex)

        # update ui
        self.plugin.update_content(self.ls_complexes)

    def toggle_complex(self, btn_complex):
        # clear ligand list
        self.ls_ligands.items = []

        # toggle the complex
        btn_complex.selected = not btn_complex.selected

        # deselect everything else
        for item in (set(self.ls_complexes.items) - {btn_complex.ln}):
            item.get_content().selected = False

        # modify state
        if btn_complex.selected:
            self.complex_indices.add(btn_complex.complex_index)
            self.plugin.request_complexes([btn_complex.complex_index], self.display_ligands)
        else:
            self.complex_indices.discard(btn_complex.complex_index)

        # update ui
        self.plugin.update_content(self.ls_complexes)
        self.plugin.update_content(self.ls_ligands)

    def toggle_ligand(self, btn_ligand):
           # toggle the button
        btn_ligand.selected = not btn_ligand.selected

        # deselect everything else
        for ln in set(self.ls_ligands.items) - {btn_ligand.ln}:
            ln.get_content().selected = False

        # modify state
        if btn_ligand.selected:
            self.residue = btn_ligand.ligand
        else:
            self.residue = ''

        # update ui
        self.plugin.update_content(self.ls_ligands)
    
    def display_ligands(self, complex):
        complex = complex[0]

        # clear ligands list
        self.ls_ligands.items = []

        # update the complex map for the actual request
        self.index_to_complex[complex.index] = complex

        # populate ligand list
        complex.io.to_pdb(self.pdb_file.name, PDBOPTIONS)
        ligs = ligands(self.pdb_file)
        for lig in ligs:
            ln_ligand = nanome.ui.LayoutNode()
            btn_ligand = ln_ligand.add_new_button(lig.resname)
            btn_ligand.ligand = lig
            btn_ligand.ln = ln_ligand
            btn_ligand.register_pressed_callback(self.toggle_ligand)
            self.ls_ligands.items.append(ln_ligand)

        # update ui
        self.plugin.update_content(self.ls_ligands)
import nanome
import tempfile
from utils.common import ligands
from os import environ, path

from nanome.api.structure import Complex
from nanome.api.ui import Dropdown, DropdownItem, Button, Label
from .forms import InteractionsForm, color_map

PDBOPTIONS = Complex.io.PDBSaveOptions()
PDBOPTIONS.write_bonds = True

BASE_PATH = path.dirname(f'{path.realpath(__file__)}')
MENU_PATH = path.join(BASE_PATH, 'json', 'newMenu.json')


class ChemInteractionsMenu():

    def __init__(self, plugin):
        self.plugin = plugin
        self.interactions_url = environ.get('INTERACTIONS_URL')

        self._menu = nanome.ui.Menu.io.from_json(MENU_PATH)
        self.ls_complexes = self._menu.root.find_node('Complex List').get_content()
        self.ls_ligands = self._menu.root.find_node('Ligands List').get_content()
        self.ls_interactions = self._menu.root.find_node('Interaction Settings List').get_content()
        self.btn_calculate = self._menu.root.find_node('Button').get_content()
        self.btn_calculate.register_pressed_callback(self.submit_form)
        self.complex_indices = set()

    def collect_interaction_data(self):
        """Collect Interaction data from various content widgets."""
        interaction_data = {}
        for row in self.ls_interactions.items:
            content = [ch.get_content() for ch in row.get_children()]
            btn_visibility = next(c for c in content if isinstance(c, Button))
            dd_color = next(c for c in content if isinstance(c, Dropdown))
            lb_name = next(c for c in content if isinstance(c, Label))
            ddi_color = next(item for item in dd_color.items if item.selected)

            name = lb_name.text_value
            visible = True if btn_visibility.selected else False
            color = ddi_color.rgb

            interaction_data[name] = {
                'visible': visible,
                'color': color
            }
        return interaction_data

    def submit_form(self, btn):
        selected_complexes = [
            item.get_content().complex_index
            for item in self.ls_complexes.items
            if item.get_content().selected]

        # ligand = next(
        #     item.get_content().ligand
        #     for item in self.ls_ligands.items
        #     if item.get_content().selected)
        interaction_data = self.collect_interaction_data()
        self.plugin.get_interactions(selected_complexes, self.residue, interaction_data)

    def color_dropdown(self):
        dropdown_items = []
        for name, color_rgb in color_map.items():
            color_hex = '#%02x%02x%02x' % color_rgb
            colored_name = f'<mark={color_hex}>    </mark>{name}'
            dd_item = DropdownItem(colored_name)
            dd_item.rgb = color_rgb
            dropdown_items.append(dd_item)
        dropdown = Dropdown()
        dropdown.max_displayed_items = 12
        dropdown.items = dropdown_items
        return dropdown

    def populate_ls_interactions(self, ls_interactions):
        """Populate the interactions table."""
        form = InteractionsForm()
        interactions = []
        ls_interactions.display_rows = 7
        for name, field in form._fields.items():
            ln = nanome.ui.LayoutNode()
            ln.sizing_type = ln.SizingTypes.expand.value
            ln.layout_orientation = nanome.ui.LayoutNode.LayoutTypes.horizontal.value

            list_item_ln = nanome.ui.LayoutNode()
            ln_btn = list_item_ln.clone()
            ln_btn.add_new_button("")
            btn = ln_btn.get_content()
            btn.selected = True
            btn.text.value.set_all('visible')
            btn.register_pressed_callback(self.toggle_visibility)

            ln_label = list_item_ln.clone()
            ln_label.add_new_label(name)

            ln_dropdown = list_item_ln.clone()
            dropdown = self.color_dropdown()
            ln_dropdown.set_content(dropdown)
            ln_dropdown.forward_dist = .001
            # Select default color in dropdown
            if field.default and field.default.get('color'):
                default_rgb = field.default['color']
                selected_item = next(iter(
                    ddi for ddi in dropdown.items
                    if ddi.rgb == default_rgb
                ), None)
                selected_item.selected = True

            ln.add_child(ln_btn)
            ln.add_child(ln_label)
            ln.add_child(ln_dropdown)
            interactions.append(ln)
        ls_interactions.items = interactions

    def toggle_visibility(self, btn):
        btn.selected = not btn.selected
        txt_selected = 'visible'
        txt_unselected = 'hidden'
        btn_text = txt_selected if btn.selected else txt_unselected
        btn.text.value.set_all(btn_text)
        self.plugin.update_content(btn)
        self.update_interaction_lines()

    def update_interaction_lines(self):
        interaction_data = self.collect_interaction_data()
        self.plugin.update_interaction_lines(interaction_data)

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

        self.populate_ls_interactions(self.ls_interactions)

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
        pdb_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdb")
        complex.io.to_pdb(pdb_file.name, PDBOPTIONS)
        ligs = ligands(pdb_file)
        for lig in ligs:
            ln_ligand = nanome.ui.LayoutNode()
            btn_ligand = ln_ligand.add_new_button(lig.resname)
            btn_ligand.ligand = lig
            btn_ligand.ln = ln_ligand
            btn_ligand.register_pressed_callback(self.toggle_ligand)
            self.ls_ligands.items.append(ln_ligand)

        # update ui
        self.plugin.update_content(self.ls_ligands)

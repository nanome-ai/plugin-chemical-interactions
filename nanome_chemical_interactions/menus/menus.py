import nanome
import tempfile
from Bio.PDB.Residue import Residue as BioResidue
from nanome.util.asyncio import async_callback
from numpy.lib.arraysetops import isin
from utils import extract_ligands
from os import environ, path

from nanome.api.structure import Complex
from nanome.api.ui import Dropdown, DropdownItem, Button, Label
from .forms import InteractionsForm, color_map

PDBOPTIONS = Complex.io.PDBSaveOptions()
PDBOPTIONS.write_bonds = True

BASE_PATH = path.dirname(f'{path.realpath(__file__)}')
MENU_PATH = path.join(BASE_PATH, 'json', 'menu.json')


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

        self.btn_toggle_interactions = self._menu.root.find_node('ln_btn_toggle_interactions').get_content()
        self.btn_toggle_interactions.register_pressed_callback(self.toggle_interactions)
        self.complex_indices = set()

    def create_structure_btns(self, structures):
        """Generate list of buttons corresponding to provided complexes."""
        complex_btns = []
        btn_labels = []

        for struct in structures:
            struct_name = ''
            if isinstance(struct, Complex):
                struct_name = struct.name
            elif isinstance(struct, BioResidue):
                struct_name = struct.resname

            if struct_name not in btn_labels:
                btn_label = struct_name
            else:
                # Find unique struct name.
                letter = 'a'
                while btn_label in btn_labels:
                    btn_label = f'{struct_name} {{{letter}}}'
                    letter = self.next_alpha(letter)
            btn_labels.append(struct_name)
            ln_btn = nanome.ui.LayoutNode()
            btn = ln_btn.add_new_button(btn_label)
            
            if isinstance(struct, Complex):
                btn.complex = struct
                btn.complex_index = struct.index
            elif isinstance(struct, BioResidue):
                btn.ligand = struct

            btn.ln = ln_btn
            complex_btns.append(ln_btn)
        return complex_btns

    @async_callback
    async def render(self, complexes=None):
        complexes = complexes or []
        self.complexes = complexes
        self.populate_ls_interactions()

        self.display_structures(complexes, self.ls_complexes)
        self.display_structures(complexes, self.ls_ligands)

        for ln_btn in self.ls_complexes.items:
            btn = ln_btn.get_content()
            btn.register_pressed_callback(self.toggle_complex)
        
        for ln_btn in self.ls_ligands.items:
            btn = ln_btn.get_content()
            btn.register_pressed_callback(self.toggle_ligand)

        self.plugin.update_menu(self._menu)

    def display_structures(self, complexes, ui_list):
        btns = self.create_structure_btns(complexes)
        ui_list.items = btns
        self.plugin.update_content(ui_list)

    def toggle_interactions(self, btn):
        btn.selected = not btn.selected
        txt_selected = 'Hide All'
        txt_unselected = 'Show all'
        btn_text = txt_selected if btn.selected else txt_unselected
        btn.text.value.set_all(btn_text)

        # Find all the interaction buttons and disable them
        selected_value = btn.selected
        for row in self.ls_interactions.items:
            content = [ch.get_content() for ch in row.get_children()]
            btn = next(c for c in content if isinstance(c, Button))
            btn.selected = selected_value
        self.plugin.update_menu(self._menu)
        self.update_interaction_lines()

    def collect_interaction_data(self):
        """Collect Interaction data from various content widgets."""
        interaction_data = {}
        for row in self.ls_interactions.items:
            line_data = row.line_data

            content = [ch.get_content() for ch in row.get_children()]
            btn_visibility = next(c for c in content if isinstance(c, Button))
            dd_color = next(c for c in content if isinstance(c, Dropdown))
            lb_name = next(c for c in content if isinstance(c, Label))
            ddi_color = next(item for item in dd_color.items if item.selected)

            name = lb_name.field_name
            visible = True if btn_visibility.selected else False
            color = ddi_color.rgb

            interaction_data[name] = {
                **line_data,
                'visible': visible,
                'color': color,
            }
        return interaction_data

    def submit_form(self, btn):
        selected_complex_indices = [
            item.get_content().complex_index
            for item in self.ls_complexes.items
            if item.get_content().selected]

        # Find deep complex saved on button
        selected_complexes = [
            getattr(item.get_content(), 'complex', None)
            for item in self.ls_complexes.items
            if getattr(item.get_content(), 'complex').index in selected_complex_indices
        ]
        selected_residue = getattr(self, 'residue', None)
        residue_complex = getattr(self, 'residue_complex', None)

        error_msg = ''
        if not selected_complexes:
            error_msg = 'Please Select a Complex'
        if selected_complexes and not selected_residue:
            error_msg = 'Please Select a Ligand'
        if error_msg:
            self.plugin.send_notification(nanome.util.enums.NotificationTypes.error, error_msg)
            return
        interaction_data = self.collect_interaction_data()
        self.plugin.get_interactions(selected_complexes, self.residue, residue_complex, interaction_data)

    def color_dropdown(self):
        dropdown_items = []
        for name, color_rgb in color_map.items():
            color_hex = '#%02x%02x%02x' % color_rgb
            colored_name = f'<mark={color_hex}>    </mark> {name}'
            dd_item = DropdownItem(colored_name)
            dd_item.rgb = color_rgb
            dropdown_items.append(dd_item)
        dropdown = Dropdown()
        dropdown.max_displayed_items = 12
        dropdown.items = dropdown_items
        return dropdown

    def populate_ls_interactions(self):
        """Populate the interactions table."""
        form = InteractionsForm()
        interactions = []
        self.ls_interactions.display_rows = 7
        for name, field in form._fields.items():
            ln = nanome.ui.LayoutNode()
            ln.sizing_type = ln.SizingTypes.ratio.value
            ln.layout_orientation = nanome.ui.LayoutNode.LayoutTypes.horizontal.value

            list_item_ln = nanome.ui.LayoutNode()
            ln_btn = list_item_ln.clone()
            ln_btn.add_new_button("")
            ln_btn.set_size_ratio(0.1)
            btn = ln_btn.get_content()

            ln.line_data = field.default
            is_visible = field.default.get('visible', True)
            btn.selected = is_visible
            btn.register_pressed_callback(self.toggle_visibility)

            ln_label = list_item_ln.clone()

            ln_label.add_new_label(field.label.text)
            ln_label.get_content().field_name = name
            ln_label.set_padding(left=0.03)
            ln_label.set_size_ratio(0.5)

            ln_dropdown = list_item_ln.clone()
            dropdown = self.color_dropdown()
            dropdown.register_item_clicked_callback(self.change_interaction_color)
            ln_dropdown.set_content(dropdown)
            ln_dropdown.set_size_ratio(0.4)
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
        self.ls_interactions.items = interactions
        self.plugin.update_content(self.ls_interactions)

    def change_interaction_color(self, dropdown, item):
        self.update_interaction_lines()

    def toggle_visibility(self, btn):
        btn.selected = not btn.selected
        self.plugin.update_content(btn)
        self.update_interaction_lines()

    @async_callback
    async def update_interaction_lines(self):
        interaction_data = self.collect_interaction_data()
        await self.plugin.update_interaction_lines(interaction_data)

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

    @staticmethod
    def next_alpha(s):
        """return next letter alphabetically."""
        return chr((ord(s.upper()) + 1 - 65) % 26 + 65).lower()

    @async_callback
    async def toggle_complex(self, btn):
        # toggle the complex 
        btn.selected = not btn.selected

        # deselect everything else
        for item in (set(self.ls_complexes.items) - {btn.ln}):
            item.get_content().selected = False
        self.plugin.update_content(self.ls_complexes) 

        if btn.selected:
            # Pull out ligands from complex and add them to ligands list
            comp = btn.complex
            deep_complex = next(iter(await self.plugin.request_complexes([comp.index])))
            btn.complex = deep_complex
            # Remove selected complex from ligands list
            for ln in self.ls_ligands.items:
                if ln.get_content().complex.index == comp.index:
                    self.ls_ligands.items.remove(ln)
            
            temp_file = tempfile.NamedTemporaryFile(suffix='.pdb')
            deep_complex.io.to_pdb(temp_file.name, PDBOPTIONS)
            ligands = extract_ligands(temp_file)
            ligand_btns = self.create_structure_btns(ligands)
            for ln_btn in ligand_btns:
                lig_btn = ln_btn.get_content()
                lig_btn.complex = deep_complex
                lig_btn.register_pressed_callback(self.toggle_ligand)
            self.ls_ligands.items.extend(ligand_btns)
        else:
            # Reset ligands list to default if nothing is selected
            ligand_btns = self.create_structure_btns(self.complexes)
            self.ls_ligands.items = ligand_btns
  
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
            self.residue_complex = btn_ligand.complex
        else:
            self.residue = ''

        # update ui
        self.plugin.update_content(self.ls_ligands)

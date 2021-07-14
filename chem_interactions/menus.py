import tempfile
from os import environ, path
from Bio.PDB.Residue import Residue as BioResidue

import nanome
from utils import extract_ligands
from nanome.api.structure import Complex
from nanome.api.ui import Dropdown, DropdownItem, Button, Label, LoadingBar
from nanome.util.asyncio import async_callback
from forms import InteractionsForm, color_map, default_line_settings

PDBOPTIONS = Complex.io.PDBSaveOptions()
PDBOPTIONS.write_bonds = True

BASE_PATH = path.dirname(f'{path.realpath(__file__)}')
MENU_PATH = path.join(BASE_PATH, 'menu_json', 'menu.json')


class ChemInteractionsMenu():

    def __init__(self, plugin):
        self.plugin = plugin
        self.interactions_url = environ.get('INTERACTIONS_URL')
        self._menu = nanome.ui.Menu.io.from_json(MENU_PATH)

        self.ln_complexes = self._menu.root.find_node('Complex Dropdown')
        self.ln_ligands = self._menu.root.find_node('Ligand Dropdown')

        self.ls_interactions = self._menu.root.find_node('Interaction Settings List').get_content()
        self.btn_calculate = self._menu.root.find_node('CalculateButton').get_content()
        self.btn_clear_frame = self._menu.root.find_node('ClearFrameButton').get_content()
        self.btn_calculate.register_pressed_callback(self.submit_form)

        self.btn_show_all_interactions = self._menu.root.find_node('Show All').get_content()
        self.btn_show_all_interactions.register_pressed_callback(self.toggle_atom_selection)

        self.btn_show_selected_interactions = self._menu.root.find_node('Selected Atoms-Residues').get_content()
        self.btn_show_selected_interactions.register_pressed_callback(self.toggle_atom_selection)
        self.ln_loading_bar = self._menu.root.find_node('LoadingBar')

        self.btn_toggle_interactions = self._menu.root.find_node('ln_btn_toggle_interactions').get_content()
        self.btn_toggle_interactions.register_pressed_callback(self.toggle_all_interactions)
        self.btn_clear_frame.register_pressed_callback(self.clear_frame)

    @async_callback
    async def render(self, complexes=None, default_values=False):
        complexes = complexes or []
        self.complexes = complexes

        for comp in self.complexes:
            comp.register_complex_updated_callback(self.on_complex_updated)

        self.render_interaction_form()

        # If we are rendering with default values, get default complex and ligand
        default_complex = None
        if default_values:
            # Find the first complex with selected atoms, and make that the default.
            # I guess that works for now.
            default_complex = next((comp for comp in complexes if any(a.selected for a in comp.atoms)), None)
            if not default_complex and complexes:
                default_complex = complexes[0]

        self.display_structures(complexes, self.ln_complexes, default_structure=default_complex)
        self.display_structures(complexes, self.ln_ligands)

        # Determine whether we should currently be showing the ligand dropdown.
        enable_ligands_node = self.btn_show_all_interactions.selected
        self.toggle_ln_ligands_visibility(enable_ligands_node)

        self.dd_complexes = self.ln_complexes.get_content()
        self.dd_ligands = self.ln_ligands.get_content()
        self.dd_ligands.register_item_clicked_callback(self.update_dropdown)

        self.dd_complexes.register_item_clicked_callback(self.toggle_complex)
        self.plugin.update_menu(self._menu)

    def toggle_ln_ligands_visibility(self, visible=True):
        # Show or hide the ligands dropdown, and the other content inside the parent layout node.
        self.ln_ligands.enabled = visible
        for ln in self.ln_ligands.parent._children:
            ln.enabled = visible


    def display_structures(self, complexes, layoutnode, default_structure=False):
        """Create dropdown of complexes, and add to provided layoutnode."""
        dropdown_items = self.create_structure_dropdown_items(complexes)
        dropdown = Dropdown()
        dropdown.max_displayed_items = 12
        dropdown.items = dropdown_items

        # set default item selected.
        if default_structure:
            for ddi in dropdown.items:
                select_ddi = False
                if isinstance(default_structure, Complex):
                    select_ddi = ddi.complex.index == default_structure.index

                if select_ddi:
                    ddi.selected = True
                    break

        layoutnode.set_content(dropdown)
        self.plugin.update_node(layoutnode)

    def create_structure_dropdown_items(self, structures):
        """Generate list of buttons corresponding to provided complexes."""
        complex_ddis = []
        ddi_labels = set()

        for struct in structures:
            struct_name = ''
            if isinstance(struct, Complex):
                struct_name = struct.full_name
            elif isinstance(struct, BioResidue):
                struct_name = struct.resname

            # # Make sure we have a unique name for every structure
            ddi_label = struct_name
            if ddi_label in ddi_labels:
                num = 1
                while ddi_label in ddi_labels:
                    ddi_label = f'{struct_name} {{{num}}}'
                    num += 1

            ddi_labels.add(ddi_label)
            ddi = DropdownItem(ddi_label)

            if isinstance(struct, Complex):
                ddi.complex = struct
            elif isinstance(struct, BioResidue):
                ddi.ligand = struct

            complex_ddis.append(ddi)

        return complex_ddis

    @async_callback
    async def toggle_all_interactions(self, btn):
        default_state = 0
        show_all_state = 1
        hide_all_state = 2
        # The text shown on the button in given state.
        # A little unintuitive, because the text describes the action in the following state
        # i.e when button in default state, the the text says "Show all"
        txt_default = 'Show All'
        txt_show_all = 'Hide All'
        txt_hide_all = 'Show Default'
        btn_text_map = {
            default_state: txt_default,
            show_all_state: txt_show_all,
            hide_all_state: txt_hide_all,
        }

        if not hasattr(btn, 'state'):
            btn.state = 0

        current_value = btn.state
        new_state = (current_value + 1) % len(btn_text_map.keys())
        btn.state = new_state
        btn_text = btn_text_map[new_state]
        btn.text.value.set_all(btn_text)

        # Show default values
        for row in self.ls_interactions.items:
            content = [ch.get_content() for ch in row.get_children()]
            btn = next(c for c in content if isinstance(c, Button))

            if new_state == default_state:
                # If resetting to default state, lookup visibility from default_line_settings
                lbl_interaction_type = next(c for c in content if isinstance(c, Label))
                interaction_type = lbl_interaction_type.field_name
                selected_value = default_line_settings[interaction_type]['visible']
            else:
                # Show all and hide all states will always be True or False respectively
                selected_value = new_state == show_all_state
            
            btn.selected = selected_value
        
        self.plugin.update_menu(self._menu)
        await self.update_interaction_lines()

    @async_callback
    async def clear_frame(self, btn):
        """Clear all interactions that are currently visible."""
        self.plugin.clear_visible_lines(self.complexes)

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

    @async_callback
    async def submit_form(self, btn):
        """Collect data from menu, and pass to the Plugin to run get_interactions."""
        # Disable calculate button until we are done processing
        btn.unusable = True
        btn.text.value.set_all('Calculating...')
        self.plugin.update_content(btn)
        
        selected_complexes = [
            item.complex
            for item in self.dd_complexes.items
            if item.selected
        ]

        if len(selected_complexes) != 1:
            raise Exception(f'Invalid selected complex count, expected 1, found {len(selected_complexes)}.')

        # Determine selection type (Show all interactions or only selected atoms)
        selected_atoms_only = False
        if self.btn_show_selected_interactions.selected:
            selected_atoms_only = True

        selected_complex = selected_complexes[0]
        ligand_ddis = [item for item in self.dd_ligands.items if item.selected]

        # Determine selection type (Show all interactions or only selected atoms)
        selected_atoms_only = False
        if self.btn_show_selected_interactions.selected:
            selected_atoms_only = True

        residues = []
        residue_complexes = []
        if ligand_ddis:
            for ligand_ddi in ligand_ddis:
                selected_ligand = getattr(ligand_ddi, 'ligand', None)
                if selected_ligand:
                    residues.append(selected_ligand)
                residue_complex = getattr(ligand_ddi, 'complex', None)
                if residue_complex:
                    residue_complexes.append(residue_complex)
        elif selected_atoms_only:
            # Find first complex with selected atoms, and set residue complex to that.
            complexes = await self.plugin.request_complexes([c.index for c in self.complexes])
            for comp in complexes:
                if any([a.selected for a in comp.atoms]):
                    residue_complexes.append(comp)
        else:
            # If no ligand selected, Try to get from selected complex.
            residue_complexes.append(selected_complex)

        error_msg = ''
        if not selected_complexes:
            error_msg = 'Please Select a Complex'

        if error_msg:
            self.plugin.send_notification(nanome.util.enums.NotificationTypes.error, error_msg)
            return


        # Get up to date selected_complex
        selected_complex = next(iter(await self.plugin.request_complexes([selected_complex.index])))
        self.update_complex_data(selected_complex)

        # Get up to date residue_complex
        for residue_complex in residue_complexes:
            residue_complex = next(iter(await self.plugin.request_complexes([residue_complex.index])))
            self.update_complex_data(residue_complex)

        loading_bar = LoadingBar()
        self.ln_loading_bar.set_content(loading_bar)
        self.plugin.update_node(self.ln_loading_bar)

        interaction_data = self.collect_interaction_data()

        try:
            await self.plugin.calculate_interactions(
                selected_complex, residue_complexes, interaction_data,
                ligands=residues, selected_atoms_only=selected_atoms_only)
        except Exception:
            msg = 'Error occurred, please check logs'
            self.plugin.send_notification(
                nanome.util.enums.NotificationTypes.error, msg)

            btn.unusable = False
            btn.text.value.set_all('Calculate')
            self.plugin.update_content(btn)
            raise

        self.ln_loading_bar.set_content(None)
        self.plugin.update_node(self.ln_loading_bar)

        btn.unusable = False
        btn.text.value.set_all('Calculate')
        self.plugin.update_content(btn)

    def update_loading_bar(self, current, total):
        loading_bar = self.ln_loading_bar.get_content()
        loading_bar.percentage = current / total
        self.plugin.update_content(loading_bar)

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

    def render_interaction_form(self):
        """Populate the interaction type form."""
        form = InteractionsForm()
        interactions = []
        self.ls_interactions.display_rows = 7
        for name, field in form._fields.items():
            ln = nanome.ui.LayoutNode()
            ln.sizing_type = ln.SizingTypes.ratio.value
            ln.layout_orientation = nanome.ui.LayoutNode.LayoutTypes.horizontal.value

            list_item_ln = nanome.ui.LayoutNode()
            ln_btn = list_item_ln.clone()
            ln_btn.set_padding(left=0.01)
            ln_btn.add_new_button("")
            ln_btn.set_size_ratio(0.07)
            ln_btn.toggle_on_press = True

            btn = ln_btn.get_content()
            btn.mesh.active = True
            btn.mesh.enabled.set_all(False)
            btn.mesh.enabled.set_each(selected=True)
            btn.mesh.color.set_each(selected=btn.outline.color.selected)
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

    @async_callback
    async def toggle_visibility(self, btn):
        btn.selected = not btn.selected
        self.plugin.update_content(btn)
        await self.update_interaction_lines()

    @async_callback
    async def update_interaction_lines(self):
        interaction_data = self.collect_interaction_data()
        await self.plugin.update_interaction_lines(interaction_data, self.complexes)

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

    def update_dropdown(self, dropdown, item):
        self.plugin.update_content(dropdown)
        return

    @async_callback
    async def toggle_complex(self, dropdown, item):
        """When Complex selected, add complex ligands as structure choices."""
        ligand_ddis = []
        if item and item.selected and self.ln_ligands.enabled:
            # Pull out ligands from complex and add them to ligands list
            # Make button unusable until ligand extraction is done.
            self.btn_calculate.unusable = True
            self.btn_calculate.text.value.set_all('Extracting Ligands...')
            self.plugin.update_content(self.btn_calculate)

            ligand_ddis = self.create_structure_dropdown_items(self.complexes)
            comp = item.complex
            if len(list(comp.molecules)) == 0:
                deep_complex = next(iter(await self.plugin.request_complexes([comp.index])))
                self.update_complex_data(deep_complex)
            else:
                deep_complex = comp
            item.complex = deep_complex

            # Find ligands nested inside of complex, and add buttons for them.
            temp_file = tempfile.NamedTemporaryFile(suffix='.pdb')
            deep_complex.io.to_pdb(temp_file.name, PDBOPTIONS)
            ligands = extract_ligands(temp_file)
            new_ligand_ddis = self.create_structure_dropdown_items(ligands)
            # Also store complex information on the dropdown items.
            for ddi in new_ligand_ddis:
                ddi.complex = deep_complex
            ligand_ddis.extend(new_ligand_ddis)
        else:
            ligand_ddis = self.create_structure_dropdown_items(self.complexes)

        self.dd_ligands.items = ligand_ddis
        self.btn_calculate.unusable = False
        self.btn_calculate.text.value.set_all('Calculate')
        self.plugin.update_content(self.btn_calculate)
        self.plugin.update_content(self.dd_ligands)

    def on_complex_updated(self, complex):
        # Update complex in self.complexes, and redraw lines
        self.update_complex_data(complex)
        self.update_interaction_lines()

    def update_complex_data(self, new_complex):
        """Replace complex in self.complexes with updated data."""
        for i, comp in enumerate(self.complexes):
            if comp.index == new_complex.index:
                self.complexes[i] = new_complex
                self.complexes[i].register_complex_updated_callback(self.on_complex_updated)
                return

    def toggle_atom_selection(self, btn):
        # Toggle selected button
        btn.selected = not btn.selected
        self.plugin.update_content(btn)

        # Make sure other button is set to opposite of pressed button (Only one can be selected at a time)
        button_group = [self.btn_show_all_interactions, self.btn_show_selected_interactions]
        for button in button_group:
            if button.name != btn.name:
                button.selected = not btn.selected
                self.plugin.update_content(button)

        # Make sure ligand label and dropdown are usable when show all interactions is selected.
        enable_ligands_node = self.btn_show_all_interactions.selected
        if enable_ligands_node:
            item = next((ddi for ddi in self.dd_complexes.items if ddi.selected), None)
            self.toggle_complex(self.dd_complexes, item)
        self.toggle_ln_ligands_visibility(enable_ligands_node)
        self.plugin.update_menu(self._menu)

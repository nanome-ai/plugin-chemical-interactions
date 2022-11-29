from os import environ, path

import nanome
from nanome.api.structure import Complex
from nanome.api.structure.substructure import Substructure
from nanome.api.ui import Dropdown, DropdownItem, Button, Label
from nanome.util import async_callback, Logs
from nanome.util.enums import NotificationTypes
from .forms import LineSettingsForm, color_map, default_line_settings

PDBOPTIONS = Complex.io.PDBSaveOptions()
PDBOPTIONS.write_bonds = True

BASE_PATH = path.dirname(f'{path.realpath(__file__)}')
MENU_PATH = path.join(BASE_PATH, 'menu_json', 'menu.json')
SETTINGS_MENU_PATH = path.join(BASE_PATH, 'menu_json', 'settings.json')


class ChemInteractionsMenu():

    def __init__(self, plugin):
        self.plugin = plugin
        self.interactions_url = environ.get('INTERACTIONS_URL')
        self._menu = nanome.ui.Menu.io.from_json(MENU_PATH)

        self.ln_complexes = self._menu.root.find_node('Complex Dropdown')
        self.ln_ligands = self._menu.root.find_node('Ligand Dropdown')

        self.ls_interactions = self._menu.root.find_node('Interaction Settings List').get_content()
        self.btn_calculate = self._menu.root.find_node('CalculateButton').get_content()
        self.btn_calculate.register_pressed_callback(self.submit_form)
        self.btn_calculate.disable_on_press = True

        self.btn_clear_frame = self._menu.root.find_node('ClearFrameButton').get_content()
        self.btn_clear_frame.register_pressed_callback(self.clear_frame)

        self.btn_distance_labels = self._menu.root.find_node('Show Distances').get_content()
        self.btn_distance_labels.toggle_on_press = True
        self.btn_distance_labels.switch.active = True

        self.btn_distance_labels.register_pressed_callback(self.toggle_distance_labels)

        self.btn_show_all_interactions = self._menu.root.find_node('Show All').get_content()
        self.btn_show_all_interactions.register_pressed_callback(self.toggle_atom_selection)

        self.btn_show_selected_interactions = self._menu.root.find_node('Selected Atoms-Residues').get_content()
        self.btn_show_selected_interactions.register_pressed_callback(self.toggle_atom_selection)
        self.ln_loading_bar = self._menu.root.find_node('LoadingBar')

        self.btn_toggle_interactions = self._menu.root.find_node('Toggle Display').get_content()
        self.btn_toggle_interactions.register_pressed_callback(self.toggle_all_interactions)

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
            elif isinstance(struct, Substructure):
                struct_name = struct.name

            # Make sure we have a unique name for every structure
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
            elif isinstance(struct, Substructure):
                ddi.ligand = list(struct.residues)
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
        btn.unusable = True
        self.plugin.update_content(btn)

        Logs.message('Clearing Frame Interactions')
        await self.plugin.clear_visible_lines(self.complexes)
        btn.unusable = False
        self.plugin.update_content(btn)

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

    def reset_calculate_btn(self):
        self.btn_calculate.unusable = False
        self.btn_calculate.text.value.set_all('Calculate')
        self.plugin.update_content(self.btn_calculate)

    @async_callback
    async def submit_form(self, btn):
        """Collect data from menu, and pass to the Plugin to run get_interactions."""
        # Disable calculate button until we are done processing
        Logs.message("Submit button pressed")
        btn.unusable = True
        btn.text.value.set_all('Calculating...')
        self.plugin.update_content(btn)

        selected_complexes = [
            item.complex
            for item in self.dd_complexes.items
            if item.selected
        ]

        if not selected_complexes:
            self.plugin.send_notification(NotificationTypes.error, 'Please Select a Complex.')
            self.reset_calculate_btn()
            return

        selected_complex = selected_complexes[0]
        ligand_ddis = [item for item in self.dd_ligands.items if item.selected]

        # Determine selection type (Show all interactions or only selected atoms)
        selected_atoms_only = False
        if self.btn_show_selected_interactions.selected:
            selected_atoms_only = True

        ligand_residues = []
        if ligand_ddis:
            for ligand_ddi in ligand_ddis:
                selected_ligand = getattr(ligand_ddi, 'ligand', None)
                if selected_ligand:
                    # Should be a list of residues
                    ligand_residues.extend(selected_ligand)

                residue_complex = getattr(ligand_ddi, 'complex', None)
                if residue_complex and not selected_ligand:
                    deep_comp = (await self.plugin.request_complexes([residue_complex.index]))[0]
                    self.update_complex_data(deep_comp)
                    ligand_residues.extend(list(deep_comp.residues))
        elif selected_atoms_only:
            # Find first complex with selected atoms, and set residue complex to that.
            complexes = await self.plugin.request_complexes([c.index for c in self.complexes])
            for comp in complexes:
                self.update_complex_data(comp)
                for rez in comp.residues:
                    if any(a.selected for a in rez.atoms):
                        ligand_residues.append(rez)
        else:
            # If no ligand selected from dropdown, and not atom selection mode, raise error
            self.plugin.send_notification(NotificationTypes.error, 'Please Select a Ligand.')
            self.reset_calculate_btn()
            return

        error_msg = ''
        if not selected_complexes:
            error_msg = 'Please Select a Complex'
            self.plugin.send_notification(NotificationTypes.error, error_msg)
            return

        # Get up to date selected_complex
        selected_complex = next(iter(await self.plugin.request_complexes([selected_complex.index])))
        if selected_complex:
            self.update_complex_data(selected_complex)
        interaction_data = self.collect_interaction_data()

        distance_labels = self.btn_distance_labels.selected
        await self.run_calculation(
            selected_complex, ligand_residues, interaction_data,
            selected_atoms_only, distance_labels)

    async def run_calculation(
        self, selected_complex, ligand_residues, interaction_data,
            selected_atoms_only=True, distance_labels=False):

        if not self.btn_calculate.unusable:
            self.btn_calculate.unusable = True
            self.btn_calculate.text.value.set_all('Calculating...')
            self.plugin.update_content(self.btn_calculate)

        loading_bar = self.ln_loading_bar.get_content()
        loading_bar.percentage = 0.0
        self.ln_loading_bar.enabled = True
        self.plugin.update_node(self.ln_loading_bar)

        try:
            await self.plugin.calculate_interactions(
                selected_complex, ligand_residues, interaction_data,
                selected_atoms_only=selected_atoms_only, distance_labels=distance_labels)
        except Exception:
            msg = 'Error occurred, please check logs'
            self.plugin.send_notification(
                nanome.util.enums.NotificationTypes.error, msg)
            self.reset_calculate_btn()
            raise

        self.ln_loading_bar.enabled = False
        loading_bar.percentage = 0.0
        self.plugin.update_node(self.ln_loading_bar)
        self.reset_calculate_btn()

    def update_loading_bar(self, current, total):
        loading_bar = self.ln_loading_bar.get_content()
        loading_bar.percentage = current / total
        self.plugin.update_content(loading_bar)

    def color_dropdown(self):
        dropdown_items = []
        for name, color_rgb in color_map.items():
            color_hex = '#%02x%02x%02x' % color_rgb
            colored_name = f'<color={color_hex}>■</color> {name}'
            dd_item = DropdownItem(colored_name)
            dd_item.rgb = color_rgb
            dropdown_items.append(dd_item)
        dropdown = Dropdown()
        dropdown.max_displayed_items = 12
        dropdown.items = dropdown_items
        return dropdown

    def render_interaction_form(self):
        """Populate the interaction type form."""
        form = LineSettingsForm()
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
        # Log the interaction being toggled
        for item in self.ls_interactions.items:
            item_btn = item.get_children()[0].get_content()
            if item_btn._content_id == btn._content_id:
                item_lbl = item.get_children()[1].get_content()
                interaction_type = item_lbl.text_value
                Logs.message(f"{'Showing' if btn.selected else 'Hiding'} {interaction_type} interactions")
                break

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

    def set_update_text(self, btn_text):
        """Allows Plugin to set button text to provide user with status updates."""
        self.btn_calculate.text.value.set_all(btn_text)
        self.plugin.update_content(self.btn_calculate)

    @async_callback
    async def toggle_complex(self, dropdown, item):
        """When Complex selected, add complex ligands as structure choices."""
        ligand_ddis = []
        if item and item.selected and self.ln_ligands.enabled:
            # Extract ligands from complex and add them to ligands list
            # Make button unusable until ligand extraction is done.
            self.btn_calculate.unusable = True
            self.btn_calculate.text.value.set_all('Extracting Ligands...')
            self.plugin.update_content(self.btn_calculate)

            ligand_ddis = self.create_structure_dropdown_items(self.complexes)
            comp = item.complex
            if sum(1 for _ in comp.molecules) == 0:
                deep_complex = (await self.plugin.request_complexes([comp.index]))[0]
                self.update_complex_data(deep_complex)
            else:
                deep_complex = comp
            item.complex = deep_complex

            # Find ligands nested inside of complex, and add them to dropdown.
            mol = next(
                mol for i, mol in enumerate(deep_complex.molecules)
                if i == deep_complex.current_frame
            )
            ligands = await mol.get_ligands()
            for ligand in ligands:
                # make sure complex is stored on residue, we will need it later
                for residue in ligand.residues:
                    # Find the chain that this residue belongs to, and set parent
                    rez_chain = next(
                        chain for chain in mol.chains
                        if chain.name == residue.chain.name
                    )
                    residue._parent = rez_chain

            new_ligand_ddis = self.create_structure_dropdown_items(ligands)
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

    @async_callback
    async def toggle_distance_labels(self, btn):
        if btn.selected:
            Logs.message("Showing distance labels")
            await self.plugin.render_distance_labels(self.complexes)
        else:
            Logs.message("Hiding distance labels")
            self.plugin.clear_distance_labels()


class SettingsMenu:

    def __init__(self, plugin):
        self.plugin = plugin
        self._menu = nanome.ui.Menu.io.from_json(SETTINGS_MENU_PATH)
        self._menu.index = 200
        self.btn_recalculate_on_update.switch.active = True
        # self.btn_recalculate_on_update.toggle_on_press = True
        self.btn_recalculate_on_update.register_pressed_callback(self.toggle_recalculate_on_update)

    def render(self):
        self._menu.enabled = True
        self.plugin.update_menu(self._menu)

    @property
    def btn_recalculate_on_update(self):
        return self._menu.root.find_node('btn_recalculate_on_update').get_content()

    def get_settings(self):
        recalculate_on_update = self.btn_recalculate_on_update.selected
        return {
            'recalculate_on_update': recalculate_on_update
        }

    def toggle_recalculate_on_update(self, btn):
        btn.selected = not btn.selected
        Logs.message("Set Recalculate on Update to: {}".format(btn.selected))
        # If button is toggled off, clear the previous run from memory
        if not btn.selected and hasattr(self.plugin, 'previous_run'):
            Logs.message("Clearing previous run from memory")
            del self.plugin.previous_run
        self.plugin.update_content(btn)

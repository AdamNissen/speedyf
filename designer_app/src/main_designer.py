import sys
import json # For saving/loading project
import uuid # For generating unique IDs

# QtWidgets - QActionGroup removed from here
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, 
                             QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, 
                             QMessageBox, QScrollArea, QSizePolicy, 
                             QToolBar, QFormLayout, QLineEdit, QDialog, QDialogButtonBox) 
                             # Added QFormLayout, QLineEdit, QDialog, QDialogButtonBox from previous steps

# QtGui - QActionGroup added here
from PyQt6.QtGui import (QPixmap, QImage, QPainter, QPen, QAction, QIcon, 
                         QKeySequence, QActionGroup, QBrush, QColor) # Added QActionGroup

from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal
import fitz  # PyMuPDF

class AreaPropertiesDialog(QDialog):
    def __init__(self, area_type, default_data_field_id="", default_prompt="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Area Properties")

        self.area_type = area_type

        # Main layout for the dialog
        layout = QVBoxLayout(self)

        # Form layout for input fields
        form_layout = QFormLayout()

        self.type_label = QLabel(f"Type: {self.area_type}")
        # We could make this bold or styled if desired
        # self.type_label.setStyleSheet("font-weight: bold;")
        form_layout.addRow(self.type_label) # Just display the type

        self.data_field_id_input = QLineEdit(self)
        self.data_field_id_input.setText(default_data_field_id)
        form_layout.addRow("Data Field Name/Link ID:", self.data_field_id_input)

        self.prompt_input = QLineEdit(self) # Or QTextEdit for multi-line prompts later
        self.prompt_input.setText(default_prompt)
        form_layout.addRow("Prompt for End-User:", self.prompt_input)

        layout.addLayout(form_layout)

        # Standard OK and Cancel buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | 
                                           QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept) # Connect OK to accept
        self.button_box.rejected.connect(self.reject) # Connect Cancel to reject

        layout.addWidget(self.button_box)

        #self.setLayout(layout)
        self.setMinimumWidth(350) # Set a reasonable minimum width

    def getProperties(self):
        # Return the entered properties if dialog was accepted
        if self.result() == QDialog.DialogCode.Accepted:
            return {
                "data_field_id": self.data_field_id_input.text().strip(),
                "prompt": self.prompt_input.text().strip()
                # 'type' is already known by the caller (DesignerApp)
            }
        return None # Or raise an exception, or return an empty dict

class Command: # A conceptual base class, or just an informal interface for now
    def __init__(self, app_context, description="Generic Command"):
        self.app = app_context # Reference to DesignerApp
        self.description = description # For potential logging or UI display

    def execute(self):
        raise NotImplementedError("Subclasses should implement this!")

    def undo(self):
        raise NotImplementedError("Subclasses should implement this!")

    def __str__(self): # For debugging
        return self.description


class DeleteAreaCommand(Command):
    def __init__(self, app_context, instance_id_to_delete):
        super().__init__(app_context, f"Delete Area: {instance_id_to_delete}")
        self.instance_id = instance_id_to_delete
        self.deleted_area_info = None # To store the full dict of the deleted area
        self.original_index = -1      # To store its original index in the list for proper undo

    def execute(self):
        # Find the area and store its data and index before deleting
        found = False
        for i, area_info in enumerate(self.app.defined_pdf_areas):
            if area_info['instance_id'] == self.instance_id:
                self.deleted_area_info = area_info.copy() # Store a copy
                self.original_index = i
                
                # 1. Remove from data model
                del self.app.defined_pdf_areas[i]
                print(f"Command: Data for area {self.instance_id} removed from defined_pdf_areas.")
                found = True
                break
        
        if not found:
            print(f"Command Error: Could not find data for area ID {self.instance_id} to delete.")
            # This command instance is now invalid, perhaps raise an error or handle
            # For now, it just means execute did nothing to the main data.
            # The undo stack should probably not get this command if execute effectively fails.
            # We'll refine executeCommand later if needed.
            return False # Indicate failure

        # 2. Remove visual representation
        page_num_of_deleted_area = self.deleted_area_info['page_num']
        removed_visual = self.app.pdf_display_label.removeVisualRectById(page_num_of_deleted_area, self.instance_id)
        if removed_visual:
            print(f"Command: Visual for area {self.instance_id} on page {page_num_of_deleted_area + 1} removed.")
        else:
            print(f"Command Warning: Visual for area {self.instance_id} on page {page_num_of_deleted_area + 1} not found for removal.")

        # 3. Clear selection if the deleted item was selected
        if self.app.currently_selected_area_instance_id == self.instance_id:
            self.app.handleAreaSelectionChanged(None) 
            # This also updates UI like disabling delete/edit buttons

        self.app.statusBar().showMessage(f"Area {self.instance_id} deleted.", 3000)
        return True # Indicate success

    def undo(self):
        if self.deleted_area_info is None or self.original_index == -1:
            print(f"Command Error: No data to undo deletion for area ID {self.instance_id}.")
            return False # Indicate failure

        # 1. Re-insert into data model at original position
        self.app.defined_pdf_areas.insert(self.original_index, self.deleted_area_info)
        print(f"Command: Data for area {self.instance_id} restored to defined_pdf_areas.")

        # 2. Re-add visual representation
        page_num = self.deleted_area_info['page_num']
        # view_qrect_tuple needs to be converted back to QRect
        vqt = self.deleted_area_info['view_qrect_tuple']
        view_qrect = QRect(vqt[0], vqt[1], vqt[2], vqt[3])
        area_type = self.deleted_area_info['type']
        
        self.app.pdf_display_label.addVisualRect(page_num, view_qrect, self.instance_id, area_type)
        print(f"Command: Visual for area {self.instance_id} on page {page_num + 1} restored.")

        # 3. Optionally, re-select the restored item (or clear selection)
        # For simplicity, let's clear selection after undoing a delete
        # Or, if DesignerApp's handleAreaSelectionChanged is robust, this might not be needed
        # if self.app.currently_selected_area_instance_id is not None:
        #     self.app.handleAreaSelectionChanged(None) 
        # Let's assume selection remains cleared after an undo of delete for now.
        # The user can re-select if needed.

        self.app.statusBar().showMessage(f"Deletion of area {self.instance_id} undone.", 3000)
        return True # Indicate success

class AddAreaCommand(Command):
    def __init__(self, app_context, area_info_to_add):
        super().__init__(app_context, f"Add Area: {area_info_to_add.get('data_field_id', area_info_to_add.get('instance_id', 'Unknown'))}")
        self.area_info = area_info_to_add # This dict contains all necessary info

    def execute(self):
        # 1. Add to data model
        self.app.defined_pdf_areas.append(self.area_info)
        print(f"Command: Area {self.area_info['instance_id']} added to defined_pdf_areas.")

        # 2. Add visual representation
        page_num = self.area_info['page_num']
        vqt = self.area_info['view_qrect_tuple']
        view_qrect = QRect(vqt[0], vqt[1], vqt[2], vqt[3])
        instance_id = self.area_info['instance_id']
        
        # **** FETCH area_type AND VISUAL PROPS FROM self.area_info ****
        area_type = self.area_info['type'] 
        outline_rgba = self.area_info.get('outline_color_rgba') # .get() for safety if not present
        fill_rgba = self.area_info.get('fill_color_rgba')
        outline_w = self.area_info.get('outline_width')
        
        self.app.pdf_display_label.addVisualRect(
            page_num, 
            view_qrect, 
            instance_id, 
            area_type, # Now defined
            outline_color_rgba=outline_rgba,
            fill_color_rgba=fill_rgba,
            outline_width=outline_w
        )
        print(f"Command: Visual for area {instance_id} on page {page_num + 1} added.")
        self.app.statusBar().showMessage(f"Area '{self.area_info.get('data_field_id', instance_id)}' added.", 3000)
        return True

    def undo(self):
        removed_from_data = False
        for i, area in enumerate(self.app.defined_pdf_areas):
            if area['instance_id'] == self.area_info['instance_id']:
                del self.app.defined_pdf_areas[i]
                removed_from_data = True
                print(f"Command Undo: Area {self.area_info['instance_id']} removed from defined_pdf_areas.")
                break
        
        if not removed_from_data:
            print(f"Command Undo Error: Could not find {self.area_info['instance_id']} in defined_pdf_areas.")
            return False

        page_num = self.area_info['page_num']
        instance_id = self.area_info['instance_id']
        self.app.pdf_display_label.removeVisualRectById(page_num, instance_id)
        print(f"Command Undo: Visual for area {instance_id} on page {page_num + 1} removed.")

        if self.app.currently_selected_area_instance_id == instance_id:
            self.app.handleAreaSelectionChanged(None)

        self.app.statusBar().showMessage(f"Addition of area '{self.area_info.get('data_field_id', instance_id)}' undone.", 3000)
        return True

    def undo(self):
        # 1. Remove from data model (find by instance_id)
        removed_from_data = False
        for i, area in enumerate(self.app.defined_pdf_areas):
            if area['instance_id'] == self.area_info['instance_id']:
                del self.app.defined_pdf_areas[i]
                removed_from_data = True
                print(f"Command Undo: Area {self.area_info['instance_id']} removed from defined_pdf_areas.")
                break
        
        if not removed_from_data:
            print(f"Command Undo Error: Could not find {self.area_info['instance_id']} in defined_pdf_areas.")
            return False

        # 2. Remove visual representation
        page_num = self.area_info['page_num']
        instance_id = self.area_info['instance_id']
        self.app.pdf_display_label.removeVisualRectById(page_num, instance_id)
        print(f"Command Undo: Visual for area {instance_id} on page {page_num + 1} removed.")

        # 3. Clear selection if this undone area was selected
        if self.app.currently_selected_area_instance_id == instance_id:
            self.app.handleAreaSelectionChanged(None)

        self.app.statusBar().showMessage(f"Addition of area '{self.area_info['data_field_id']}' undone.", 3000)
        return True # Indicate success

class EditAreaPropertiesCommand(Command):
    def __init__(self, app_context, instance_id, old_properties, new_properties):
        # old_properties and new_properties should be dicts like {'data_field_id': ..., 'prompt': ...}
        super().__init__(app_context, f"Edit Properties: {instance_id}")
        self.instance_id = instance_id
        self.old_props = old_properties # e.g., {'data_field_id': 'old_name', 'prompt': 'old_prompt'}
        self.new_props = new_properties # e.g., {'data_field_id': 'new_name', 'prompt': 'new_prompt'}
        self.area_index = -1 # To store the index of the area in defined_pdf_areas

    def _find_area_and_index(self):
        """Helper to find the area and its index."""
        for i, area_info in enumerate(self.app.defined_pdf_areas):
            if area_info['instance_id'] == self.instance_id:
                self.area_index = i
                return area_info
        return None

    def execute(self):
        area_info = self._find_area_and_index()
        if area_info is None:
            print(f"Command Error: Area {self.instance_id} not found for editing properties.")
            return False

        # Store old properties if not already (e.g., if execute is called for redo)
        # However, old_props should be captured before the first execute.
        # For simplicity, we assume __init__ received correct old_props.

        # Apply new properties
        area_info['data_field_id'] = self.new_props['data_field_id']
        area_info['prompt'] = self.new_props['prompt']
        # Note: 'type', 'page_num', 'rect_pdf', 'view_qrect_tuple' are not changed by this command.
        
        print(f"Command: Properties for area {self.instance_id} updated to DataFieldID='{self.new_props['data_field_id']}', Prompt='{self.new_props['prompt']}'.")
        self.app.statusBar().showMessage(f"Properties for area {self.instance_id} updated.", 3000)
        
        # If visual representation depends on these properties (e.g., a label showing data_field_id on the rect),
        # we might need to trigger a repaint or update of that specific visual item.
        # For now, our blue boxes don't change based on this metadata.
        # self.app.pdf_display_label.update() # May not be needed if no visual change
        
        return True # Indicate success

    def undo(self):
        area_info = self._find_area_and_index() # Index should still be valid
        if area_info is None:
            # This would be a more serious issue, implies data inconsistency
            print(f"Command Undo Error: Area {self.instance_id} not found for undoing property edit.")
            return False

        # Revert to old properties
        area_info['data_field_id'] = self.old_props['data_field_id']
        area_info['prompt'] = self.old_props['prompt']

        print(f"Command Undo: Properties for area {self.instance_id} reverted to DataFieldID='{self.old_props['data_field_id']}', Prompt='{self.old_props['prompt']}'.")
        self.app.statusBar().showMessage(f"Edit of area {self.instance_id} properties undone.", 3000)

        # If visual representation depends on these properties, trigger update
        # self.app.pdf_display_label.update()

        return True # Indicate success

class MoveAreaCommand(Command):
    def __init__(self, app_context, instance_id, page_num, 
                 old_view_rect_tuple, new_view_rect_tuple, 
                 old_pdf_rect_tuple, new_pdf_rect_tuple):
        super().__init__(app_context, f"Move Area: {instance_id}")
        self.instance_id = instance_id
        self.page_num = page_num # Page number of the moved area

        # Store both view and PDF coordinates for old and new states
        self.old_view_rect_tuple = old_view_rect_tuple
        self.new_view_rect_tuple = new_view_rect_tuple
        self.old_pdf_rect_tuple = old_pdf_rect_tuple
        self.new_pdf_rect_tuple = new_pdf_rect_tuple
        
        self.area_index = -1 # To find the area quickly if needed

    def _apply_state(self, pdf_rect_tuple, view_rect_tuple):
        """Helper to apply a given state (PDF and view rects) to the area."""
        found = False
        for i, area_info in enumerate(self.app.defined_pdf_areas):
            if area_info['instance_id'] == self.instance_id:
                self.area_index = i # Store index for potential future use
                area_info['rect_pdf'] = pdf_rect_tuple
                area_info['view_qrect_tuple'] = view_rect_tuple
                
                # Update visual representation in InteractivePdfLabel
                # Convert view_qrect_tuple back to QRect for the label
                vqt = view_rect_tuple
                view_qrect = QRect(vqt[0], vqt[1], vqt[2], vqt[3])
                self.app.pdf_display_label.updateVisualRectPositionAndStyle(
                    self.page_num, 
                    self.instance_id, 
                    new_rect=view_qrect
                )
                found = True
                break
        return found

    def execute(self):
        if not self._apply_state(self.new_pdf_rect_tuple, self.new_view_rect_tuple):
            print(f"Command Error: Area {self.instance_id} not found for move execute.")
            return False
        
        print(f"Command: Area {self.instance_id} moved to PDF Rect: {self.new_pdf_rect_tuple}.")
        self.app.statusBar().showMessage(f"Area {self.instance_id} moved.", 3000)
        return True

    def undo(self):
        if not self._apply_state(self.old_pdf_rect_tuple, self.old_view_rect_tuple):
            print(f"Command Error: Area {self.instance_id} not found for move undo.")
            return False

        print(f"Command Undo: Area {self.instance_id} move reverted to PDF Rect: {self.old_pdf_rect_tuple}.")
        self.app.statusBar().showMessage(f"Move of area {self.instance_id} undone.", 3000)
        return True

class ResizeAreaCommand(Command):
    def __init__(self, app_context, instance_id, page_num, 
                 old_view_rect_tuple, new_view_rect_tuple, 
                 old_pdf_rect_tuple, new_pdf_rect_tuple):
        super().__init__(app_context, f"Resize Area: {instance_id}")
        self.instance_id = instance_id
        self.page_num = page_num

        # Store both view and PDF coordinates for old and new states
        self.old_view_rect_tuple = old_view_rect_tuple
        self.new_view_rect_tuple = new_view_rect_tuple
        self.old_pdf_rect_tuple = old_pdf_rect_tuple
        self.new_pdf_rect_tuple = new_pdf_rect_tuple
        
        self.area_index = -1 # To find the area quickly if needed (optional)

    def _apply_state(self, pdf_rect_tuple, view_rect_tuple):
        """Helper to apply a given state (PDF and view rects) to the area."""
        found = False
        for i, area_info in enumerate(self.app.defined_pdf_areas):
            if area_info['instance_id'] == self.instance_id:
                self.area_index = i 
                area_info['rect_pdf'] = pdf_rect_tuple
                area_info['view_qrect_tuple'] = view_rect_tuple
                
                # Update visual representation in InteractivePdfLabel
                vqt = view_rect_tuple
                view_qrect = QRect(vqt[0], vqt[1], vqt[2], vqt[3])
                # We re-use the same method as for moving, as it updates the rect
                self.app.pdf_display_label.updateVisualRectPositionAndStyle(
                    self.page_num, 
                    self.instance_id, 
                    new_rect=view_qrect 
                    # No need to pass new_type, as type doesn't change on resize
                )
                found = True
                break
        return found

    def execute(self):
        if not self._apply_state(self.new_pdf_rect_tuple, self.new_view_rect_tuple):
            print(f"Command Error: Area {self.instance_id} not found for resize execute.")
            return False
        
        print(f"Command: Area {self.instance_id} resized to PDF Rect: {self.new_pdf_rect_tuple}.")
        self.app.statusBar().showMessage(f"Area {self.instance_id} resized.", 3000)
        return True

    def undo(self):
        if not self._apply_state(self.old_pdf_rect_tuple, self.old_view_rect_tuple):
            print(f"Command Error: Area {self.instance_id} not found for resize undo.")
            return False

        print(f"Command Undo: Area {self.instance_id} resize reverted to PDF Rect: {self.old_pdf_rect_tuple}.")
        self.app.statusBar().showMessage(f"Resize of area {self.instance_id} undone.", 3000)
        return True

# For handle identification (place these constants outside/before the class)
HANDLE_SIZE = 8
H_TOP_LEFT, H_TOP_MIDDLE, H_TOP_RIGHT, \
H_MIDDLE_LEFT, H_MIDDLE_RIGHT, \
H_BOTTOM_LEFT, H_BOTTOM_MIDDLE, H_BOTTOM_RIGHT = range(8)

class InteractivePdfLabel(QLabel):
    rectDefinedSignal = pyqtSignal(QRect)
    areaSelectionChangedSignal = pyqtSignal(object) 
    areaMovedSignal = pyqtSignal(str, QRect)
    areaResizedSignal = pyqtSignal(str, QRect)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent # Should be DesignerApp instance
        self.setMouseTracking(True)
        
        self.current_rubber_band_rect = None
        self.origin_point = None      
        self.page_visual_rects = {} 
        self.current_pixmap_page_num = None
        self.selected_visual_info = None 

        self.is_moving_selection = False
        self.drag_start_mouse_pos = None     
        self.drag_start_rect_pos = None   

        self.is_resizing_selection = False
        self.active_resize_handle = None 
        self.resize_start_mouse_pos = None 
        self.resize_start_rect = None      

    def _get_handle_rects(self, base_rect):
        if not base_rect or base_rect.isNull():
            return {}
        hs = HANDLE_SIZE
        hs_half = hs // 2
        handles = {
            H_TOP_LEFT: QRect(base_rect.left() - hs_half, base_rect.top() - hs_half, hs, hs),
            H_TOP_MIDDLE: QRect(base_rect.center().x() - hs_half, base_rect.top() - hs_half, hs, hs),
            H_TOP_RIGHT: QRect(base_rect.right() - hs_half + 1, base_rect.top() - hs_half, hs, hs),
            H_MIDDLE_LEFT: QRect(base_rect.left() - hs_half, base_rect.center().y() - hs_half, hs, hs),
            H_MIDDLE_RIGHT: QRect(base_rect.right() - hs_half + 1, base_rect.center().y() - hs_half, hs, hs),
            H_BOTTOM_LEFT: QRect(base_rect.left() - hs_half, base_rect.bottom() - hs_half + 1, hs, hs),
            H_BOTTOM_MIDDLE: QRect(base_rect.center().x() - hs_half, base_rect.bottom() - hs_half + 1, hs, hs),
            H_BOTTOM_RIGHT: QRect(base_rect.right() - hs_half + 1, base_rect.bottom() - hs_half + 1, hs, hs),
        }
        return handles

    def _get_handle_at_pos(self, pos, base_rect):
        handle_rects = self._get_handle_rects(base_rect)
        for handle_id, handle_r in handle_rects.items():
            if handle_r.contains(pos):
                return handle_id
        return None

    def setCurrentPixmapPage(self, page_num):
        self.current_pixmap_page_num = page_num
        old_selected_id = None
        if self.selected_visual_info:
            old_selected_id = self.selected_visual_info['id']
            # Check if selected item is on the new page
            is_selected_on_new_page = any(
                info['id'] == old_selected_id 
                for info in self.page_visual_rects.get(self.current_pixmap_page_num, [])
            )
            if not is_selected_on_new_page:
                self.selected_visual_info = None
                self.areaSelectionChangedSignal.emit(None) # Emit only if selection actually changes to None
        self.update()

    def addVisualRect(self, page_num, view_qrect, instance_id, area_type, 
                      outline_color_rgba=None, fill_color_rgba=None, outline_width=None):
        if page_num not in self.page_visual_rects:
            self.page_visual_rects[page_num] = []
        item_info = {
            'rect': view_qrect, 'id': instance_id, 'type': area_type,
            'outline_color_rgba': outline_color_rgba if outline_color_rgba else (255,0,0,255),
            'fill_color_rgba': fill_color_rgba if fill_color_rgba else (0,0,0,0),
            'outline_width': outline_width if outline_width is not None else 1
        }
        self.page_visual_rects[page_num].append(item_info)
        if page_num == self.current_pixmap_page_num:
            self.update()

    def mousePressEvent(self, event):
        if not (self.parent_widget and hasattr(self.parent_widget, 'current_drawing_tool')):
            print("InteractivePdfLabel.mousePressEvent: Parent widget or current_drawing_tool not available.")
            return

        active_tool = self.parent_widget.current_drawing_tool
        print(f"InteractivePdfLabel.mousePressEvent: Active tool from parent: '{active_tool}'") # Debug

        if event.button() == Qt.MouseButton.LeftButton and self.pixmap():
            click_pos = event.pos()

            # Define which tools initiate a drawing drag (rubber band)
            area_definition_tools = ["text_area", "signature_area", "initials_area"]
            shape_drawing_tools = ["draw_rectangle", "draw_oval", "draw_line"]
            all_drawing_initiation_tools = area_definition_tools + shape_drawing_tools

            if active_tool in all_drawing_initiation_tools:
                self.origin_point = click_pos
                self.current_rubber_band_rect = QRect(self.origin_point, self.origin_point)
                if self.selected_visual_info is not None:
                    self.selected_visual_info = None
                    self.areaSelectionChangedSignal.emit(None)
                self.update()
            
            elif active_tool == "select_area":
                if self.selected_visual_info and self.selected_visual_info['rect']: # Check for handle grab first
                    clicked_handle = self._get_handle_at_pos(click_pos, self.selected_visual_info['rect'])
                    if clicked_handle is not None:
                        self.is_resizing_selection = True
                        self.active_resize_handle = clicked_handle
                        self.resize_start_mouse_pos = click_pos
                        self.resize_start_rect = QRect(self.selected_visual_info['rect'])
                        self.parent_widget.pdf_display_label.setCursor(Qt.CursorShape.PointingHandCursor)
                        print(f"Resize initiated from handle: {clicked_handle}")
                        self.update()
                        return 
                # Normal selection/deselection logic for "select_area" tool
                rect_infos_on_current_page = self.page_visual_rects.get(self.current_pixmap_page_num, [])
                hits_info_dicts = [info for info in reversed(rect_infos_on_current_page) if info['rect'].contains(click_pos)]
                newly_selected_info_dict = None
                previous_selection_id = self.selected_visual_info['id'] if self.selected_visual_info else None

                if event.modifiers() == Qt.KeyboardModifier.AltModifier and hits_info_dicts:
                    current_sel_index_in_hits = -1
                    if self.selected_visual_info and self.selected_visual_info in hits_info_dicts:
                        current_sel_index_in_hits = hits_info_dicts.index(self.selected_visual_info)
                    if current_sel_index_in_hits != -1:
                        next_index = (current_sel_index_in_hits + 1) % len(hits_info_dicts)
                        newly_selected_info_dict = hits_info_dicts[next_index]
                    elif hits_info_dicts:
                        newly_selected_info_dict = hits_info_dicts[0]
                elif not event.modifiers() and hits_info_dicts:
                    newly_selected_info_dict = hits_info_dicts[0]

                if previous_selection_id != (newly_selected_info_dict['id'] if newly_selected_info_dict else None):
                    self.selected_visual_info = newly_selected_info_dict
                    self.areaSelectionChangedSignal.emit(self.selected_visual_info['id'] if self.selected_visual_info else None)
                    self.update()
                # Debug print for select_area
                if self.selected_visual_info:
                    print(f"InteractivePdfLabel: Area selected by SelectTool - ID: {self.selected_visual_info['id']}")
                elif previous_selection_id is not None and newly_selected_info_dict is None:
                     print("InteractivePdfLabel: Selection cleared by SelectTool.")
            
            elif active_tool == "move_area":
                if self.selected_visual_info and self.selected_visual_info['rect']: # Check for handle grab first
                    clicked_handle = self._get_handle_at_pos(click_pos, self.selected_visual_info['rect'])
                    if clicked_handle is not None:
                        self.is_resizing_selection = True
                        self.active_resize_handle = clicked_handle
                        self.resize_start_mouse_pos = click_pos
                        self.resize_start_rect = QRect(self.selected_visual_info['rect'])
                        self.parent_widget.pdf_display_label.setCursor(Qt.CursorShape.PointingHandCursor)
                        print(f"Resize initiated (from MoveTool) from handle: {clicked_handle}")
                        self.update()
                        return
                # Normal move initiation logic
                target_to_move_info = None
                selection_changed_by_this_press = False
                rect_infos_on_current_page = self.page_visual_rects.get(self.current_pixmap_page_num, [])

                if event.modifiers() == Qt.KeyboardModifier.AltModifier:
                    hits_info_dicts = [info for info in reversed(rect_infos_on_current_page) if info['rect'].contains(click_pos)]
                    if hits_info_dicts:
                        current_sel_index_in_hits = -1
                        if self.selected_visual_info and self.selected_visual_info in hits_info_dicts:
                            current_sel_index_in_hits = hits_info_dicts.index(self.selected_visual_info)
                        if current_sel_index_in_hits != -1:
                            next_index = (current_sel_index_in_hits + 1) % len(hits_info_dicts)
                            target_to_move_info = hits_info_dicts[next_index]
                        else:
                            target_to_move_info = hits_info_dicts[0]
                        print(f"MoveTool+Alt: Cycled to ID: {target_to_move_info['id'] if target_to_move_info else 'None'}")
                else: # Normal Click with Move tool
                    if self.selected_visual_info and self.selected_visual_info['rect'].contains(click_pos):
                        target_to_move_info = self.selected_visual_info
                    else:
                        hits_info_dicts = [info for info in reversed(rect_infos_on_current_page) if info['rect'].contains(click_pos)]
                        if hits_info_dicts:
                            target_to_move_info = hits_info_dicts[0]
                
                if target_to_move_info:
                    if not self.selected_visual_info or self.selected_visual_info['id'] != target_to_move_info['id']:
                        self.selected_visual_info = target_to_move_info
                        self.areaSelectionChangedSignal.emit(self.selected_visual_info['id'])
                        selection_changed_by_this_press = True
                elif self.selected_visual_info: # Clicked empty space
                    self.selected_visual_info = None
                    self.areaSelectionChangedSignal.emit(None)
                    selection_changed_by_this_press = True

                if target_to_move_info:
                    self.is_moving_selection = True
                    self.drag_start_mouse_pos = click_pos
                    self.drag_start_rect_pos = self.selected_visual_info['rect'].topLeft()
                    self.parent_widget.pdf_display_label.setCursor(Qt.CursorShape.ClosedHandCursor)
                    print(f"Move initiated for ID: {self.selected_visual_info['id']}")
                    if not selection_changed_by_this_press: self.update()
                elif selection_changed_by_this_press: self.update()

    def mouseMoveEvent(self, event):
        current_pos = event.pos()
        active_tool = self.parent_widget.current_drawing_tool if self.parent_widget else None

        # Define all tools that use rubber-band for defining new shapes/areas
        area_definition_tools = ["text_area", "signature_area", "initials_area"]
        shape_drawing_tools = ["draw_rectangle", "draw_oval", "draw_line"]
        all_drawing_initiation_tools = area_definition_tools + shape_drawing_tools

        if self.is_resizing_selection and self.selected_visual_info and self.active_resize_handle is not None:
            new_rect = QRect(self.resize_start_rect)
            if self.active_resize_handle == H_TOP_LEFT: new_rect.setTopLeft(current_pos)
            elif self.active_resize_handle == H_TOP_MIDDLE: new_rect.setTop(current_pos.y())
            elif self.active_resize_handle == H_TOP_RIGHT: new_rect.setTopRight(current_pos)
            elif self.active_resize_handle == H_MIDDLE_LEFT: new_rect.setLeft(current_pos.x())
            elif self.active_resize_handle == H_MIDDLE_RIGHT: new_rect.setRight(current_pos.x())
            elif self.active_resize_handle == H_BOTTOM_LEFT: new_rect.setBottomLeft(current_pos)
            elif self.active_resize_handle == H_BOTTOM_MIDDLE: new_rect.setBottom(current_pos.y())
            elif self.active_resize_handle == H_BOTTOM_RIGHT: new_rect.setBottomRight(current_pos)
            self.selected_visual_info['rect'] = new_rect.normalized()
            self.update()
            return

        elif self.is_moving_selection and self.selected_visual_info:
            mouse_delta = current_pos - self.drag_start_mouse_pos
            new_top_left = self.drag_start_rect_pos + mouse_delta
            self.selected_visual_info['rect'].moveTo(new_top_left)
            self.update()
            return

        # **** CORRECTED: Use all_drawing_initiation_tools for rubber band ****
        elif self.origin_point is not None and self.current_rubber_band_rect is not None and \
             active_tool in all_drawing_initiation_tools:
            self.current_rubber_band_rect = QRect(self.origin_point, current_pos).normalized()
            self.update()
            return

        # Hover logic for cursors (no button pressed)
        if active_tool in ["select_area", "move_area"] and self.selected_visual_info and \
           self.selected_visual_info['rect'] and self.current_pixmap_page_num is not None and \
           any(info['id'] == self.selected_visual_info['id'] for info in self.page_visual_rects.get(self.current_pixmap_page_num, [])):
            hovered_handle = self._get_handle_at_pos(current_pos, self.selected_visual_info['rect'])
            if hovered_handle is not None:
                if hovered_handle in [H_TOP_LEFT, H_BOTTOM_RIGHT]: self.setCursor(Qt.CursorShape.SizeFDiagCursor)
                elif hovered_handle in [H_TOP_RIGHT, H_BOTTOM_LEFT]: self.setCursor(Qt.CursorShape.SizeBDiagCursor)
                elif hovered_handle in [H_TOP_MIDDLE, H_BOTTOM_MIDDLE]: self.setCursor(Qt.CursorShape.SizeVerCursor)
                elif hovered_handle in [H_MIDDLE_LEFT, H_MIDDLE_RIGHT]: self.setCursor(Qt.CursorShape.SizeHorCursor)
            else:
                if active_tool == "move_area":
                    if self.selected_visual_info['rect'].contains(current_pos):
                        self.setCursor(Qt.CursorShape.OpenHandCursor)
                    else: self.setCursor(Qt.CursorShape.ArrowCursor)
                else: self.setCursor(Qt.CursorShape.ArrowCursor) # Select tool, not on handle
        elif active_tool not in all_drawing_initiation_tools: # Not drawing, not select/move over item
            if active_tool == "select_area": self.setCursor(Qt.CursorShape.ArrowCursor)
            elif active_tool == "move_area": self.setCursor(Qt.CursorShape.OpenHandCursor)
            elif active_tool is None: self.setCursor(Qt.CursorShape.ArrowCursor)
            # Drawing tools set CrossCursor via DesignerApp.handleToolSelected

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            active_tool = self.parent_widget.current_drawing_tool if self.parent_widget else None
            
            area_definition_tools = ["text_area", "signature_area", "initials_area"]
            shape_drawing_tools = ["draw_rectangle", "draw_oval", "draw_line"]
            all_drawing_initiation_tools = area_definition_tools + shape_drawing_tools

            if self.is_resizing_selection and self.selected_visual_info:
                instance_id = self.selected_visual_info['id']
                final_resized_view_qrect = self.selected_visual_info['rect'].normalized()
                self.selected_visual_info['rect'] = final_resized_view_qrect
                self.areaResizedSignal.emit(instance_id, final_resized_view_qrect)
                self.is_resizing_selection = False
                self.active_resize_handle = None
                self.resize_start_mouse_pos = None
                self.resize_start_rect = None
                if active_tool == "move_area": self.parent_widget.pdf_display_label.setCursor(Qt.CursorShape.OpenHandCursor)
                elif active_tool == "select_area": self.parent_widget.pdf_display_label.setCursor(Qt.CursorShape.ArrowCursor)

            elif self.is_moving_selection and self.selected_visual_info:
                instance_id = self.selected_visual_info['id']
                new_view_qrect = self.selected_visual_info['rect']
                self.areaMovedSignal.emit(instance_id, new_view_qrect)
                self.is_moving_selection = False
                self.drag_start_mouse_pos = None
                self.drag_start_rect_pos = None
                if active_tool == "move_area": self.parent_widget.pdf_display_label.setCursor(Qt.CursorShape.OpenHandCursor)
            
            # **** CORRECTED: Use all_drawing_initiation_tools for finalizing rubber band ****
            elif self.origin_point is not None and self.current_rubber_band_rect is not None and \
                 self.current_pixmap_page_num is not None and \
                 active_tool in all_drawing_initiation_tools:
                final_rect_view = self.current_rubber_band_rect.normalized()
                if final_rect_view.width() > 0 and final_rect_view.height() > 0:
                    self.rectDefinedSignal.emit(final_rect_view)
                self.origin_point = None
                self.current_rubber_band_rect = None
                self.update()

    def paintEvent(self, event):
        super().paintEvent(event) 
        painter = QPainter(self)

        if self.current_pixmap_page_num is not None:
            rect_infos_for_current_page = self.page_visual_rects.get(self.current_pixmap_page_num, [])
            
            for info in rect_infos_for_current_page:
                rect_to_draw = info['rect'] 
                area_type = info.get('type', 'text_input')
                is_selected = (self.selected_visual_info is not None and 
                               self.selected_visual_info['id'] == info['id'])

                pen_color_obj = QColor(Qt.GlobalColor.black)
                pen_width = 1
                current_brush = QBrush(Qt.BrushStyle.NoBrush)

                if is_selected:
                    pen_color_obj = QColor(Qt.GlobalColor.green)
                    pen_width = 2
                    current_brush = QBrush(Qt.BrushStyle.NoBrush) 
                else: 
                    oc_rgba = info.get('outline_color_rgba', (255, 0, 0, 255)) 
                    fc_rgba = info.get('fill_color_rgba', (0, 0, 0, 0))       
                    ow = info.get('outline_width', 1)                         

                    pen_color_obj = QColor(oc_rgba[0], oc_rgba[1], oc_rgba[2], oc_rgba[3])
                    pen_width = ow
                    
                    if fc_rgba[3] > 0: 
                        current_brush = QBrush(QColor(fc_rgba[0], fc_rgba[1], fc_rgba[2], fc_rgba[3]), 
                                               Qt.BrushStyle.SolidPattern)
                    else:
                        current_brush = QBrush(Qt.BrushStyle.NoBrush)

                    if area_type == "signature_area":
                        pen_color_obj = QColor(Qt.GlobalColor.blue) 
                        pen_width = 1
                        current_brush = QBrush(QColor(Qt.GlobalColor.darkGray), Qt.BrushStyle.FDiagPattern)
                    elif area_type == "initials_area":
                        pen_color_obj = QColor(Qt.GlobalColor.blue)
                        pen_width = 1
                        current_brush = QBrush(QColor(Qt.GlobalColor.darkGray), Qt.BrushStyle.BDiagPattern)
                    elif area_type == "text_input":
                        pen_color_obj = QColor(Qt.GlobalColor.blue)
                        pen_width = 1
                        current_brush = QBrush(Qt.BrushStyle.NoBrush)
                
                pen = QPen(pen_color_obj, pen_width, Qt.PenStyle.SolidLine)
                painter.setPen(pen)
                painter.setBrush(current_brush)
                
                if area_type in ["text_input", "signature_area", "initials_area", "drawing_rectangle"]:
                    painter.drawRect(rect_to_draw)
                elif area_type == "drawing_oval":
                    painter.drawEllipse(rect_to_draw)
                elif area_type == "drawing_line":
                    painter.drawLine(rect_to_draw.topLeft(), rect_to_draw.bottomRight())
            
            if self.selected_visual_info and \
               self.current_pixmap_page_num is not None and \
               any(info['id'] == self.selected_visual_info['id'] for info in self.page_visual_rects.get(self.current_pixmap_page_num, [])):
                selected_rect_for_handles = self.selected_visual_info['rect']
                handle_rects = self._get_handle_rects(selected_rect_for_handles)
                painter.setPen(QPen(QColor(Qt.GlobalColor.black), 1))
                painter.setBrush(QBrush(QColor(Qt.GlobalColor.white)))
                for handle_r in handle_rects.values():
                    painter.drawRect(handle_r)
            
        if self.current_rubber_band_rect is not None and not self.current_rubber_band_rect.isNull():
            pen_rubber_band = QPen(QColor(Qt.GlobalColor.red), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen_rubber_band)
            painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            painter.drawRect(self.current_rubber_band_rect)

    def clearDefinedRects(self):
        self.page_visual_rects = {}
        old_selected_id = self.selected_visual_info['id'] if self.selected_visual_info else None
        self.selected_visual_info = None
        if old_selected_id:
            self.areaSelectionChangedSignal.emit(None)
        self.update()

    def removeVisualRectById(self, page_num, instance_id):
        removed = False
        if page_num in self.page_visual_rects:
            initial_len = len(self.page_visual_rects[page_num])
            self.page_visual_rects[page_num] = [info for info in self.page_visual_rects[page_num] if info['id'] != instance_id]
            if len(self.page_visual_rects[page_num]) < initial_len:
                removed = True
        if self.selected_visual_info and self.selected_visual_info['id'] == instance_id:
            self.selected_visual_info = None
        if removed:
            self.update()
        return removed
    
    def updateVisualRectPositionAndStyle(self, page_num, instance_id, new_rect=None, new_type=None):
        if page_num in self.page_visual_rects:
            for i, info in enumerate(self.page_visual_rects[page_num]):
                if info['id'] == instance_id:
                    changed = False
                    if new_rect is not None and info['rect'] != new_rect:
                        self.page_visual_rects[page_num][i]['rect'] = new_rect
                        changed = True
                    if new_type is not None and info.get('type') != new_type:
                         self.page_visual_rects[page_num][i]['type'] = new_type
                         changed = True
                    if changed and page_num == self.current_pixmap_page_num:
                        if self.selected_visual_info and self.selected_visual_info['id'] == instance_id:
                            if new_rect is not None: self.selected_visual_info['rect'] = new_rect
                            if new_type is not None: self.selected_visual_info['type'] = new_type
                        self.update()
                    return True
        return False
    
class DesignerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.pdf_document = None
        self.current_pdf_path = None # **** NEW: Path to the currently loaded PDF ****
        self.current_project_path = None # **** NEW: Path to the current project file ****
        self.current_page_num = 0
        self.zoom_levels = [0.25, 0.50, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0]
        # Find the index for our default zoom factor (e.g., 1.5)
        try:
            self.current_zoom_level_index = self.zoom_levels.index(1.5) 
        except ValueError:
            self.current_zoom_level_index = self.zoom_levels.index(1.0) # Fallback to 100%
            print("Warning: Default zoom 1.5 not in zoom_levels, defaulting to 1.0")
        self.current_zoom_factor = self.zoom_levels[self.current_zoom_level_index]
        self.defined_pdf_areas = []
        self.current_drawing_tool = None # Will be set in initUI or by tool selection
        self.currently_selected_area_instance_id = None
        self.project_is_dirty = False 
        self.undo_stack = []
        self.redo_stack = []
        self.initUI()
        #self.setSelectToolActive() #commented out to remove the activation

    def initUI(self):
        # ... (setWindowTitle, setGeometry, central_widget, main_layout, menubar, toolbar as before) ...
        self.setWindowTitle('SpeedyF Designer')
        self.setGeometry(100, 100, 900, 750)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Menu Bar ---
        menubar = self.menuBar()
        file_menu = menubar.addMenu('&File')
        # ... (New, Open, Separator, Save, Save As actions as before) ...
        new_project_action = QAction('&New Project', self)
        new_project_action.setStatusTip('Create a new project')
        new_project_action.setShortcut(QKeySequence.StandardKey.New)
        new_project_action.triggered.connect(self.newProject)
        file_menu.addAction(new_project_action)

        open_project_action = QAction('&Open Project...', self)
        open_project_action.setStatusTip('Open an existing project')
        open_project_action.setShortcut(QKeySequence.StandardKey.Open) 
        open_project_action.triggered.connect(self.openExistingProject)
        file_menu.addAction(open_project_action)

        file_menu.addSeparator()

        self.save_project_action = QAction('&Save Project', self)
        self.save_project_action.setStatusTip('Save the current project')
        self.save_project_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_project_action.triggered.connect(self.saveProject)
        self.save_project_action.setEnabled(False) 
        file_menu.addAction(self.save_project_action)

        self.save_project_as_action = QAction('&Save Project As...', self)
        self.save_project_as_action.setStatusTip('Save the current project to a new file')
        self.save_project_as_action.triggered.connect(self.saveProjectAs)
        self.save_project_as_action.setEnabled(False) 
        file_menu.addAction(self.save_project_as_action)

        edit_menu = menubar.addMenu('&Edit')

        self.undo_action = QAction('&Undo', self)
        self.undo_action.setStatusTip('Undo the last action')
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo) # Ctrl+Z
        self.undo_action.triggered.connect(self.undo)
        self.undo_action.setEnabled(False) # Initially disabled
        edit_menu.addAction(self.undo_action)

        self.redo_action = QAction('&Redo', self)
        self.redo_action.setStatusTip('Redo the last undone action')
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo) # Ctrl+Y or Ctrl+Shift+Z on some platforms
        self.redo_action.triggered.connect(self.redo)
        self.redo_action.setEnabled(False) # Initially disabled
        edit_menu.addAction(self.redo_action)        

        # --- Toolbar ---
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        self.tool_action_group = QActionGroup(self)
        self.tool_action_group.setExclusive(True) 
        self.tool_action_group.triggered.connect(self.handleToolSelected)

        # Select Area Action (as before)
        self.select_area_action = QAction("Select Area", self) 
        self.select_area_action.setStatusTip("Select, move, or edit defined areas")
        self.select_area_action.setCheckable(True)
        self.select_area_action.setData("select_area") 
        toolbar.addAction(self.select_area_action)
        self.tool_action_group.addAction(self.select_area_action)

        # Define Text Area Action (as before)
        self.define_text_area_action = QAction("Text Area", self)
        self.define_text_area_action.setStatusTip("Define a text input area")
        self.define_text_area_action.setCheckable(True)
        self.define_text_area_action.setData("text_area") 
        toolbar.addAction(self.define_text_area_action)
        self.tool_action_group.addAction(self.define_text_area_action)

        # **** NEW: Define Signature Area Action ****
        self.define_signature_area_action = QAction("Signature Area", self)
        # self.define_signature_area_action.setIcon(QIcon("path/to/signature_icon.png")) # Optional
        self.define_signature_area_action.setStatusTip("Define a signature area")
        self.define_signature_area_action.setCheckable(True)
        self.define_signature_area_action.setData("signature_area") # New tool identifier
        toolbar.addAction(self.define_signature_area_action)
        self.tool_action_group.addAction(self.define_signature_area_action)

        # **** NEW: Define Initials Area Action ****
        self.define_initials_area_action = QAction("Initials Area", self)
        # self.define_initials_area_action.setIcon(QIcon("path/to/initials_icon.png")) # Optional
        self.define_initials_area_action.setStatusTip("Define an initials area")
        self.define_initials_area_action.setCheckable(True)
        self.define_initials_area_action.setData("initials_area") # New tool identifier
        toolbar.addAction(self.define_initials_area_action)
        self.tool_action_group.addAction(self.define_initials_area_action)

        self.move_area_action = QAction("Move Area", self)
        # self.move_area_action.setIcon(QIcon("path/to/move_icon.png")) # Optional icon
        self.move_area_action.setStatusTip("Move an existing defined area")
        self.move_area_action.setCheckable(True)
        self.move_area_action.setData("move_area") # New tool identifier
        toolbar.addAction(self.move_area_action)
        self.tool_action_group.addAction(self.move_area_action)

        # **** NEW: Drawing Tools ****
        toolbar.addSeparator() # Separate drawing tools

        self.draw_rectangle_action = QAction("Draw Rectangle", self)
        # self.draw_rectangle_action.setIcon(QIcon("path/to/rect_icon.png")) # Optional
        self.draw_rectangle_action.setStatusTip("Draw a rectangle shape")
        self.draw_rectangle_action.setCheckable(True)
        self.draw_rectangle_action.setData("draw_rectangle")
        toolbar.addAction(self.draw_rectangle_action)
        self.tool_action_group.addAction(self.draw_rectangle_action)

        self.draw_oval_action = QAction("Draw Oval", self)
        # self.draw_oval_action.setIcon(QIcon("path/to/oval_icon.png")) # Optional
        self.draw_oval_action.setStatusTip("Draw an oval shape")
        self.draw_oval_action.setCheckable(True)
        self.draw_oval_action.setData("draw_oval")
        toolbar.addAction(self.draw_oval_action)
        self.tool_action_group.addAction(self.draw_oval_action)

        self.draw_line_action = QAction("Draw Line", self)
        # self.draw_line_action.setIcon(QIcon("path/to/line_icon.png")) # Optional
        self.draw_line_action.setStatusTip("Draw a line segment")
        self.draw_line_action.setCheckable(True)
        self.draw_line_action.setData("draw_line")
        toolbar.addAction(self.draw_line_action)
        self.tool_action_group.addAction(self.draw_line_action)

        toolbar.addSeparator() # Separator after drawing tools

        # **** NEW: Zoom Actions ****
        self.zoom_out_action = QAction("Zoom Out", self)
        # self.zoom_out_action.setIcon(QIcon("path/to/zoom_out_icon.png")) # Optional
        self.zoom_out_action.setStatusTip("Decrease zoom level")
        self.zoom_out_action.setShortcut(QKeySequence.StandardKey.ZoomOut) # Typically Ctrl+-
        self.zoom_out_action.triggered.connect(self.zoomOut)
        self.zoom_out_action.setEnabled(False) # Initially disabled
        toolbar.addAction(self.zoom_out_action)

        self.zoom_in_action = QAction("Zoom In", self)
        # self.zoom_in_action.setIcon(QIcon("path/to/zoom_in_icon.png")) # Optional
        self.zoom_in_action.setStatusTip("Increase zoom level")
        self.zoom_in_action.setShortcut(QKeySequence.StandardKey.ZoomIn) # Typically Ctrl++
        self.zoom_in_action.triggered.connect(self.zoomIn)
        self.zoom_in_action.setEnabled(False) # Initially disabled
        toolbar.addAction(self.zoom_in_action)
        
        # We could add a QLabel here to display current zoom % later
        # self.zoom_level_label = QLabel("100%")
        # toolbar.addWidget(self.zoom_level_label)

        toolbar.addSeparator()

        # Edit Area Properties Action (as before)
        self.edit_area_action = QAction("Edit Properties", self)
        # ... (rest of edit_area_action setup)
        self.edit_area_action.setStatusTip("Edit properties of the currently selected area")
        self.edit_area_action.triggered.connect(self.editSelectedAreaProperties)
        self.edit_area_action.setEnabled(False) 
        toolbar.addAction(self.edit_area_action)

        # Delete Area Action (as before)
        self.delete_area_action = QAction("Delete Area", self)
        # ... (rest of delete_area_action setup)
        self.delete_area_action.setStatusTip("Delete the currently selected area")
        self.delete_area_action.triggered.connect(self.deleteSelectedArea)
        self.delete_area_action.setEnabled(False) 
        toolbar.addAction(self.delete_area_action)

        # --- Controls Widget (as before) ---
        controls_widget = QWidget()
        # ... (rest of controls_widget and its layout as before) ...
        controls_layout = QVBoxLayout(controls_widget)
        self.info_label = QLabel('Select a tool, then load a PDF to begin.', self)
        controls_layout.addWidget(self.info_label)
        self.load_pdf_button = QPushButton('Load PDF', self)
        self.load_pdf_button.clicked.connect(self.openPdfFile)
        controls_layout.addWidget(self.load_pdf_button)
        nav_layout = QHBoxLayout()
        self.prev_page_button = QPushButton("<< Previous", self)
        self.prev_page_button.clicked.connect(self.goToPreviousPage)
        self.prev_page_button.setEnabled(False)
        nav_layout.addWidget(self.prev_page_button)
        self.page_info_label = QLabel("Page 0 of 0", self)
        nav_layout.addWidget(self.page_info_label)
        self.next_page_button = QPushButton("Next >>", self)
        self.next_page_button.clicked.connect(self.goToNextPage)
        self.next_page_button.setEnabled(False)
        nav_layout.addWidget(self.next_page_button)
        controls_layout.addLayout(nav_layout)
        main_layout.addWidget(controls_widget)

        # --- PDF Display Area ---
        self.pdf_display_label = InteractivePdfLabel(self) # self is DesignerApp
        self.default_min_display_width = 400
        self.default_min_display_height = 300
        self.pdf_display_label.setMinimumSize(self.default_min_display_width, self.default_min_display_height)
        self.pdf_display_label.setStyleSheet("QLabel { background-color : lightgray; border: 1px solid black; }")

        self.pdf_display_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
         
        self.pdf_display_label.rectDefinedSignal.connect(self.handleRectDefined)
        self.pdf_display_label.areaSelectionChangedSignal.connect(self.handleAreaSelectionChanged)
        self.pdf_display_label.areaMovedSignal.connect(self.handleAreaMoved)
        self.pdf_display_label.areaResizedSignal.connect(self.handleAreaResized)
        
        self.scroll_area = QScrollArea(self)
        # ... (scroll_area setup as before) ...
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.pdf_display_label)
        main_layout.addWidget(self.scroll_area)
        main_layout.setStretchFactor(self.scroll_area, 1)

        # Explicitly set initial UI state reflecting no tool is active
        self.info_label.setText("Select a tool from the toolbar or load a PDF.")
        self.pdf_display_label.setCursor(Qt.CursorShape.ArrowCursor)

        self._updateUndoRedoActionStates()
        # The status bar is already set to "Ready"
        # self.statusBar().showMessage("Ready")

    def setTextAreaTool(self, checked):
        if checked:
            self.current_drawing_tool = "text_area"
            self.info_label.setText("Mode: Define Text Area. Click and drag on the PDF.")
            self.pdf_display_label.setCursor(Qt.CursorShape.CrossCursor) # Ensure crosshair
            # If we had other tool actions, we'd uncheck them here or use QActionGroup
            print("Text Area tool selected")
        else:
            # This case handles when the action is unchecked (e.g., if part of an exclusive group
            # or if we implement clicking it again to deselect)
            if self.current_drawing_tool == "text_area": # Only deselect if it was the active one
                self.current_drawing_tool = None 
                self.info_label.setText("No tool selected. Load a PDF or select a tool.")
                self.pdf_display_label.setCursor(Qt.CursorShape.ArrowCursor) # Default cursor
                print("Text Area tool deselected")

    # We might want a general "select tool" or "pointer tool" later
    # def setSelectTool(self):
    #     self.current_drawing_tool = "select"
    #     self.info_label.setText("Mode: Select. (Functionality TBD)")
    #     self.pdf_display_label.setCursor(Qt.CursorShape.ArrowCursor)
    #     # Uncheck other tool actions
    #     self.define_text_area_action.setChecked(False)

    def handleAreaSelectionChanged(self, selected_instance_id):
        self.currently_selected_area_instance_id = selected_instance_id

        if selected_instance_id:
            selected_area_data = next((area for area in self.defined_pdf_areas if area['instance_id'] == selected_instance_id), None)
            
            print(f"DesignerApp: Area selected - Instance ID: {selected_instance_id}")
            if selected_area_data:
                 print(f"   Data Field ID: {selected_area_data['data_field_id']}")
            self.statusBar().showMessage(f"Area {selected_instance_id} selected.", 3000)
            
            # Enable Delete/Edit actions
            if hasattr(self, 'delete_area_action'): 
                self.delete_area_action.setEnabled(True)
            if hasattr(self, 'edit_area_action'): 
                self.edit_area_action.setEnabled(True)

        else: # None was passed (or empty string), meaning selection was cleared
            print("DesignerApp: Selection cleared.")
            self.statusBar().showMessage("Selection cleared.", 3000)

            # Disable Delete/Edit actions
            if hasattr(self, 'delete_area_action'): 
                self.delete_area_action.setEnabled(False)
            # **** ENSURE THIS LINE IS PRESENT AND CORRECT ****
            if hasattr(self, 'edit_area_action'): 
                self.edit_area_action.setEnabled(False) 

    def _reset_pdf_display_label(self, message="PDF page will appear here"):
        print("Attempting _reset_pdf_display_label...") # For debugging
        self.pdf_display_label.setPixmap(QPixmap()) 
        self.pdf_display_label.setText(message) 
        self.pdf_display_label.setMinimumSize(self.default_min_display_width, self.default_min_display_height)
        self.pdf_display_label.adjustSize()
        self.pdf_display_label.setCurrentPixmapPage(None)
        self.pdf_display_label.selected_view_rect = None # Ensure label's internal selection is reset
        self.pdf_display_label.selected_visual_info = None # label's internal selection
        # self.currently_selected_area_instance_id = None # Moved to handleAreaSelectionChanged
        self.handleAreaSelectionChanged(None) # Notify app that selection is cleared

        
        self.page_info_label.setText("Page 0 of 0")
        self.prev_page_button.setEnabled(False)
        self.next_page_button.setEnabled(False)

        if self.scroll_area and self.scroll_area.viewport():
            self.scroll_area.viewport().update()

        # **** NEW: Try hiding and showing the label ****
        self.pdf_display_label.hide()
        self.pdf_display_label.show()
        print("_reset_pdf_display_label finished.")

    def _updateNavigation(self):
        """Updates page info label and button states."""
        if self.pdf_document:
            total_pages = self.pdf_document.page_count
            current_display_page = self.current_page_num + 1
            self.page_info_label.setText(f"Page {current_display_page} of {total_pages}")

            self.prev_page_button.setEnabled(self.current_page_num > 0)
            self.next_page_button.setEnabled(self.current_page_num < total_pages - 1)
        else:
            self.page_info_label.setText("Page 0 of 0")
            self.prev_page_button.setEnabled(False)
            self.next_page_button.setEnabled(False)

    def _get_view_rects_for_page(self, page_num):
        view_rect_infos = [] 
        if not self.pdf_document:
            return view_rect_infos
        matrix = fitz.Matrix(self.current_zoom_factor, self.current_zoom_factor)
        for area_info in self.defined_pdf_areas: # area_info is a dict from our stored list
            if area_info['page_num'] == page_num:
                pdf_coords = area_info['rect_pdf']
                pdf_fitz_rect = fitz.Rect(pdf_coords[0], pdf_coords[1], pdf_coords[2], pdf_coords[3])
                view_fitz_rect = pdf_fitz_rect * matrix
                view_qrect = QRect(round(view_fitz_rect.x0), round(view_fitz_rect.y0),
                                round(view_fitz_rect.width), round(view_fitz_rect.height))
                # **** CHANGE: Include type ****
                view_rect_infos.append({
                    'rect': view_qrect, 
                    'id': area_info['instance_id'],
                    'type': area_info['type'],
                    'outline_color_rgba': area_info.get('outline_color_rgba'), # Pass along
                    'fill_color_rgba': area_info.get('fill_color_rgba'),       # Pass along
                    'outline_width': area_info.get('outline_width')            # Pass along
                })
        return view_rect_infos

    def displayPdfPage(self, page_num): # Revised structure for clarity
        if not self.pdf_document or page_num < 0 or page_num >= self.pdf_document.page_count:
            self._reset_pdf_display_label("Invalid page number or no PDF loaded.")
            self._updateNavigation()
            return

        # Clear DesignerApp's idea of selection if page changes
        if self.current_page_num != page_num and self.currently_selected_area_instance_id:
            self.handleAreaSelectionChanged(None)

        try:
            page = self.pdf_document.load_page(page_num)
            mat = fitz.Matrix(self.current_zoom_factor, self.current_zoom_factor)
            pix = page.get_pixmap(matrix=mat)
            img_format = QImage.Format.Format_RGB888 if pix.alpha == 0 else QImage.Format.Format_RGBA8888
            qimage = QImage(pix.samples, pix.width, pix.height, pix.stride, img_format)
            qpixmap = QPixmap.fromImage(qimage)

            self.pdf_display_label.setPixmap(qpixmap)
            self.pdf_display_label.setCurrentPixmapPage(page_num) # This tells label its page and calls update()
            
            # Clear old visual rects from label (for ALL pages) and then add for current page
            self.pdf_display_label.clearDefinedRects() 
            view_rect_infos_for_this_page = self._get_view_rects_for_page(page_num)
            for info in view_rect_infos_for_this_page:
                # **** CORRECTED LINE HERE ****
                self.pdf_display_label.addVisualRect( 
                    page_num, info['rect'], info['id'], info['type'],
                    outline_color_rgba=info.get('outline_color_rgba'),
                    fill_color_rgba=info.get('fill_color_rgba'),
                    outline_width=info.get('outline_width')
                )
            
            self.pdf_display_label.setMinimumSize(qpixmap.width(), qpixmap.height())
            self.pdf_display_label.adjustSize() 

            self.current_page_num = page_num
            self._updateNavigation() # Update page X of Y and nav buttons

            if self.scroll_area:
                self.scroll_area.verticalScrollBar().setValue(0)
                self.scroll_area.horizontalScrollBar().setValue(0)
        except Exception as e:
            QMessageBox.critical(self, "Error Displaying Page", f"Could not display page {page_num + 1}: {e}")
            self._reset_pdf_display_label(f"Error displaying page {page_num + 1}")
            self._updateNavigation()

    def handleRectDefined(self, view_qrect): # view_qrect is the QRect from the signal
        if not self.pdf_document or self.pdf_display_label.current_pixmap_page_num is None:
            return 
        
        current_tool_page = self.pdf_display_label.current_pixmap_page_num
        
        # --- Logic for tools that use the AreaPropertiesDialog ---
        if self.current_drawing_tool in ["text_area", "signature_area", "initials_area"]:
            tool_type_for_dialog = ""
            default_name_prefix = ""
            area_data_type_string = "" # This is the 'type' for storage

            if self.current_drawing_tool == "text_area":
                tool_type_for_dialog = "Text Input"
                default_name_prefix = "TextArea"
                area_data_type_string = "text_input"
            elif self.current_drawing_tool == "signature_area":
                tool_type_for_dialog = "Signature Area"
                default_name_prefix = "SignatureArea"
                area_data_type_string = "signature_area"
            elif self.current_drawing_tool == "initials_area":
                tool_type_for_dialog = "Initials Area"
                default_name_prefix = "InitialsArea"
                area_data_type_string = "initials_area"
            
            suggested_data_field_id = f"{default_name_prefix}_{len(self.defined_pdf_areas) + 1}"
            current_prompt_text = ""

            while True: 
                dialog = AreaPropertiesDialog(
                    area_type=tool_type_for_dialog, 
                    default_data_field_id=suggested_data_field_id,
                    default_prompt=current_prompt_text,          
                    parent=self
                )
                if dialog.exec() == QDialog.DialogCode.Accepted: # Correct for PyQt6
                    properties = dialog.getProperties()
                    suggested_data_field_id = properties["data_field_id"] 
                    current_prompt_text = properties["prompt"]

                    if properties and properties["data_field_id"]:
                        instance_id = f"inst_{uuid.uuid4().hex[:8]}"
                        inverse_matrix = ~fitz.Matrix(self.current_zoom_factor, self.current_zoom_factor)
                        view_fitz_rect = fitz.Rect(view_qrect.x(), view_qrect.y(), view_qrect.right(), view_qrect.bottom())
                        pdf_fitz_rect = view_fitz_rect * inverse_matrix
                        
                        area_info_to_add = {
                            'instance_id': instance_id, 'page_num': current_tool_page,
                            'rect_pdf': tuple(pdf_fitz_rect.irect), 
                            'data_field_id': properties["data_field_id"], 'type': area_data_type_string, 
                            'prompt': properties["prompt"],
                            'view_qrect_tuple': (view_qrect.x(), view_qrect.y(), view_qrect.width(), view_qrect.height())
                        }
                        command = AddAreaCommand(self, area_info_to_add)
                        self.executeCommand(command)
                        break 
                    else: 
                        QMessageBox.warning(self, "Missing Information", "Data Field Name / Link ID cannot be empty. Please try again.")
                else: 
                    print(f"Area definition ({area_data_type_string}) cancelled by user.")
                    break 
        
        # --- Logic for Drawing Tools (Rectangle, Oval, Line - bypass dialog for MVP) ---
        elif self.current_drawing_tool in ["draw_rectangle", "draw_oval", "draw_line"]:
            instance_id_prefix = ""
            area_data_type_string = "" # This is the 'type' for storage

            if self.current_drawing_tool == "draw_rectangle":
                instance_id_prefix = "draw_rect_"
                area_data_type_string = "drawing_rectangle"
            elif self.current_drawing_tool == "draw_oval":
                instance_id_prefix = "draw_oval_"
                area_data_type_string = "drawing_oval"
            elif self.current_drawing_tool == "draw_line":
                instance_id_prefix = "draw_line_"
                area_data_type_string = "drawing_line"

            instance_id = f"{instance_id_prefix}{uuid.uuid4().hex[:8]}"
            inverse_matrix = ~fitz.Matrix(self.current_zoom_factor, self.current_zoom_factor)
            
            # For lines, the view_qrect defines the start and end points.
            # For PDF storage, we can still store this bounding box, or start/end points.
            # Let's store the bounding box for consistency in rect_pdf for now.
            # The paintEvent will interpret it as start/end for lines.
            view_fitz_rect = fitz.Rect(view_qrect.x(), view_qrect.y(),
                                       view_qrect.right(), view_qrect.bottom())
            pdf_fitz_rect = view_fitz_rect * inverse_matrix

            area_info_to_add = {
                'instance_id': instance_id,
                'page_num': current_tool_page,
                'rect_pdf': tuple(pdf_fitz_rect.irect), 
                'type': area_data_type_string,
                'data_field_id': instance_id, # Drawings use their instance_id as data_field_id
                'prompt': "", # Drawings don't have prompts
                'view_qrect_tuple': (view_qrect.x(), view_qrect.y(), 
                                     view_qrect.width(), view_qrect.height()),
                # Default visual properties for MVP drawings
                'outline_color_rgba': (255, 0, 0, 255), # Red, fully opaque (R,G,B,A)
                'fill_color_rgba': (0, 0, 0, 0),       # Transparent fill (especially for lines/rects)
                'outline_width': 1
            }
            command = AddAreaCommand(self, area_info_to_add)
            self.executeCommand(command)
            print(f"Drawing {area_data_type_string.replace('_', ' ').title()} Added (Instance ID: {instance_id})")

        else:
            # This case should ideally not be reached if mousePressEvent in InteractivePdfLabel
            # only initiates drawing for known tools.
            print(f"Rectangle defined with unhandled or no active drawing tool: {self.current_drawing_tool}")
            return
        
    def openPdfFile(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open PDF File", "", 
                                                   "PDF Files (*.pdf);;All Files (*)")
        if file_name:
            # Close previous document if one is open
            if self.pdf_document:
                self.pdf_document.close()
                self.pdf_document = None
            
            # Reset state for the new file context
            self._reset_pdf_display_label() 
            self.defined_pdf_areas = [] 
            self.pdf_display_label.clearDefinedRects()
            self._updateNavigation()
            
            self.current_pdf_path = None # Reset current PDF path
            self.current_project_path = None # **** NEW: Reset project path for new PDF context ****
            
            # Initially disable save actions; they'll be enabled if PDF loads successfully
            if hasattr(self, 'save_project_as_action'):
                self.save_project_as_action.setEnabled(False)
            if hasattr(self, 'save_project_action'):
                self.save_project_action.setEnabled(False)

            try:
                doc = fitz.open(file_name)
                if not doc.is_pdf:
                    doc.close()
                    QMessageBox.critical(self, "Error", 
                                         f"The selected file '{file_name.split('/')[-1]}' is not a PDF document.")
                    self._reset_pdf_display_label("File is not a PDF. Please select a PDF file.")
                    self._updateNavigation()
                    self._markProjectAsDirty(False)
                    # Ensure save actions remain disabled
                    if hasattr(self, 'save_project_as_action'): self.save_project_as_action.setEnabled(False)
                    if hasattr(self, 'save_project_action'): self.save_project_action.setEnabled(False)
                    return

                self.pdf_document = doc
                self.current_pdf_path = file_name # Store new PDF path
                self.current_page_num = 0 
                try:
                    self.current_zoom_level_index = self.zoom_levels.index(1.5) # Default to 150%
                except ValueError:
                    self.current_zoom_level_index = self.zoom_levels.index(1.0) # Fallback to 100%
                self.current_zoom_factor = self.zoom_levels[self.current_zoom_level_index]

                self.info_label.setText(f"Loaded: {file_name.split('/')[-1]} ({self.pdf_document.page_count} pages)")
                self.displayPdfPage(self.current_page_num) # This will use the new zoom factor

                self.save_project_as_action.setEnabled(True)
                if hasattr(self, 'save_project_action'): self.save_project_action.setEnabled(False)
                self._updateZoomActionStates()
                self._markProjectAsDirty(False)

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open or process file: {e}")
                self.pdf_document = None 
                self.current_pdf_path = None # Clear path on error
                self.current_project_path = None # Also clear project path on error
                self._reset_pdf_display_label("Failed to load. Please try another file.")
                self._updateNavigation()
                if hasattr(self, 'save_project_as_action'):
                    self.save_project_as_action.setEnabled(False)
                if hasattr(self, 'save_project_action'):
                     self.save_project_action.setEnabled(False)
                self._updateZoomActionStates()
                self._markProjectAsDirty(False)
        else:
            # User cancelled the file dialog. Current state remains unchanged.
            pass

    def goToPreviousPage(self):
        if self.pdf_document and self.current_page_num > 0:
            self.current_page_num -= 1
            self.displayPdfPage(self.current_page_num)

    def goToNextPage(self):
        if self.pdf_document and self.current_page_num < self.pdf_document.page_count - 1:
            self.current_page_num += 1
            self.displayPdfPage(self.current_page_num)

    def saveProject(self):
        if not self.current_pdf_path:
            QMessageBox.warning(self, "Cannot Save", "Please load a PDF document first.")
            return

        if self.current_project_path:
            # Project has been saved before, save to the same path
            project_data = {
                'version': '1.0',
                'pdf_path': self.current_pdf_path,
                'defined_areas': self.defined_pdf_areas,
                'zoom_factor': self.current_zoom_factor
            }
            try:
                with open(self.current_project_path, 'w') as f:
                    json.dump(project_data, f, indent=4)
                self.statusBar().showMessage(f"Project saved to {self.current_project_path}", 5000)
                self._markProjectAsDirty(False)
                self.undo_stack.clear() # Clear history after save
                self.redo_stack.clear()
                self._updateUndoRedoActionStates()
                # TODO (Advanced): Implement a "dirty" flag to track unsaved changes.
                # For now, "Save" is always available if a project path exists.
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Could not save project: {e}")
                self.statusBar().showMessage(f"Error saving project: {e}")
        else:
            # Project has not been saved before, so call "Save As..."
            self.saveProjectAs()

    # Modify saveProjectAs to enable the "Save" action after a successful save
    def saveProjectAs(self):
        if not self.current_pdf_path:
            QMessageBox.warning(self, "Cannot Save", "Please load a PDF document first.")
            return

        suggested_filename = "untitled.speedyf_proj"
        if self.current_pdf_path:
            pdf_basename = self.current_pdf_path.split('/')[-1].split('\\')[-1]
            pdf_name_part = pdf_basename.rsplit('.', 1)[0] if '.' in pdf_basename else pdf_basename
            suggested_filename = f"{pdf_name_part}.speedyf_proj"

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Project As...", suggested_filename,
                                                   "SpeedyF Project Files (*.speedyf_proj);;All Files (*)")

        if file_path:
            project_data = {
                'version': '1.0',
                'pdf_path': self.current_pdf_path,
                'defined_areas': self.defined_pdf_areas
            }
            try:
                with open(file_path, 'w') as f:
                    json.dump(project_data, f, indent=4)
                
                self.current_project_path = file_path
                self.statusBar().showMessage(f"Project saved to {file_path}", 5000)
                if hasattr(self, 'save_project_action'): self.save_project_action.setEnabled(True)
                self._markProjectAsDirty(False)
                self.undo_stack.clear() # Clear history after save as
                self.redo_stack.clear()
                self._updateUndoRedoActionStates()
                # Update window title to include project name? (more advanced)
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Could not save project: {e}")
                self.statusBar().showMessage(f"Error saving project: {e}")
        else:
            self.statusBar().showMessage("Save operation cancelled.", 2000)

    def _reset_pdf_display_label(self, message="PDF page will appear here"):
        # ... (existing code) ...
        self.pdf_display_label.setCurrentPixmapPage(None) 
        self.page_info_label.setText("Page 0 of 0")
        self.prev_page_button.setEnabled(False)
        self.next_page_button.setEnabled(False)
        # When resetting (e.g. no PDF loaded), disable save.
        # If you add a "New Project" action, it should also call this or similar logic.
        # For now, openPdfFile handles enabling/disabling save_project_as_action.
        # self.current_project_path = None # If a "New Project" action resets everything
        # if hasattr(self, 'save_project_as_action'): self.save_project_as_action.setEnabled(False)
        # if hasattr(self, 'save_project_action'): self.save_project_action.setEnabled(False)


    # In openPdfFile, when a new PDF is loaded, you might want to reset self.current_project_path
    # to None to signify that this new PDF + its areas (if any are defined yet)
    # hasn't been saved as a project yet.
    # At the point a new PDF is successfully loaded in openPdfFile:
    # self.current_project_path = None
    # self.save_project_action.setEnabled(False) # If you had a "Save" action
    # This encourages "Save As" for a newly opened/modified PDF configuration.

    def newProject(self):
        # First, check for unsaved changes and prompt the user if necessary.
        if not self._promptToSaveUnsavedChanges():
            self.statusBar().showMessage("New project creation cancelled.", 2000)
            return # User cancelled the "New Project" operation or a preceding save failed.

        # Proceed with resetting for a new project if changes were saved, discarded, or there were none.
        if self.pdf_document:
            self.pdf_document.close()
            self.pdf_document = None

        self.current_pdf_path = None
        self.current_project_path = None # Ensure this is cleared for a new, unsaved project
        self.defined_pdf_areas = []
        self.current_page_num = 0
        
        # Reset zoom to default
        try:
            self.current_zoom_level_index = self.zoom_levels.index(1.5) 
        except ValueError:
            self.current_zoom_level_index = self.zoom_levels.index(1.0) # Fallback
        self.current_zoom_factor = self.zoom_levels[self.current_zoom_level_index]

        # Clear visual elements from the PDF display label
        self.pdf_display_label.clearDefinedRects() 
        self._reset_pdf_display_label("Load a PDF to begin a new project.") # Resets display and selection state
        
        # Update UI states
        self._updateNavigation() 
        self._updateZoomActionStates()

        self.info_label.setText("New project started. Load a PDF.")
        self.statusBar().showMessage("New project created. Ready.", 5000)

        # Disable save actions as it's a new, unsaved project context
        if hasattr(self, 'save_project_as_action'): 
            self.save_project_as_action.setEnabled(False) # Becomes enabled when a PDF is loaded
        if hasattr(self, 'save_project_action'): 
            self.save_project_action.setEnabled(False)
        
        # Mark the new project as not dirty
        self._markProjectAsDirty(False) 
        # _updateWindowTitle is called by _markProjectAsDirty to reflect "Untitled"

        # Clear undo/redo history for the new project
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._updateUndoRedoActionStates() # Disable Undo/Redo menu items
        
        print("New project started.")

    def openExistingProject(self):
        # **** NEW: Prompt to save if current project is dirty ****
        if not self._promptToSaveUnsavedChanges():
            self.statusBar().showMessage("Open project cancelled.", 2000)
            return # User cancelled or save failed/was cancelled

        # Proceed with opening a project file
        file_path, _ = QFileDialog.getOpenFileName(self, "Open SpeedyF Project", "",
                                                   "SpeedyF Project Files (*.speedyf_proj);;All Files (*)")

        if not file_path:
            self.statusBar().showMessage("Open project cancelled by user from file dialog.", 2000)
            return

        try:
            with open(file_path, 'r') as f:
                project_data = json.load(f)

            if 'pdf_path' not in project_data or 'defined_areas' not in project_data:
                QMessageBox.critical(self, "Error", "Invalid project file format.")
                # Reset to a clean state if opening an invalid project file
                self.newProject() # Call newProject to ensure a clean state, it handles its own dirty check (which will be false now)
                return

            # --- Successfully read project data, now apply it ---
            # 1. Reset current state (newProject() already called if there were unsaved changes,
            #    but we need to ensure a clean slate before loading new data regardless)
            #    Calling newProject() here again is a bit heavy if _promptToSaveUnsavedChanges
            #    already resulted in a save or discard.
            #    Let's refine this: newProject() should be the one to clear state *after* successful save/discard.
            #    Here, we need to ensure the *current* state is cleared if it wasn't already by the prompt.
            
            # If _promptToSaveUnsavedChanges returned True, it means either:
            #   a) project wasn't dirty
            #   b) project was dirty, user saved successfully (project_is_dirty is now False)
            #   c) project was dirty, user discarded (project_is_dirty should be considered False for the new load)
            # So, we can now safely clear the current state variables before loading.

            # Clear current state *before* loading new project data
            if self.pdf_document:
                self.pdf_document.close()
            self.pdf_document = None
            self.current_pdf_path = None
            # self.current_project_path will be set by the loaded project
            self.defined_pdf_areas = []
            self.pdf_display_label.clearDefinedRects()
            self._reset_pdf_display_label("Loading project...") # Resets display label and nav
            # self.current_page_num and zoom will be set from project data or defaults

            # 2. Attempt to load the PDF specified in the project file
            loaded_pdf_path = project_data['pdf_path']
            project_defined_areas = project_data.get('defined_areas', [])
            
            try: 
                doc = fitz.open(loaded_pdf_path)
                if not doc.is_pdf:
                    doc.close()
                    QMessageBox.critical(self, "Project Error", f"The linked file '{loaded_pdf_path}' is not a valid PDF.")
                    self._markProjectAsDirty(False) # Reset to clean, empty state
                    self._updateWindowTitle()
                    self._updateNavigation()
                    self._updateZoomActionStates()
                    return
                
                self.pdf_document = doc
                self.current_pdf_path = loaded_pdf_path
                self.current_project_path = file_path # This is the opened project's path
                self.current_page_num = project_data.get('start_page_num', 0) # Optional: save/load start page
                
                loaded_zoom = project_data.get('zoom_factor', 1.5)
                closest_level_index = min(range(len(self.zoom_levels)), 
                                          key=lambda i: abs(self.zoom_levels[i] - loaded_zoom))
                self.current_zoom_level_index = closest_level_index
                self.current_zoom_factor = self.zoom_levels[self.current_zoom_level_index]

                self.info_label.setText(f"Project: {file_path.split('/')[-1].split('\\')[-1]}")
                
                self.defined_pdf_areas = project_defined_areas
                
                self.displayPdfPage(self.current_page_num) # Displays page and its defined areas

                self.save_project_as_action.setEnabled(True)
                self.save_project_action.setEnabled(True) 
                self.statusBar().showMessage(f"Project '{file_path.split('/')[-1]}' opened.", 5000)
                self._updateZoomActionStates()
                self._markProjectAsDirty(False) # Freshly opened project is considered clean
                # _updateWindowTitle is called by _markProjectAsDirty
                self.undo_stack.clear()
                self.redo_stack.clear()
                self._updateUndoRedoActionStates()
                print(f"Project opened. Defined areas: {len(self.defined_pdf_areas)}")

            except Exception as e_pdf:
                QMessageBox.critical(self, "Error Loading PDF from Project", 
                                     f"Could not load PDF '{loaded_pdf_path}': {e_pdf}")
                self._markProjectAsDirty(False) # Reset to clean, empty state
                self._updateWindowTitle()
                self._updateNavigation()
                self._updateZoomActionStates()
                return

        except FileNotFoundError:
            QMessageBox.critical(self, "Error", f"Project file not found: {file_path}")
        except json.JSONDecodeError:
            QMessageBox.critical(self, "Error", f"Could not parse project file. Invalid JSON: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error Opening Project", f"An unexpected error occurred: {e}")
            # Reset to a clean state on generic error by effectively calling newProject's core logic
            self._reset_to_new_project_state() # You might need a dedicated method for this internal reset

# ... (Inside DesignerApp class)

    def handleToolSelected(self, action):
        new_tool_id = action.data()
        old_tool_id = self.current_drawing_tool

        # Clear selection if switching tools and something was selected
        if self.currently_selected_area_instance_id is not None:
            if new_tool_id != "select_area" or (old_tool_id == "select_area" and old_tool_id != new_tool_id) :
                self.clearCurrentSelection() 

        self.current_drawing_tool = new_tool_id # Set the new tool
        
        if new_tool_id == "select_area":
            self.info_label.setText("Mode: Select Area. Click on an existing area to select.")
            self.pdf_display_label.setCursor(Qt.CursorShape.ArrowCursor)
            print("Select Area tool active")
        elif new_tool_id == "text_area":
            self.info_label.setText("Mode: Define Text Area. Click and drag on the PDF.")
            self.pdf_display_label.setCursor(Qt.CursorShape.CrossCursor)
            print("Text Area tool active")
        elif new_tool_id == "signature_area":
            self.info_label.setText("Mode: Define Signature Area. Click and drag on the PDF.")
            self.pdf_display_label.setCursor(Qt.CursorShape.CrossCursor)
            print("Signature Area tool active")
        elif new_tool_id == "initials_area":
            self.info_label.setText("Mode: Define Initials Area. Click and drag on the PDF.")
            self.pdf_display_label.setCursor(Qt.CursorShape.CrossCursor)
            print("Initials Area tool active")
        elif new_tool_id == "move_area":
            self.info_label.setText("Mode: Move Area. Click and drag an existing area to move it.")
            self.pdf_display_label.setCursor(Qt.CursorShape.OpenHandCursor) # Or SizeAllCursor
            print("Move Area tool active")
        elif new_tool_id == "draw_rectangle":
            self.info_label.setText("Mode: Draw Rectangle. Click and drag to define.")
            self.pdf_display_label.setCursor(Qt.CursorShape.CrossCursor)
            print("Draw Rectangle tool active")
        elif new_tool_id == "draw_oval":
            self.info_label.setText("Mode: Draw Oval. Click and drag to define bounding box.")
            self.pdf_display_label.setCursor(Qt.CursorShape.CrossCursor)
            print("Draw Oval tool active")
        elif new_tool_id == "draw_line":
            self.info_label.setText("Mode: Draw Line. Click and drag from start to end point.")
            self.pdf_display_label.setCursor(Qt.CursorShape.CrossCursor)
            print("Draw Line tool active")
        else: 
            # This case should ideally not be reached if all toolbar actions have valid setData
            self.current_drawing_tool = None 
            self.info_label.setText("No specific tool selected. Load PDF or select a tool.")
            self.pdf_display_label.setCursor(Qt.CursorShape.ArrowCursor)
            if self.currently_selected_area_instance_id: # Clear selection if falling back
                self.clearCurrentSelection()
            print("No tool or unknown tool active (tool_id: '{new_tool_id}')") # Added tool_id to print for debugging

    def clearCurrentSelection(self):
        """Helper to clear the current selection state."""
        if self.currently_selected_area_instance_id is not None:
            self.pdf_display_label.selected_visual_info = None
            self.pdf_display_label.update()
            self.handleAreaSelectionChanged(None) # Notifies app, updates self.currently_selected_area_instance_id

    def setSelectToolActive(self): # Helper to activate select tool programmatically (e.g., on startup)
        self.select_area_action.setChecked(True)
        # handleToolSelected will be called automatically by QActionGroup's triggered signal

    def deleteSelectedArea(self):
        if not self.currently_selected_area_instance_id:
            print("No area selected to delete.")
            # self.statusBar().showMessage("No area selected to delete.", 2000) # Optional: Status bar msg is now in command
            return

        # Create the command object
        command = DeleteAreaCommand(self, self.currently_selected_area_instance_id)
        
        # Execute the command via the command manager
        # executeCommand will call command.execute(), handle undo/redo stacks, 
        # mark project dirty, and the command itself handles UI updates like
        # clearing selection and status bar messages.
        self.executeCommand(command)

    def keyPressEvent(self, event):
        """Handle key presses for the main window."""
        if self.currently_selected_area_instance_id: # Check if an area is selected
            if event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
                print("Delete/Backspace key pressed with selection.")
                self.deleteSelectedArea()
                event.accept() # Indicate we've handled the event
                return

        # Call the base class implementation for any other key events
        super().keyPressEvent(event)

    def editSelectedAreaProperties(self):
        if not self.currently_selected_area_instance_id:
            QMessageBox.information(self, "Edit Properties", "No area selected to edit.")
            return

        selected_id = self.currently_selected_area_instance_id
        area_data_to_edit = None
        
        # Find the current data for the selected area
        for area_info in self.defined_pdf_areas:
            if area_info['instance_id'] == selected_id:
                area_data_to_edit = area_info
                break
        
        if not area_data_to_edit:
            QMessageBox.warning(self, "Error", f"Could not find data for selected area ID {selected_id} to edit.")
            self.handleAreaSelectionChanged(None) # Clear potentially inconsistent selection
            return

        # Store old properties for the command
        old_properties = {
            'data_field_id': area_data_to_edit.get('data_field_id', ''),
            'prompt': area_data_to_edit.get('prompt', '')
        }

        # Open the dialog, pre-filled with existing properties
        dialog = AreaPropertiesDialog(
            area_type=area_data_to_edit.get('type', 'Unknown Type'), 
            default_data_field_id=old_properties['data_field_id'],
            default_prompt=old_properties['prompt'],
            parent=self
        )
        dialog.setWindowTitle(f"Edit Area Properties (ID: {selected_id})")

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_properties_from_dialog = dialog.getProperties()
            
            if new_properties_from_dialog and new_properties_from_dialog["data_field_id"]:
                # Check if anything actually changed
                if old_properties['data_field_id'] == new_properties_from_dialog['data_field_id'] and \
                   old_properties['prompt'] == new_properties_from_dialog['prompt']:
                    self.statusBar().showMessage("No changes made to properties.", 2000)
                    return # No actual change, so no command needed

                # Properties changed, create and execute the command
                command = EditAreaPropertiesCommand(self, selected_id, old_properties, new_properties_from_dialog)
                self.executeCommand(command)
                # The command's execute method handles updating self.defined_pdf_areas and status bar.
                # self._markProjectAsDirty() is handled by executeCommand.
            
            else: # Dialog accepted, but data_field_id was empty
                QMessageBox.warning(self, "Missing Information", 
                                    "Data Field Name / Link ID cannot be empty. Properties not updated.")
        else:
            print(f"Editing properties for area {selected_id} cancelled.")

    def handleAreaMoved(self, instance_id, new_view_qrect): # new_view_qrect is from the signal
        """Handles the signal after a visual area has been moved in InteractivePdfLabel."""
        if not self.pdf_document:
            return

        old_area_info = None
        for area_info in self.defined_pdf_areas:
            if area_info['instance_id'] == instance_id:
                old_area_info = area_info.copy() # Get a copy of the current state
                break
        
        if not old_area_info:
            print(f"Error: Data for moved area {instance_id} not found in DesignerApp.")
            return

        # Old state (already stored in PDF and view tuple formats)
        old_pdf_rect_tuple = old_area_info['rect_pdf']
        old_view_qrect_tuple = old_area_info['view_qrect_tuple']
        page_num = old_area_info['page_num'] # Page number doesn't change on move

        # New state from the signal (new_view_qrect)
        # Transform this new_view_qrect to new PDF coordinates
        inverse_matrix = ~fitz.Matrix(self.current_zoom_factor, self.current_zoom_factor)
        new_view_fitz_rect = fitz.Rect(new_view_qrect.x(), new_view_qrect.y(),
                                       new_view_qrect.right(), new_view_qrect.bottom())
        new_pdf_fitz_rect = new_view_fitz_rect * inverse_matrix
        new_pdf_rect_tuple = tuple(new_pdf_fitz_rect.irect)
        new_view_qrect_tuple = (new_view_qrect.x(), new_view_qrect.y(),
                                new_view_qrect.width(), new_view_qrect.height())

        # Create and execute the command
        # Ensure the arguments here match the variables defined above
        command = MoveAreaCommand(self, instance_id, page_num,
                                  old_view_qrect_tuple,  
                                  new_view_qrect_tuple,  
                                  old_pdf_rect_tuple,
                                  new_pdf_rect_tuple)
        self.executeCommand(command)
        
        print(f"MoveAreaCommand created for Instance ID: {instance_id}")

    def handleAreaResized(self, instance_id, new_view_qrect): # new_view_qrect from signal
        """Handles the signal after a visual area has been resized in InteractivePdfLabel."""
        if not self.pdf_document:
            return

        old_area_info = None
        for area_info in self.defined_pdf_areas:
            if area_info['instance_id'] == instance_id:
                old_area_info = area_info.copy() # Get a copy of the current state (before visual resize)
                break
        
        if not old_area_info:
            print(f"Error: Data for resized area {instance_id} not found in DesignerApp.")
            return

        # Old state from the data model
        old_pdf_rect_tuple = old_area_info['rect_pdf']
        old_view_qrect_tuple = old_area_info['view_qrect_tuple']
        page_num = old_area_info['page_num'] # Page number doesn't change on resize

        # New state from the signal (new_view_qrect from the visual resize)
        # Transform this new_view_qrect to new PDF coordinates
        inverse_matrix = ~fitz.Matrix(self.current_zoom_factor, self.current_zoom_factor)
        
        # Ensure QRect has positive width/height before converting (already normalized by InteractivePdfLabel)
        normalized_new_view_qrect = new_view_qrect.normalized()
        new_view_fitz_rect = fitz.Rect(normalized_new_view_qrect.x(), normalized_new_view_qrect.y(),
                                       normalized_new_view_qrect.right(), normalized_new_view_qrect.bottom())
        new_pdf_fitz_rect = new_view_fitz_rect * inverse_matrix
        new_pdf_rect_tuple = tuple(new_pdf_fitz_rect.irect)
        new_view_qrect_tuple_for_storage = (normalized_new_view_qrect.x(), normalized_new_view_qrect.y(),
                                            normalized_new_view_qrect.width(), normalized_new_view_qrect.height())

        # Create and execute the command
        command = ResizeAreaCommand(self, instance_id, page_num,
                                    old_view_qrect_tuple, new_view_qrect_tuple_for_storage,
                                    old_pdf_rect_tuple, new_pdf_rect_tuple)
        self.executeCommand(command)
        
        # The command's execute method now handles updating self.defined_pdf_areas,
        # calling InteractivePdfLabel.updateVisualRectPositionAndStyle, and status bar.
        # self._markProjectAsDirty() is handled by executeCommand.
        print(f"ResizeAreaCommand created for Instance ID: {instance_id}")

    def _updateZoomActionStates(self):
        """Enables/disables zoom actions based on current zoom level and PDF loaded state."""
        pdf_loaded = self.pdf_document is not None
        
        can_zoom_in = pdf_loaded and self.current_zoom_level_index < len(self.zoom_levels) - 1
        can_zoom_out = pdf_loaded and self.current_zoom_level_index > 0
        
        if hasattr(self, 'zoom_in_action'):
            self.zoom_in_action.setEnabled(can_zoom_in)
        if hasattr(self, 'zoom_out_action'):
            self.zoom_out_action.setEnabled(can_zoom_out)
        
        # Later, update a zoom level display label if we add one
        # if pdf_loaded and hasattr(self, 'zoom_level_label'):
        #     self.zoom_level_label.setText(f"{int(self.current_zoom_factor * 100)}%")
        # elif hasattr(self, 'zoom_level_label'):
        #     self.zoom_level_label.setText("---%")


    def zoomIn(self):
        if self.pdf_document and self.current_zoom_level_index < len(self.zoom_levels) - 1:
            self.current_zoom_level_index += 1
            self.current_zoom_factor = self.zoom_levels[self.current_zoom_level_index]
            print(f"Zoom In. New factor: {self.current_zoom_factor} (Level: {self.current_zoom_level_index})")
            self.displayPdfPage(self.current_page_num) # Re-render the current page
            self._updateZoomActionStates()

    def zoomOut(self):
        if self.pdf_document and self.current_zoom_level_index > 0:
            self.current_zoom_level_index -= 1
            self.current_zoom_factor = self.zoom_levels[self.current_zoom_level_index]
            print(f"Zoom Out. New factor: {self.current_zoom_factor} (Level: {self.current_zoom_level_index})")
            self.displayPdfPage(self.current_page_num) # Re-render the current page
            self._updateZoomActionStates()

    def _updateWindowTitle(self):
        """Updates the main window title to include project name and dirty status."""
        title = "SpeedyF Designer"
        project_name = ""
        if self.current_project_path:
            project_name = self.current_project_path.split('/')[-1].split('\\')[-1]
        elif self.current_pdf_path: # If no project path, but PDF is loaded
            project_name = self.current_pdf_path.split('/')[-1].split('\\')[-1] + " (untitled project)"
        else:
            project_name = "Untitled"

        if project_name:
            title += f" - {project_name}"

        if self.project_is_dirty:
            title += "*"

        self.setWindowTitle(title)

    def _markProjectAsDirty(self, dirty=True):
        """Marks the project as dirty (or clean) and updates the window title."""
        if self.project_is_dirty != dirty: # Only update if state changes
            self.project_is_dirty = dirty
            self._updateWindowTitle()
            print(f"Project dirty state: {self.project_is_dirty}")
            # TODO: Later, we might enable/disable the "Save" action based on dirty state too,
            # but it's also fine for "Save" to be enabled if a path exists, regardless of dirty state.
            # For now, save_project_action is enabled if current_project_path exists.

    def closeEvent(self, event):
        """Handles the event when the user tries to close the main window."""
        if self.project_is_dirty:
            reply = QMessageBox.question(self, 'Unsaved Changes',
                                           "You have unsaved changes. Do you want to save them before closing?",
                                           QMessageBox.StandardButton.Save | 
                                           QMessageBox.StandardButton.Discard | 
                                           QMessageBox.StandardButton.Cancel,
                                           QMessageBox.StandardButton.Cancel) # Default button

            if reply == QMessageBox.StandardButton.Save:
                # Attempt to save. If save is successful, proceed to close.
                # If save is cancelled by user (e.g. in Save As dialog), then ignore close event.
                if self.current_project_path:
                    self.saveProject() # Save to existing path
                    if not self.project_is_dirty: # Check if save was successful (project is no longer dirty)
                        event.accept() # Allow window to close
                    else:
                        event.ignore() # Save might have failed or been cancelled by user from a "Save As"
                else: # No current project path, so trigger "Save As"
                    self.saveProjectAs()
                    if not self.project_is_dirty: # Check if "Save As" was successful
                        event.accept()
                    else:
                        event.ignore() # "Save As" was cancelled by user or failed
            
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept() # Discard changes and allow window to close
            
            else: # QMessageBox.StandardButton.Cancel or closed dialog
                event.ignore() # Cancel the close operation, keep window open
        else:
            event.accept() # No unsaved changes, allow window to close normally

    def _promptToSaveUnsavedChanges(self):
        """
        Checks for unsaved changes and prompts the user to save.
        Returns True if the operation should proceed (changes saved or discarded),
        False if the operation should be cancelled.
        """
        if not self.project_is_dirty:
            return True # No unsaved changes, proceed

        project_name_display = "the current project"
        if self.current_project_path:
            project_name_display = self.current_project_path.split('/')[-1].split('\\')[-1]
        elif self.current_pdf_path:
             pdf_basename = self.current_pdf_path.split('/')[-1].split('\\')[-1]
             project_name_display = f"'{pdf_basename} (untitled project)'"


        reply = QMessageBox.question(self, 'Unsaved Changes',
                                       f"You have unsaved changes in {project_name_display}.\n"
                                       "Do you want to save them?",
                                       QMessageBox.StandardButton.Save | 
                                       QMessageBox.StandardButton.Discard | 
                                       QMessageBox.StandardButton.Cancel,
                                       QMessageBox.StandardButton.Cancel)

        if reply == QMessageBox.StandardButton.Save:
            if self.current_project_path:
                self.saveProject()
            else:
                self.saveProjectAs()
            
            # If save was cancelled (e.g., user cancelled "Save As" dialog),
            # project_is_dirty will still be True. In this case, cancel the calling operation.
            return not self.project_is_dirty # Proceed only if save was successful (not dirty)
        
        elif reply == QMessageBox.StandardButton.Discard:
            return True # Proceed, discarding changes
        
        else: # QMessageBox.StandardButton.Cancel or closed dialog
            return False # Cancel the calling operation

    def _updateUndoRedoActionStates(self):
        """Updates the enabled state of Undo and Redo actions."""
        if hasattr(self, 'undo_action'): # Check if actions exist
            self.undo_action.setEnabled(len(self.undo_stack) > 0)
        if hasattr(self, 'redo_action'):
            self.redo_action.setEnabled(len(self.redo_stack) > 0)

    def executeCommand(self, command):
        """
        Executes a command, adds it to the undo stack, and clears the redo stack.
        A 'command' object is expected to have execute() and undo() methods.
        """
        # In a real implementation, command.execute() might return success/failure
        command.execute() # Assuming command.execute() performs the action

        self.undo_stack.append(command)
        self.redo_stack.clear() # A new action clears the redo history

        self._updateUndoRedoActionStates()
        self._markProjectAsDirty() # Any executed command makes the project dirty
        print(f"Command executed. Undo stack size: {len(self.undo_stack)}, Redo stack size: {len(self.redo_stack)}")


    def undo(self):
        if not self.undo_stack:
            return

        command = self.undo_stack.pop()
        command.undo() # Assuming command.undo() performs the reversal

        self.redo_stack.append(command)
        self._updateUndoRedoActionStates()
        self._markProjectAsDirty() # Undoing an action also makes the project dirty relative to its last saved state
        print(f"Command undone. Undo stack size: {len(self.undo_stack)}, Redo stack size: {len(self.redo_stack)}")

    def redo(self):
        if not self.redo_stack:
            return

        command = self.redo_stack.pop()
        command.execute() # Or command.redo() if it's different

        self.undo_stack.append(command)
        self._updateUndoRedoActionStates()
        self._markProjectAsDirty()
        print(f"Command redone. Undo stack size: {len(self.undo_stack)}, Redo stack size: {len(self.redo_stack)}")

# Main function remains the same
def main():
    app = QApplication(sys.argv)
    ex = DesignerApp()
    ex.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
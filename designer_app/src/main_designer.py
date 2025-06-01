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
                         QKeySequence, QActionGroup, QBrush) # Added QActionGroup

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

        self.setLayout(layout)
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

class InteractivePdfLabel(QLabel):
    rectDefinedSignal = pyqtSignal(QRect)
    # **** CHANGE: Signal now emits instance_id (str) or None ****
    areaSelectionChangedSignal = pyqtSignal(str) # Emits instance_id or empty string/None for deselection
    areaMovedSignal = pyqtSignal(str, QRect) # instance_id, new_view_qrect

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.current_rubber_band_rect = None
        self.origin_point = None      
        # **** CHANGE: Store dicts with 'rect', 'id', AND 'type' ****
        self.page_visual_rects = {} # Key: page_num, Value: list of {'rect': QRect, 'id': str, 'type': str}
        self.current_pixmap_page_num = None
        self.selected_visual_info = None # Stores a selected {'rect': QRect, 'id': str, 'type': str} dict
        self.is_moving_selection = False
        self.drag_start_mouse_pos = None     # QPoint: Mouse position when drag started
        self.drag_start_rect_pos = None    # QPoint: Top-left of rect when drag started



    # **** NEW METHOD ****
    def setCurrentPixmapPage(self, page_num):
        """Sets the page number for the currently displayed pixmap."""
        self.current_pixmap_page_num = page_num
        self.update() # Trigger a repaint to show rects for the new page

    def addVisualRect(self, page_num, view_qrect, instance_id, area_type):
        if page_num not in self.page_visual_rects:
            self.page_visual_rects[page_num] = []
        self.page_visual_rects[page_num].append({'rect': view_qrect, 'id': instance_id, 'type': area_type})

        if page_num == self.current_pixmap_page_num:
            self.update()

    def mousePressEvent(self, event):
        # Initial debug print (as you added)
        if self.parent_widget and hasattr(self.parent_widget, 'current_drawing_tool'):
            print(f"InteractivePdfLabel.mousePressEvent: Active tool from parent: '{self.parent_widget.current_drawing_tool}'")
        else:
            print("InteractivePdfLabel.mousePressEvent: Parent widget or current_drawing_tool not available.")
            return # Cannot proceed without parent context for tool

        if event.button() == Qt.MouseButton.LeftButton and self.pixmap():
            active_tool = self.parent_widget.current_drawing_tool
            click_pos = event.pos()

            drawing_tools = ["text_area", "signature_area", "initials_area"]
            if active_tool in drawing_tools:
                self.origin_point = click_pos
                self.current_rubber_band_rect = QRect(self.origin_point, self.origin_point)
                if self.selected_visual_info is not None:
                    self.selected_visual_info = None
                    self.areaSelectionChangedSignal.emit(None)
                self.update()
            
            elif active_tool == "select_area":
                # ... (Your existing, working selection and Alt+Click logic for "select_area" tool)
                # This block should remain unchanged from when it was working perfectly for selection.
                rect_infos_on_current_page = []
                if self.current_pixmap_page_num is not None:
                    rect_infos_on_current_page = self.page_visual_rects.get(self.current_pixmap_page_num, [])
                
                hits_info_dicts = [info for info in reversed(rect_infos_on_current_page) if info['rect'].contains(click_pos)] # List of dicts
                # Convert to list of QRects for cycling if your previous Alt+Click logic used list of QRects for hits.
                # Or, adapt cycling to work with list of dicts. Let's assume hits_info_dicts is what we need for cycling.

                newly_selected_info_dict = None 
                previous_selection_id = self.selected_visual_info['id'] if self.selected_visual_info else None

                if event.modifiers() == Qt.KeyboardModifier.AltModifier and hits_info_dicts:
                    current_sel_index_in_hits = -1
                    if self.selected_visual_info and self.selected_visual_info in hits_info_dicts: 
                        current_sel_index_in_hits = hits_info_dicts.index(self.selected_visual_info)
                    
                    if current_sel_index_in_hits != -1: 
                        next_index = (current_sel_index_in_hits + 1) % len(hits_info_dicts) # Your cycling logic for select tool
                        newly_selected_info_dict = hits_info_dicts[next_index]
                    elif hits_info_dicts: 
                        newly_selected_info_dict = hits_info_dicts[0] 
                
                elif not event.modifiers() and hits_info_dicts: 
                    newly_selected_info_dict = hits_info_dicts[0] # Topmost hit

                if previous_selection_id != (newly_selected_info_dict['id'] if newly_selected_info_dict else None):
                    self.selected_visual_info = newly_selected_info_dict
                    self.areaSelectionChangedSignal.emit(self.selected_visual_info['id'] if self.selected_visual_info else None)
                    self.update()
                
                # Your debug print block (ensure it's correctly indented within this elif)
                if self.selected_visual_info:
                    print(f"InteractivePdfLabel: Area selected by SelectTool - ID: {self.selected_visual_info['id']}")
                elif previous_selection_id is not None and newly_selected_info_dict is None:
                     print("InteractivePdfLabel: Selection cleared by SelectTool.")


            elif active_tool == "move_area":
                target_to_move_info = None # This will be the info dict {'rect': QRect, 'id': str, 'type': str}
                previous_selection_id = self.selected_visual_info['id'] if self.selected_visual_info else None
                selection_changed_by_this_press = False

                rect_infos_on_current_page = []
                if self.current_pixmap_page_num is not None:
                    rect_infos_on_current_page = self.page_visual_rects.get(self.current_pixmap_page_num, [])

                if event.modifiers() == Qt.KeyboardModifier.AltModifier:
                    # Alt+Click with Move tool: Cycle selection, then prepare to move
                    hits_info_dicts = [info for info in reversed(rect_infos_on_current_page) if info['rect'].contains(click_pos)]
                    if hits_info_dicts:
                        current_sel_index_in_hits = -1
                        if self.selected_visual_info and self.selected_visual_info in hits_info_dicts:
                            current_sel_index_in_hits = hits_info_dicts.index(self.selected_visual_info)
                        
                        if current_sel_index_in_hits != -1: # Cycle from current selection among hits
                            next_index = (current_sel_index_in_hits + 1) % len(hits_info_dicts)
                            target_to_move_info = hits_info_dicts[next_index]
                        else: # No current selection in hits, or no selection at all, pick first hit (topmost)
                            target_to_move_info = hits_info_dicts[0]
                        
                        print(f"MoveTool+Alt: Cycled to ID: {target_to_move_info['id'] if target_to_move_info else 'None'}")
                    # If no hits with Alt, target_to_move_info remains None
                
                else: # Normal Click (no Alt) with Move tool
                    # Priority 1: Is the click on the *currently selected* item?
                    if self.selected_visual_info and self.selected_visual_info['rect'].contains(click_pos):
                        target_to_move_info = self.selected_visual_info
                        print(f"MoveTool: Moving already selected ID: {target_to_move_info['id']}")
                    else:
                        # Priority 2: Clicked not on current selection (or nothing selected), find topmost under cursor
                        hits_info_dicts = [info for info in reversed(rect_infos_on_current_page) if info['rect'].contains(click_pos)]
                        if hits_info_dicts:
                            target_to_move_info = hits_info_dicts[0] # Topmost
                            print(f"MoveTool: Selected topmost ID: {target_to_move_info['id']} for move.")
                        # If no hits (clicked empty space), target_to_move_info remains None

                # Update selection state if it changed due to the (Alt)Click
                if target_to_move_info:
                    if not self.selected_visual_info or self.selected_visual_info['id'] != target_to_move_info['id']:
                        self.selected_visual_info = target_to_move_info
                        self.areaSelectionChangedSignal.emit(self.selected_visual_info['id'])
                        selection_changed_by_this_press = True # Selection changed, needs update
                elif self.selected_visual_info: # Clicked empty space, but something was selected
                    self.selected_visual_info = None
                    self.areaSelectionChangedSignal.emit(None)
                    selection_changed_by_this_press = True

                # Now, if a target was identified (and is now selected), prepare for moving
                if target_to_move_info: # target_to_move_info is now self.selected_visual_info
                    self.is_moving_selection = True
                    self.drag_start_mouse_pos = click_pos
                    self.drag_start_rect_pos = self.selected_visual_info['rect'].topLeft()
                    self.parent_widget.pdf_display_label.setCursor(Qt.CursorShape.ClosedHandCursor)
                    print(f"Move initiated for ID: {self.selected_visual_info['id']}")
                    if not selection_changed_by_this_press: # If selection didn't change but we start move
                        self.update() # Ensure visual cues for move (like cursor) take effect if selection didn't change
                elif selection_changed_by_this_press: # Clicked empty, selection cleared
                    self.update() # Ensure deselection is painted

    def paintEvent(self, event):
        super().paintEvent(event) # Draw the pixmap
        painter = QPainter(self)

        if self.current_pixmap_page_num is not None:
            rect_infos_for_current_page = self.page_visual_rects.get(self.current_pixmap_page_num, [])

            for info in rect_infos_for_current_page:
                rect_to_draw = info['rect']
                area_type = info.get('type', 'text_input') # Default to text_input if type is missing
                is_selected = (self.selected_visual_info is not None and self.selected_visual_info['id'] == info['id'])

                pen_color = Qt.GlobalColor.green if is_selected else Qt.GlobalColor.blue
                pen_width = 2 if is_selected else 1
                pen = QPen(pen_color, pen_width, Qt.PenStyle.SolidLine)
                painter.setPen(pen)

                # **** NEW: Set Brush based on type ****
                current_brush = QBrush(Qt.BrushStyle.NoBrush) # Default: no fill for text_input
                if area_type == "signature_area":
                    # Forward diagonal lines (like /////)
                    current_brush = QBrush(Qt.GlobalColor.darkGray, Qt.BrushStyle.FDiagPattern)
                elif area_type == "initials_area":
                    # Backward diagonal lines (like \\\\\)
                    current_brush = QBrush(Qt.GlobalColor.darkGray, Qt.BrushStyle.BDiagPattern)

                painter.setBrush(current_brush)
                painter.drawRect(rect_to_draw)

        # Draw the current rubber band rectangle (as before)
        if self.current_rubber_band_rect is not None and not self.current_rubber_band_rect.isNull():
            pen_rubber_band = QPen(Qt.GlobalColor.red, 1, Qt.PenStyle.DashLine)
            painter.setPen(pen_rubber_band)
            painter.setBrush(Qt.BrushStyle.NoBrush) # Rubber band has no fill
            painter.drawRect(self.current_rubber_band_rect)


    def mouseMoveEvent(self, event):
        # Handle rubber band drawing for defining new areas
        if self.origin_point is not None and self.current_rubber_band_rect is not None and \
           self.parent_widget and self.parent_widget.current_drawing_tool in ["text_area", "signature_area", "initials_area"]:
            current_pos = event.pos()
            self.current_rubber_band_rect = QRect(self.origin_point, current_pos).normalized()
            self.update()
        
        # **** NEW: Handle moving an existing selected area ****
        elif self.is_moving_selection and self.selected_visual_info:
            mouse_delta = event.pos() - self.drag_start_mouse_pos
            new_top_left = self.drag_start_rect_pos + mouse_delta
            
            # Update the 'rect' QRect object directly. Since it's a reference
            # to the one in page_visual_rects, that list will also see the change.
            self.selected_visual_info['rect'].moveTo(new_top_left)
            self.update() # Trigger repaint to show the rectangle moving

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Finalize defining a new area (rubber band)
            if self.origin_point is not None and self.current_rubber_band_rect is not None and \
               self.current_pixmap_page_num is not None and self.parent_widget and \
               self.parent_widget.current_drawing_tool in ["text_area", "signature_area", "initials_area"]:
                
                final_rect_view = self.current_rubber_band_rect.normalized()
                if final_rect_view.width() > 0 and final_rect_view.height() > 0:
                    self.rectDefinedSignal.emit(final_rect_view)
                
                self.origin_point = None
                self.current_rubber_band_rect = None
                self.update()

            # **** NEW: Finalize moving a selection ****
            elif self.is_moving_selection and self.selected_visual_info:
                instance_id = self.selected_visual_info['id']
                new_view_qrect = self.selected_visual_info['rect'] # This is the updated rect

                print(f"Move ended for ID: {instance_id}. New view QRect: {new_view_qrect}")
                self.areaMovedSignal.emit(instance_id, new_view_qrect) # Emit signal to DesignerApp
                
                self.is_moving_selection = False
                self.drag_start_mouse_pos = None
                self.drag_start_rect_pos = None
                # Cursor will be reset by DesignerApp when tool mode is confirmed or changed
                # Or set it back to OpenHand for the move tool here:
                if self.parent_widget and self.parent_widget.current_drawing_tool == "move_area":
                    self.parent_widget.pdf_display_label.setCursor(Qt.CursorShape.OpenHandCursor)
                self.update() # Ensure final position is painted
            
            # If it was a click for selection and not a move, state is already handled by mousePress
            # No explicit else needed here if mousePress handled selection updates.

    def clearDefinedRects(self):
        self.page_visual_rects = {}
        self.selected_visual_info = None # Clear selection too
        self.update()

    # **** NEW METHOD: To remove a specific visual rectangle by its ID ****
    def removeVisualRectById(self, page_num, instance_id):
        if page_num in self.page_visual_rects:
            self.page_visual_rects[page_num] = [info for info in self.page_visual_rects[page_num] if info['id'] != instance_id]
            if self.selected_visual_info and self.selected_visual_info['id'] == instance_id:
                self.selected_visual_info = None
                # No need to emit here, DesignerApp will call handleAreaSelectionChanged(None) after deletion
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
        self.current_zoom_factor = 1.5
        self.defined_pdf_areas = []
        self.current_drawing_tool = None # Will be set in initUI or by tool selection
        self.currently_selected_area_instance_id = None # **** NEW/REPURPOSED ****
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

        toolbar.addSeparator()

        # Delete Area Action (as before)
        self.delete_area_action = QAction("Delete Area", self)
        # ... (rest of delete_area_action setup)
        self.delete_area_action.setStatusTip("Delete the currently selected area")
        self.delete_area_action.triggered.connect(self.deleteSelectedArea)
        self.delete_area_action.setEnabled(False) 
        toolbar.addAction(self.delete_area_action)

        # Edit Area Properties Action (as before)
        self.edit_area_action = QAction("Edit Properties", self)
        # ... (rest of edit_area_action setup)
        self.edit_area_action.setStatusTip("Edit properties of the currently selected area")
        self.edit_area_action.triggered.connect(self.editSelectedAreaProperties)
        self.edit_area_action.setEnabled(False) 
        toolbar.addAction(self.edit_area_action)

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
        # ... (pdf_display_label setup as before) ...
        self.default_min_display_width = 400
        self.default_min_display_height = 300
        self.pdf_display_label.setMinimumSize(self.default_min_display_width, self.default_min_display_height)
        self.pdf_display_label.setStyleSheet("QLabel { background-color : lightgray; border: 1px solid black; }")
        
        self.pdf_display_label.rectDefinedSignal.connect(self.handleRectDefined)
        # **** NEW: Connect the new signal ****
        self.pdf_display_label.areaSelectionChangedSignal.connect(self.handleAreaSelectionChanged)
        
        self.scroll_area = QScrollArea(self)
        # ... (scroll_area setup as before) ...
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.pdf_display_label)
        main_layout.addWidget(self.scroll_area)
        main_layout.setStretchFactor(self.scroll_area, 1)

        # Explicitly set initial UI state reflecting no tool is active
        self.info_label.setText("Select a tool from the toolbar or load a PDF.")
        self.pdf_display_label.setCursor(Qt.CursorShape.ArrowCursor)

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
                    'type': area_info['type'] # Get type from stored data
                })
        return view_rect_infos

    def displayPdfPage(self, page_num): # Revised structure for clarity
        # ... (initial checks and page loading to get qpixmap) ...
        if not self.pdf_document or page_num < 0 or page_num >= self.pdf_document.page_count:
            # ... reset and return ... (as before)
            self._reset_pdf_display_label("Invalid page number or no PDF loaded.")
            # self.currently_selected_area_instance_id = None # Already handled by _reset which calls handleAreaSelectionChanged
            self._updateNavigation()
            return

        # Clear DesignerApp's idea of selection if page changes
        if self.current_page_num != page_num and self.currently_selected_area_instance_id:
            self.handleAreaSelectionChanged(None)

        try:
            # ... (load page, render pixmap, create qpixmap as before) ...
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
                self.pdf_display_label.addVisualRect(page_num, info['rect'], info['id'], info['type'])
            # The label's own selected_visual_info will be None due to setCurrentPixmapPage or clearDefinedRects
            # or if it's re-selected, mousePressEvent will handle it.

            self.pdf_display_label.setMinimumSize(qpixmap.width(), qpixmap.height())
            self.pdf_display_label.adjustSize() 

            self.current_page_num = page_num
            self._updateNavigation() # Update page X of Y and nav buttons

            if self.scroll_area:
                self.scroll_area.verticalScrollBar().setValue(0)
                self.scroll_area.horizontalScrollBar().setValue(0)
        except Exception as e:
            # ... (error handling as before) ...
            QMessageBox.critical(self, "Error Displaying Page", f"Could not display page {page_num + 1}: {e}")
            self._reset_pdf_display_label(f"Error displaying page {page_num + 1}")
            # self.currently_selected_area_instance_id = None # Already handled by _reset
            self._updateNavigation()

    def handleRectDefined(self, view_qrect):
        if not self.pdf_document or self.pdf_display_label.current_pixmap_page_num is None:
            return 
        
        current_tool_page = self.pdf_display_label.current_pixmap_page_num
        tool_type_for_dialog = ""
        default_name_prefix = ""
        area_data_type_string = ""

        if self.current_drawing_tool == "text_area":
            tool_type_for_dialog = "Text Input"
            default_name_prefix = "TextArea"
            area_data_type_string = "text_input"
        elif self.current_drawing_tool == "signature_area":
            tool_type_for_dialog = "Signature Area"
            default_name_prefix = "SignatureArea"
            area_data_type_string = "signature_area"
        elif self.current_drawing_tool == "initials_area": # **** NEW elif block ****
            tool_type_for_dialog = "Initials Area"
            default_name_prefix = "InitialsArea"
            area_data_type_string = "initials_area"
        else:
            print(f"Rectangle defined with no active drawing tool or unknown tool: {self.current_drawing_tool}")
            return # Do not proceed

        # Common logic for dialog and processing
        suggested_data_field_id = f"{default_name_prefix}_{len(self.defined_pdf_areas) + 1}"
        current_prompt_text = ""

        while True:
            dialog = AreaPropertiesDialog(
                area_type=tool_type_for_dialog, 
                default_data_field_id=suggested_data_field_id,
                default_prompt=current_prompt_text,          
                parent=self
            )

            if dialog.exec() == QDialog.DialogCode.Accepted:
                properties = dialog.getProperties()
                suggested_data_field_id = properties["data_field_id"] if properties else suggested_data_field_id
                current_prompt_text = properties["prompt"] if properties else current_prompt_text

                if properties and properties["data_field_id"]:
                    inverse_matrix = ~fitz.Matrix(self.current_zoom_factor, self.current_zoom_factor)
                    view_fitz_rect = fitz.Rect(view_qrect.x(), view_qrect.y(),
                                               view_qrect.right(), view_qrect.bottom())
                    pdf_fitz_rect = view_fitz_rect * inverse_matrix
                    instance_id = f"inst_{uuid.uuid4().hex[:8]}"

                    defined_area_info = {
                        'instance_id': instance_id,
                        'page_num': current_tool_page,
                        'rect_pdf': tuple(pdf_fitz_rect.irect), 
                        'data_field_id': properties["data_field_id"],
                        'type': area_data_type_string, # This is "text_input", "signature_area", or "initials_area"
                        'prompt': properties["prompt"],
                        'view_qrect_tuple': (view_qrect.x(), view_qrect.y(), 
                                            view_qrect.width(), view_qrect.height())
                    }
                    self.defined_pdf_areas.append(defined_area_info)

                    print(f"Area Defined ({area_data_type_string}) and Accepted (Instance ID: {instance_id}):")
                    print(f"  Data Field ID: {properties['data_field_id']}, Prompt: {properties['prompt']}")
                    print(f"  Total Defined Areas: {len(self.defined_pdf_areas)}")

                    self.pdf_display_label.addVisualRect(current_tool_page, view_qrect, instance_id, area_data_type_string)
                    break 
                else: 
                    QMessageBox.warning(self, "Missing Information", 
                                        "Data Field Name / Link ID cannot be empty. Please try again.")
            else: 
                print(f"Area definition ({area_data_type_string}) cancelled by user.")
                break 

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
                    # Ensure save actions remain disabled
                    if hasattr(self, 'save_project_as_action'): self.save_project_as_action.setEnabled(False)
                    if hasattr(self, 'save_project_action'): self.save_project_action.setEnabled(False)
                    return

                self.pdf_document = doc
                self.current_pdf_path = file_name # Store new PDF path
                self.current_page_num = 0 
                self.current_zoom_factor = 1.5
                self.info_label.setText(f"Loaded: {file_name.split('/')[-1]} ({self.pdf_document.page_count} pages)")
                self.displayPdfPage(self.current_page_num)
                
                # Enable "Save Project As..." now that a PDF is loaded
                if hasattr(self, 'save_project_as_action'):
                    self.save_project_as_action.setEnabled(True)
                # "Save" remains disabled until a "Save As..." is done for this new context
                if hasattr(self, 'save_project_action'):
                     self.save_project_action.setEnabled(False)

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
                'defined_areas': self.defined_pdf_areas
            }
            try:
                with open(self.current_project_path, 'w') as f:
                    json.dump(project_data, f, indent=4)
                self.statusBar().showMessage(f"Project saved to {self.current_project_path}", 5000)
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
                # **** NEW: Enable "Save" action after "Save As..." ****
                self.save_project_action.setEnabled(True) 
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
        # TODO (Advanced): Check for unsaved changes and prompt.
        
        if self.pdf_document:
            self.pdf_document.close()
            self.pdf_document = None

        self.current_pdf_path = None
        self.current_project_path = None # **** ENSURE THIS IS CLEARED ****
        self.defined_pdf_areas = []
        self.current_page_num = 0
        
        self.pdf_display_label.clearDefinedRects()
        self._reset_pdf_display_label("Load a PDF to begin a new project.")
        self._updateNavigation()

        self.info_label.setText("New project started. Load a PDF.")
        self.statusBar().showMessage("New project created. Ready.", 5000)

        # Update enabled state of menu actions
        if hasattr(self, 'save_project_as_action'):
            self.save_project_as_action.setEnabled(False)
        if hasattr(self, 'save_project_action'): # **** ENSURE SAVE IS DISABLED ****
            self.save_project_action.setEnabled(False)
        
        print("New project started.")

    def openExistingProject(self):
        # TODO (Advanced): Check for unsaved changes in the current project and prompt to save.
        
        file_path, _ = QFileDialog.getOpenFileName(self, "Open SpeedyF Project", "",
                                                   "SpeedyF Project Files (*.speedyf_proj);;All Files (*)")

        if not file_path:
            self.statusBar().showMessage("Open project cancelled.", 2000)
            return

        try:
            with open(file_path, 'r') as f:
                project_data = json.load(f)

            # Basic validation of project file structure
            if 'pdf_path' not in project_data or 'defined_areas' not in project_data:
                QMessageBox.critical(self, "Error", "Invalid project file format.")
                return

            # --- Successfully read project data, now apply it ---

            # 1. Reset current state (like "New Project")
            self.newProject() # This clears pdf_document, paths, defined_areas, visuals etc.

            # 2. Attempt to load the PDF specified in the project file
            loaded_pdf_path = project_data['pdf_path']
            
            # Temporarily store defined areas from file, as openPdfFile will clear self.defined_pdf_areas
            project_defined_areas = project_data.get('defined_areas', [])
            
            # Attempt to open the PDF.
            # We'll call a slightly modified or a direct way to open PDF without full reset of areas yet.
            # For now, let's assume openPdfFile is called and then we repopulate.
            
            # --- Re-evaluate PDF opening part ---
            # Option A: Use existing openPdfFile, then overwrite defined_areas
            # Option B: Create a leaner _loadPdfDocument(path) that doesn't reset everything

            # Let's try Option A carefully:
            # newProject() has already cleared everything.
            # Now, specifically load the PDF document.
            
            try: # Inner try for PDF loading specifically from project file
                doc = fitz.open(loaded_pdf_path)
                if not doc.is_pdf: # Should ideally not happen if saved correctly
                    doc.close()
                    QMessageBox.critical(self, "Project Error", f"The linked file '{loaded_pdf_path}' is not a valid PDF.")
                    # State is already reset by newProject(), so just return
                    return
                
                # If PDF loaded from project path is successful:
                self.pdf_document = doc
                self.current_pdf_path = loaded_pdf_path # Set current PDF path
                self.current_project_path = file_path # Set current PROJECT path
                self.current_page_num = 0 # Start at first page
                self.current_zoom_factor = project_data.get('zoom_factor', 1.5) # Load zoom if saved, else default

                self.info_label.setText(f"Loaded: {loaded_pdf_path.split('/')[-1]} ({self.pdf_document.page_count} pages)")
                
                # 3. Restore defined areas
                self.defined_pdf_areas = project_defined_areas # Restore from file
                
                # 4. Display the first page (this will also trigger redisplay of visual rects IF integrated there)
                self.displayPdfPage(self.current_page_num) # This now needs to also draw the rects

                # 5. Update UI states
                self.save_project_as_action.setEnabled(True)
                self.save_project_action.setEnabled(True) # Project is now "saved" to current_project_path
                self.statusBar().showMessage(f"Project '{file_path.split('/')[-1]}' opened.", 5000)
                print(f"Project opened. Defined areas: {len(self.defined_pdf_areas)}")

            except Exception as e_pdf:
                QMessageBox.critical(self, "Error Loading PDF from Project", 
                                     f"Could not load PDF '{loaded_pdf_path}': {e_pdf}")
                # State was already reset by newProject(), so just inform user.
                # self._reset_pdf_display_label and _updateNavigation were called by newProject()
                return

        except FileNotFoundError:
            QMessageBox.critical(self, "Error", f"Project file not found: {file_path}")
        except json.JSONDecodeError:
            QMessageBox.critical(self, "Error", f"Could not parse project file. Invalid JSON: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error Opening Project", f"An unexpected error occurred: {e}")
            self.newProject() # Reset to a clean state on generic error


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
            return

        selected_id = self.currently_selected_area_instance_id
        area_to_delete_page_num = -1
        area_found_in_data = False

        # Find and remove the area from the data model (self.defined_pdf_areas)
        for i, area_info in enumerate(self.defined_pdf_areas):
            if area_info['instance_id'] == selected_id:
                area_to_delete_page_num = area_info['page_num']
                del self.defined_pdf_areas[i]
                area_found_in_data = True
                print(f"Data for area {selected_id} removed from self.defined_pdf_areas.")
                break
        
        if not area_found_in_data:
            print(f"Error: Could not find data for selected area ID {selected_id} to delete.")
            # Clear selection just in case, though this state should ideally not occur
            self.handleAreaSelectionChanged(None) 
            if self.pdf_display_label.selected_visual_info and \
               self.pdf_display_label.selected_visual_info.get('id') == selected_id:
                self.pdf_display_label.selected_visual_info = None
                self.pdf_display_label.update()
            return

        # Tell InteractivePdfLabel to remove the visual representation
        # We need the page number where the visual rect was.
        # The selected_id was on self.pdf_display_label.current_pixmap_page_num
        # or area_to_delete_page_num if found.
        
        # The selection highlight is managed by InteractivePdfLabel's selected_visual_info.
        # The visual rectangle itself is in InteractivePdfLabel's page_visual_rects.
        
        current_label_page = self.pdf_display_label.current_pixmap_page_num
        if area_to_delete_page_num != -1 : # Check if page_num was found
            # Remove the visual rectangle from the label's storage
            removed_visual = self.pdf_display_label.removeVisualRectById(area_to_delete_page_num, selected_id)
            if removed_visual:
                print(f"Visual for area {selected_id} on page {area_to_delete_page_num + 1} removed.")
            else:
                print(f"Warning: Visual for area {selected_id} on page {area_to_delete_page_num + 1} not found in label's store for removal.")

            # If the deleted area was on the currently displayed page, 
            # ensure the label updates and clears its own selection state for that ID.
            if area_to_delete_page_num == current_label_page:
                if self.pdf_display_label.selected_visual_info and \
                   self.pdf_display_label.selected_visual_info.get('id') == selected_id:
                    self.pdf_display_label.selected_visual_info = None 
                    # No need to emit here, handleAreaSelectionChanged(None) below will do it for DesignerApp
                self.pdf_display_label.update() # Repaint the label to remove the blue box and highlight

        # Clear the current selection in DesignerApp and update UI (e.g., disable Delete button)
        self.handleAreaSelectionChanged(None) 

        self.statusBar().showMessage(f"Area {selected_id} deleted.", 3000)
        print(f"Area {selected_id} deleted. Remaining areas: {len(self.defined_pdf_areas)}")
        # TODO (Advanced): Mark project as "dirty" / needing save.

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
        area_index = -1

        # Find the area in the data model
        for i, area_info in enumerate(self.defined_pdf_areas):
            if area_info['instance_id'] == selected_id:
                area_data_to_edit = area_info
                area_index = i
                break
        
        if not area_data_to_edit:
            QMessageBox.warning(self, "Error", f"Could not find data for selected area ID {selected_id} to edit.")
            # This state implies an inconsistency, clear selection.
            self.handleAreaSelectionChanged(None) 
            if self.pdf_display_label.selected_visual_info and \
               self.pdf_display_label.selected_visual_info.get('id') == selected_id:
                self.pdf_display_label.selected_visual_info = None
                self.pdf_display_label.update()
            return

        # Pre-fill the dialog with existing properties
        dialog = AreaPropertiesDialog(
            area_type=area_data_to_edit.get('type', 'Text Input'), # Get type from data
            default_data_field_id=area_data_to_edit.get('data_field_id', ''),
            default_prompt=area_data_to_edit.get('prompt', ''),
            parent=self
        )
        dialog.setWindowTitle(f"Edit Area Properties (ID: {selected_id})") # Update dialog title

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_properties = dialog.getProperties()
            if new_properties and new_properties["data_field_id"]: # Ensure new data_field_id is not empty
                # Update the existing dictionary in self.defined_pdf_areas
                self.defined_pdf_areas[area_index]['data_field_id'] = new_properties['data_field_id']
                self.defined_pdf_areas[area_index]['prompt'] = new_properties['prompt']
                # Type is not editable in this dialog for now, so it remains unchanged.
                # instance_id, page_num, rect_pdf, view_qrect_tuple also remain unchanged by this edit.

                print(f"Properties updated for area {selected_id}:")
                print(f"  New Data Field ID: {new_properties['data_field_id']}")
                print(f"  New Prompt: {new_properties['prompt']}")
                self.statusBar().showMessage(f"Properties for area {selected_id} updated.", 3000)
                # TODO (Advanced): If data_field_id changed, and if we had color-coding by family,
                # we might need to tell InteractivePdfLabel to update the color of this visual rect.
                # For now, the blue box's appearance doesn't change based on this metadata edit.
                # Also, mark project as "dirty" / needing save.
            else:
                QMessageBox.warning(self, "Missing Information", 
                                    "Data Field Name / Link ID cannot be empty. Properties not updated.")
        else:
            print(f"Editing properties for area {selected_id} cancelled.")

# Main function remains the same
def main():
    app = QApplication(sys.argv)
    ex = DesignerApp()
    ex.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
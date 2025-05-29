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
                         QKeySequence, QActionGroup) # Added QActionGroup

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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.setCursor(Qt.CursorShape.CrossCursor)
        
        self.current_rubber_band_rect = None
        self.origin_point = None      
        # **** CHANGE: Store visual rects per page ****
        # Key: page_num (int), Value: list of QRect (view coordinates)
        self.page_visual_rects = {} 
        self.current_pixmap_page_num = None # Page number of the currently displayed pixmap

    # **** NEW METHOD ****
    def setCurrentPixmapPage(self, page_num):
        """Sets the page number for the currently displayed pixmap."""
        self.current_pixmap_page_num = page_num
        self.update() # Trigger a repaint to show rects for the new page

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.pixmap() and self.parent_widget:
            active_tool = self.parent_widget.current_drawing_tool
            click_pos = event.pos() # Get click position once

            if active_tool == "text_area": # Or other drawing tools later
                self.origin_point = click_pos
                self.current_rubber_band_rect = QRect(self.origin_point, self.origin_point)
                self.selected_view_rect = None # Clear any selection when starting to draw new
                self.update()

            elif active_tool == "select_area":
                rects_on_current_page = []
                if self.current_pixmap_page_num is not None:
                    rects_on_current_page = self.page_visual_rects.get(self.current_pixmap_page_num, [])

                hits = []
                # Iterate normally: first in list is "bottom-most" if appended, last is "top-most"
                for i, rect in enumerate(rects_on_current_page):
                    if rect.contains(click_pos):
                        hits.append({'rect': rect, 'index_in_list': i}) 
                        # Storing original index might be useful later, but for cycling, order in hits matters.
                        # For cycling, let's rephrase: hits will be a list of QRects in their Z-order (topmost last)

                # Let's rebuild hits so that topmost is last in the list
                hits = [r['rect'] for r in sorted(hits, key=lambda x: x['index_in_list'])]


                newly_selected_rect = None

                if event.modifiers() == Qt.KeyboardModifier.AltModifier and hits:
                    # Alt+Click: Cycle through hits
                    print("Alt+Click detected. Hits:", len(hits))
                    if self.selected_view_rect and self.selected_view_rect in hits:
                        try:
                            current_selection_index_in_hits = hits.index(self.selected_view_rect)
                            # Cycle "downwards" (visually deeper, earlier in draw order)
                            next_index = (current_selection_index_in_hits - 1 + len(hits)) % len(hits)
                            newly_selected_rect = hits[next_index]
                            print(f"Cycling selection. Old index in hits: {current_selection_index_in_hits}, New index: {next_index}")
                        except ValueError: # Should not happen if selected_view_rect is in hits
                            newly_selected_rect = hits[-1] # Default to topmost if error
                    else:
                        # No current selection, or current selection not under Alt+Click point
                        # Select the topmost one (last in the 'hits' list, as it was drawn last among hits)
                        newly_selected_rect = hits[-1] if hits else None
                        print("Alt+Click selected topmost or first in cycle.")

                elif not event.modifiers() and hits: # Normal click (no Alt)
                    # Select the topmost one (last in the 'hits' list)
                    newly_selected_rect = hits[-1] if hits else None
                    print("Normal click selected topmost.")

                # Update selection state
                if self.selected_view_rect != newly_selected_rect:
                    self.selected_view_rect = newly_selected_rect
                    self.update() # Trigger repaint

                if self.selected_view_rect:
                    print(f"Area selected on page {self.current_pixmap_page_num + 1}: {self.selected_view_rect}")
                    # TODO: Emit a signal to DesignerApp with info about the selected area
                else:
                    # If newly_selected_rect is None (because no hits or Alt+Click deselect)
                    # and self.selected_view_rect was already None, no "cleared" message is needed unless it changed.
                    # The above if condition handles the update call only if selection actually changes.
                    # Let's ensure a message if it becomes None from something.
                    if newly_selected_rect is None and self.selected_view_rect is not None: # Check if it *became* None
                        self.selected_view_rect = None # Ensure it's set
                        self.update()
                        print("Selection cleared by click on empty space.")

    def mouseMoveEvent(self, event):
        if self.origin_point is not None and self.pixmap(): 
            current_pos = event.pos()
            self.current_rubber_band_rect = QRect(self.origin_point, current_pos).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and \
           self.origin_point is not None and \
           self.current_rubber_band_rect is not None and \
           self.pixmap() and \
           self.current_pixmap_page_num is not None: # Ensure we know the page

            final_rect_view = self.current_rubber_band_rect.normalized()
            
            if final_rect_view.width() > 0 and final_rect_view.height() > 0:
                # Emit signal with the current page number and the view rectangle
                # We'll let DesignerApp tell us to add it visually via addVisualRect
                self.rectDefinedSignal.emit(final_rect_view) # Signal remains the same for now
                                                              # DesignerApp knows the current page
            
            self.origin_point = None
            self.current_rubber_band_rect = None
            self.update()
        else:
            self.origin_point = None
            self.current_rubber_band_rect = None
            if self.pixmap():
                self.update()

    def paintEvent(self, event):
        super().paintEvent(event) # Draw the pixmap
        painter = QPainter(self)
        
        # Draw all committed visual rectangles for the current page
        if self.current_pixmap_page_num is not None:
            rects_for_current_page = self.page_visual_rects.get(self.current_pixmap_page_num, [])
            
            for rect in rects_for_current_page:
                if rect == self.selected_view_rect: # Skip drawing selected one with default style
                    continue 
                pen_defined = QPen(Qt.GlobalColor.blue, 1, Qt.PenStyle.SolidLine)
                painter.setPen(pen_defined)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(rect)
            
            # Draw the selected rectangle with a different style (if any is selected)
            if self.selected_view_rect is not None:
                # Ensure selected_view_rect is one of the rects for the current page
                # (This check is implicitly handled if selected_view_rect is set from rects_on_current_page)
                pen_selected = QPen(Qt.GlobalColor.green, 2, Qt.PenStyle.SolidLine) # Thicker, green
                painter.setPen(pen_selected)
                painter.setBrush(Qt.BrushStyle.NoBrush) # Or a semi-transparent fill
                painter.drawRect(self.selected_view_rect)
            
        # Draw the current rubber band rectangle if one is being drawn
        if self.current_rubber_band_rect is not None and not self.current_rubber_band_rect.isNull():
            pen_rubber_band = QPen(Qt.GlobalColor.red, 1, Qt.PenStyle.DashLine)
            painter.setPen(pen_rubber_band)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.current_rubber_band_rect)

    # **** MODIFIED METHOD ****
    def addVisualRect(self, page_num, view_qrect):
        """Adds a QRect (in view coordinates) for a specific page to be displayed."""
        if page_num not in self.page_visual_rects:
            self.page_visual_rects[page_num] = []
        self.page_visual_rects[page_num].append(view_qrect)
        
        # Only update if the added rect is for the currently visible page
        if page_num == self.current_pixmap_page_num:
            self.update()

    # **** MODIFIED METHOD ****
    def clearDefinedRects(self):
        """Clears all visually defined rectangles for all pages."""
        self.page_visual_rects = {}
        self.update() # Repaint to clear visuals

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
        self.initUI()
        self.setSelectToolActive() # Make select tool active by default after UI is ready

    def initUI(self):
        self.setWindowTitle('SpeedyF Designer')
        self.setGeometry(100, 100, 900, 750)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Menu Bar ---
        menubar = self.menuBar()
        file_menu = menubar.addMenu('&File')

        # New Project Action (as before)
        new_project_action = QAction('&New Project', self)
        new_project_action.setStatusTip('Create a new project')
        new_project_action.setShortcut(QKeySequence.StandardKey.New)
        new_project_action.triggered.connect(self.newProject)
        file_menu.addAction(new_project_action)

        # **** NEW: Open Project Action ****
        open_project_action = QAction('&Open Project...', self)
        open_project_action.setStatusTip('Open an existing project')
        open_project_action.setShortcut(QKeySequence.StandardKey.Open) # Ctrl+O
        open_project_action.triggered.connect(self.openExistingProject)
        file_menu.addAction(open_project_action)

        file_menu.addSeparator() # Separator

        # Save Project Action (as before)
        self.save_project_action = QAction('&Save Project', self)
        # ... (rest of save_project_action setup as before) ...
        self.save_project_action.setStatusTip('Save the current project')
        self.save_project_action.setShortcut(QKeySequence.StandardKey.Save) 
        self.save_project_action.triggered.connect(self.saveProject)
        self.save_project_action.setEnabled(False) 
        file_menu.addAction(self.save_project_action)


        # Save Project As... Action (as before)
        self.save_project_as_action = QAction('&Save Project As...', self)
        # ... (rest of save_project_as_action setup as before) ...
        self.save_project_as_action.setStatusTip('Save the current project to a new file')
        self.save_project_as_action.triggered.connect(self.saveProjectAs)
        self.save_project_as_action.setEnabled(False)
        file_menu.addAction(self.save_project_as_action)

  # --- Toolbar ---
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        # Action Group for tools (to make them mutually exclusive)
        self.tool_action_group = QActionGroup(self)
        self.tool_action_group.setExclusive(True) # Only one action can be checked at a time
        self.tool_action_group.triggered.connect(self.handleToolSelected) # Connect group's signal

        # Select Area Action
        self.select_area_action = QAction("Select Area", self) 
        # self.select_area_action.setIcon(QIcon("path/to/select_icon.png")) # Optional icon
        self.select_area_action.setStatusTip("Select, move, or edit defined areas")
        self.select_area_action.setCheckable(True)
        self.select_area_action.setData("select_area") # Store tool identifier
        toolbar.addAction(self.select_area_action)
        self.tool_action_group.addAction(self.select_area_action)

        # Define Text Area Action (modify slightly to use setData)
        self.define_text_area_action = QAction("Text Area", self)
        # self.define_text_area_action.setIcon(QIcon("path/to/text_icon.png")) # Optional icon
        self.define_text_area_action.setStatusTip("Define a text input area")
        self.define_text_area_action.setCheckable(True)
        self.define_text_area_action.setData("text_area") # Store tool identifier
        # self.define_text_area_action.triggered.connect(self.setTextAreaTool) # Old connection - remove
        toolbar.addAction(self.define_text_area_action)
        self.tool_action_group.addAction(self.define_text_area_action)


        # --- Controls Widget (as before) ---
        controls_widget = QWidget()
        # ... (rest of controls_widget and its layout as before) ...
        controls_layout = QVBoxLayout(controls_widget)
        self.info_label = QLabel('Select a tool, then load a PDF to begin.', self)
        controls_layout.addWidget(self.info_label)
        # ... (load_pdf_button, nav_layout as before) ...
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


        # --- PDF Display Area (as before) ---
        self.pdf_display_label = InteractivePdfLabel(self)
        # ... (rest of pdf_display_label and scroll_area setup as before) ...
        self.default_min_display_width = 400
        self.default_min_display_height = 300
        self.pdf_display_label.setMinimumSize(self.default_min_display_width, self.default_min_display_height)
        self.pdf_display_label.setStyleSheet("QLabel { background-color : lightgray; border: 1px solid black; }")
        self.pdf_display_label.rectDefinedSignal.connect(self.handleRectDefined)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.pdf_display_label)
        main_layout.addWidget(self.scroll_area)
        main_layout.setStretchFactor(self.scroll_area, 1)

        # Status Bar (QMainWindow has one by default)
        self.statusBar().showMessage("Ready")

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

    def _reset_pdf_display_label(self, message="PDF page will appear here"):
        print("Attempting _reset_pdf_display_label...") # For debugging
        self.pdf_display_label.setPixmap(QPixmap()) 
        self.pdf_display_label.setText(message) 
        self.pdf_display_label.setMinimumSize(self.default_min_display_width, self.default_min_display_height)
        self.pdf_display_label.adjustSize()
        self.pdf_display_label.setCurrentPixmapPage(None)
        self.pdf_display_label.selected_view_rect = None # **** NEW: Clear selection ****
        
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
        """Transforms stored PDF rects for a given page to view QRects."""
        view_qrects = []
        if not self.pdf_document:
            return view_qrects

        # Forward transformation matrix
        matrix = fitz.Matrix(self.current_zoom_factor, self.current_zoom_factor)

        for area_info in self.defined_pdf_areas:
            if area_info['page_num'] == page_num:
                pdf_coords = area_info['rect_pdf'] # This is a tuple (x0, y0, x1, y1)
                pdf_fitz_rect = fitz.Rect(pdf_coords[0], pdf_coords[1], pdf_coords[2], pdf_coords[3])
                
                view_fitz_rect = pdf_fitz_rect * matrix # Apply forward transform
                
                # Convert fitz.Rect (x0,y0,x1,y1) to QRect (x,y,width,height)
                view_qrect = QRect(round(view_fitz_rect.x0), round(view_fitz_rect.y0),
                                   round(view_fitz_rect.width), round(view_fitz_rect.height))
                view_qrects.append(view_qrect)
        return view_qrects

    def displayPdfPage(self, page_num):
        if not self.pdf_document or page_num < 0 or page_num >= self.pdf_document.page_count:
            self._reset_pdf_display_label("Invalid page number or no PDF loaded.")
            self._updateNavigation()
            return

        try:
            page = self.pdf_document.load_page(page_num)
            mat = fitz.Matrix(self.current_zoom_factor, self.current_zoom_factor)
            pix = page.get_pixmap(matrix=mat)
            img_format = QImage.Format.Format_RGB888 if pix.alpha == 0 else QImage.Format.Format_RGBA8888
            qimage = QImage(pix.samples, pix.width, pix.height, pix.stride, img_format)
            qpixmap = QPixmap.fromImage(qimage)
            
            self.pdf_display_label.selected_view_rect = None # Clear selection when page changes
            self.pdf_display_label.setPixmap(qpixmap)
            self.pdf_display_label.setCurrentPixmapPage(page_num) 
            
            self.pdf_display_label.setMinimumSize(qpixmap.width(), qpixmap.height())
            self.pdf_display_label.adjustSize() 

            self.current_page_num = page_num # Set current page before updating nav and rects
            self._updateNavigation()

            # **** NEW: Re-display visual rects for this page ****
            self.pdf_display_label.clearDefinedRects() # Clear any old page's visual rects from label
            view_rects_for_this_page = self._get_view_rects_for_page(page_num)
            for vr in view_rects_for_this_page:
                # addVisualRect in InteractivePdfLabel needs page_num and qrect
                self.pdf_display_label.addVisualRect(page_num, vr)
            # Ensure the label repaints if rects were added (addVisualRect should handle this if page matches)
            # self.pdf_display_label.update() # May not be needed if addVisualRect updates

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

        if self.current_drawing_tool == "text_area":
            # Prepare initial values for the dialog. These will be updated if the user makes an error
            # and the dialog needs to re-appear with previously entered data.
            # For the very first time, we can suggest a default name or leave it blank.
            suggested_data_field_id = f"TextArea_{len(self.defined_pdf_areas) + 1}" # Optional suggestion
            current_prompt_text = "" # Start with an empty prompt

            while True: # Loop until dialog is accepted with valid data, or cancelled
                dialog = AreaPropertiesDialog(
                    area_type="Text Input", 
                    default_data_field_id=suggested_data_field_id, # Pass the current/suggested ID
                    default_prompt=current_prompt_text,           # Pass the current prompt
                    parent=self
                )

                if dialog.exec() == QDialog.DialogCode.Accepted:
                    properties = dialog.getProperties()
                    
                    # Preserve entered values for potential next iteration of the dialog
                    suggested_data_field_id = properties["data_field_id"] if properties else suggested_data_field_id
                    current_prompt_text = properties["prompt"] if properties else current_prompt_text

                    if properties and properties["data_field_id"]: # Ensure a name was provided
                        # Valid input: Proceed to create and store the area information
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
                            'type': "text_input", 
                            'prompt': properties["prompt"]
                        }
                        self.defined_pdf_areas.append(defined_area_info)

                        print(f"Area Defined and Accepted:")
                        print(f"  Data Field ID: {properties['data_field_id']}, Prompt: {properties['prompt']}")
                        # ... (other print statements if you want them) ...
                        print(f"  Total Defined Areas: {len(self.defined_pdf_areas)}")

                        self.pdf_display_label.addVisualRect(current_tool_page, view_qrect)
                        break # Exit the while loop, successfully defined
                    
                    else: # Dialog accepted, but data_field_id was empty
                        QMessageBox.warning(self, "Missing Information", 
                                            "Data Field Name / Link ID cannot be empty. Please try again.")
                        # Loop continues, dialog will re-appear.
                        # suggested_data_field_id will be empty, current_prompt_text will retain its value.
                
                else: # Dialog was cancelled (QDialog.DialogCode.Rejected)
                    print("Area definition cancelled by user.")
                    break # Exit the while loop, area not defined
        
        # else: (no active drawing tool) - no changes needed here
            pass

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


    def handleToolSelected(self, action):
        """Handles the selection of a tool from the QActionGroup."""
        tool_id = action.data() # Get the identifier we stored with setData()
        if not action.isChecked():
            # This can happen if the exclusive group allows unchecking the last item,
            # or if an action is programmatically unchecked.
            # We might want to ensure one tool is always active, or default to "select_area".
            # For now, if something gets unchecked leading to no tool, set current_drawing_tool to None.
            # However, with setExclusive(True), clicking another checkable action will uncheck the previous.
            # If an action is clicked to uncheck itself (if that's allowed by the group), then tool_id would be its ID.
            # A simpler model for exclusive groups is that one is always checked.
            # Let's assume for now that if an action is triggered, it becomes the active tool.
            # The `checked` state is implicitly handled by QActionGroup if another is selected.
            # The main concern is if the user can "unclick" the active tool to have no tool selected.
            # QActionGroup.triggered sends the action that *became* checked.
            pass # The action is now checked, QActionGroup handled unchecking others.

        # If switching away from select tool or to a different tool, clear current selection
        if self.current_drawing_tool == "select_area" and tool_id != "select_area":
            self.pdf_display_label.selected_view_rect = None
            self.pdf_display_label.update() # Repaint to remove highlight

        self.current_drawing_tool = tool_id
        
        if tool_id == "select_area":
            self.info_label.setText("Mode: Select Area. Click on an existing area to select.")
            self.pdf_display_label.setCursor(Qt.CursorShape.ArrowCursor)
            print("Select Area tool active")
        elif tool_id == "text_area":
            self.info_label.setText("Mode: Define Text Area. Click and drag on the PDF.")
            self.pdf_display_label.setCursor(Qt.CursorShape.CrossCursor)
            print("Text Area tool active")
        else:
            self.current_drawing_tool = None # Should not happen with defined setData
            self.info_label.setText("No tool selected. Load a PDF or select a tool.")
            self.pdf_display_label.setCursor(Qt.CursorShape.ArrowCursor)
            print("No tool (or unknown tool) active")

    def setSelectToolActive(self): # Helper to activate select tool programmatically (e.g., on startup)
        self.select_area_action.setChecked(True)
        # handleToolSelected will be called automatically by QActionGroup's triggered signal
        
# Main function remains the same
def main():
    app = QApplication(sys.argv)
    ex = DesignerApp()
    ex.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, # Changed QWidget to QMainWindow
                             QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, 
                             QMessageBox, QScrollArea, QSizePolicy, 
                             QToolBar) # Added QToolBar
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QAction, QIcon # Added QAction, QIcon
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal
import fitz  # PyMuPDF

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
        if event.button() == Qt.MouseButton.LeftButton and self.pixmap() and \
           (self.parent_widget and self.parent_widget.current_drawing_tool is not None):
            self.origin_point = event.pos()
            self.current_rubber_band_rect = QRect(self.origin_point, self.origin_point)
            self.update()

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
        super().paintEvent(event)
        painter = QPainter(self)
        
        # **** CHANGE: Draw only rects for the current page ****
        if self.current_pixmap_page_num is not None:
            rects_for_current_page = self.page_visual_rects.get(self.current_pixmap_page_num, [])
            if rects_for_current_page:
                pen_defined = QPen(Qt.GlobalColor.blue, 1, Qt.PenStyle.SolidLine)
                painter.setPen(pen_defined)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                for rect in rects_for_current_page:
                    painter.drawRect(rect)
            
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

class DesignerApp(QMainWindow): # Changed from QWidget
    def __init__(self):
        super().__init__() # Changed for QMainWindow
        self.pdf_document = None
        self.current_page_num = 0
        self.current_zoom_factor = 1.5
        self.defined_pdf_areas = []
        self.current_drawing_tool = None # To store the active tool, e.g., "text_area"
        self.initUI()

    def initUI(self):
        self.setWindowTitle('SpeedyF Designer')
        self.setGeometry(100, 100, 900, 750) # Adjusted size slightly for toolbar

        # --- Create a Central Widget ---
        # QMainWindow needs a central widget. All your previous main content
        # will go into a layout set on this central widget.
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # --- Main Layout (will be set on the central_widget) ---
        main_layout = QVBoxLayout(central_widget) # Apply layout to central_widget

        # --- Toolbar ---
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar) # Add the toolbar to the QMainWindow

        # Action for defining text areas
        # You can find standard icons using QStyle or provide your own .png files
        # For now, we'll just use text. If you have an icon: QIcon("path/to/icon.png")
        self.define_text_area_action = QAction("Text Area", self) # Text will appear on toolbar if no icon
        self.define_text_area_action.setStatusTip("Define a text input area")
        self.define_text_area_action.setCheckable(True) # Makes it a toggle-able tool
        self.define_text_area_action.triggered.connect(self.setTextAreaTool)
        toolbar.addAction(self.define_text_area_action)
        
        # We'll use an action group later to make tools mutually exclusive
        # self.tool_action_group = QActionGroup(self)
        # self.tool_action_group.addAction(self.define_text_area_action)
        # self.tool_action_group.setExclusive(True)

        # --- Top section for controls (as before, but added to main_layout) ---
        controls_widget = QWidget() 
        controls_layout = QVBoxLayout(controls_widget)

        self.info_label = QLabel('Select a tool, then load a PDF to begin.', self) # Updated info
        controls_layout.addWidget(self.info_label)

        self.load_pdf_button = QPushButton('Load PDF', self)
        self.load_pdf_button.clicked.connect(self.openPdfFile)
        controls_layout.addWidget(self.load_pdf_button)

        nav_layout = QHBoxLayout()
        self.prev_page_button = QPushButton("<< Previous", self)
        # ... (rest of nav_layout setup as before) ...
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

        # PDF Display Area (as before, added to main_layout)
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
        self.pdf_display_label.clear()
        self.pdf_display_label.setText(message)
        self.pdf_display_label.setMinimumSize(self.default_min_display_width, self.default_min_display_height)
        self.pdf_display_label.adjustSize()
        self.pdf_display_label.setCurrentPixmapPage(None) # Reset page context for label
        # Also reset navigation when no PDF is loaded
        self.page_info_label.setText("Page 0 of 0")
        self.prev_page_button.setEnabled(False)
        self.next_page_button.setEnabled(False)

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

            self.pdf_display_label.setPixmap(qpixmap)
            # **** NEW: Tell the label which page this pixmap is for ****
            self.pdf_display_label.setCurrentPixmapPage(page_num) 
            # The setCurrentPixmapPage calls update(), which triggers paintEvent to draw relevant rects.

            self.pdf_display_label.setMinimumSize(qpixmap.width(), qpixmap.height())
            self.pdf_display_label.adjustSize() 

            self.current_page_num = page_num # This must be set before _updateNavigation
            self._updateNavigation()

            if self.scroll_area:
                self.scroll_area.verticalScrollBar().setValue(0)
                self.scroll_area.horizontalScrollBar().setValue(0)
        except Exception as e:
            QMessageBox.critical(self, "Error Displaying Page", f"Could not display page {page_num + 1}: {e}")
            self._reset_pdf_display_label(f"Error displaying page {page_num + 1}")
            self._updateNavigation()

    def handleRectDefined(self, view_qrect):
        if not self.pdf_document or self.pdf_display_label.current_pixmap_page_num is None:
            return # Should not happen if mousePressEvent checks for active tool and pixmap
        
        current_tool_page = self.pdf_display_label.current_pixmap_page_num # Page where rect was drawn

        if self.current_drawing_tool == "text_area":
            inverse_matrix = ~fitz.Matrix(self.current_zoom_factor, self.current_zoom_factor)
            view_fitz_rect = fitz.Rect(view_qrect.x(), view_qrect.y(),
                                       view_qrect.right(), view_qrect.bottom())
            pdf_fitz_rect = view_fitz_rect * inverse_matrix

            area_name = f"TextArea_{len(self.defined_pdf_areas) + 1}" # Temporary naming
            area_prompt = "Enter text here"
            area_type = "text_input"
            
            defined_area_info = {
                'page_num': current_tool_page, # Use the page number where rect was drawn
                'rect_pdf': tuple(pdf_fitz_rect.irect), 
                'name': area_name, 'type': area_type, 'prompt': area_prompt,
            }
            # self.defined_pdf_areas.append(defined_area_info) # After dialog
            print(f"Tool: {self.current_drawing_tool} on Page {current_tool_page + 1}")
            print(f"  View Rect: {view_qrect.x()},{view_qrect.y()},{view_qrect.width()},{view_qrect.height()}")
            print(f"  PDF Coords: {pdf_fitz_rect.irect}")

            # **** CHANGE: Pass current page number to addVisualRect ****
            self.pdf_display_label.addVisualRect(current_tool_page, view_qrect)
            
            # TODO: Open metadata dialog. On OK, add to self.defined_pdf_areas.
            # If dialog is cancelled, we might want a way to remove the last visual rect:
            # self.pdf_display_label.removeLastVisualRectForPage(current_tool_page) -> new method needed in label
        else:
            pass # No tool active, no visual rect added.

    def openPdfFile(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open PDF File", "", 
                                                   "PDF Files (*.pdf);;All Files (*)")
        if file_name:
            if self.pdf_document:
                self.pdf_document.close()
                self.pdf_document = None
            
            self._reset_pdf_display_label() 
            self.defined_pdf_areas = [] 
            self.pdf_display_label.clearDefinedRects() # This now clears the page_visual_rects dictionary
            self._updateNavigation() # Call after resetting, includes resetting page_info_label

            try:
                doc = fitz.open(file_name)
                if not doc.is_pdf:
                    doc.close()
                    QMessageBox.critical(self, "Error", 
                                         f"The selected file '{file_name.split('/')[-1]}' is not a PDF document.")
                    self._reset_pdf_display_label("File is not a PDF. Please select a PDF file.")
                    self._updateNavigation()
                    return

                self.pdf_document = doc
                self.current_page_num = 0 
                self.current_zoom_factor = 1.5
                self.info_label.setText(f"Loaded: {file_name.split('/')[-1]} ({self.pdf_document.page_count} pages)")
                self.displayPdfPage(self.current_page_num) # This calls _updateNavigation and setCurrentPixmapPage

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open or process file: {e}")
                self.pdf_document = None 
                self._reset_pdf_display_label("Failed to load. Please try another file.")
                self._updateNavigation()
        else:
            pass

    def goToPreviousPage(self):
        if self.pdf_document and self.current_page_num > 0:
            self.current_page_num -= 1
            self.displayPdfPage(self.current_page_num)

    def goToNextPage(self):
        if self.pdf_document and self.current_page_num < self.pdf_document.page_count - 1:
            self.current_page_num += 1
            self.displayPdfPage(self.current_page_num)



# Main function remains the same
def main():
    app = QApplication(sys.argv)
    ex = DesignerApp()
    ex.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
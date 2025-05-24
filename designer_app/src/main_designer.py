import sys
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, 
                             QPushButton, QFileDialog, QMessageBox, QScrollArea,
                             QSizePolicy)
from PyQt6.QtGui import QPixmap, QImage                                        # Added QPixmap, QImage
import fitz  # PyMuPDF

class DesignerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.pdf_document = None
        self.current_page_num = 0 # To keep track of the current page later
        self.initUI()

    def initUI(self):
        self.setWindowTitle('SpeedyF Designer')
        self.setGeometry(100, 100, 800, 600)

        main_layout = QVBoxLayout()

        controls_layout = QVBoxLayout()
        self.info_label = QLabel('Load a PDF to begin.', self)
        controls_layout.addWidget(self.info_label)

        self.load_pdf_button = QPushButton('Load PDF', self)
        self.load_pdf_button.clicked.connect(self.openPdfFile)
        controls_layout.addWidget(self.load_pdf_button)

        main_layout.addLayout(controls_layout)

        self.pdf_display_label = QLabel("PDF page will appear here", self)
        self.default_min_display_width = 400 # Store default minimums
        self.default_min_display_height = 300
        self.pdf_display_label.setMinimumSize(self.default_min_display_width, self.default_min_display_height)
        self.pdf_display_label.setStyleSheet("QLabel { background-color : lightgray; border: 1px solid black; }")

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True) # Keep this True for now
        self.scroll_area.setWidget(self.pdf_display_label)

        main_layout.addWidget(self.scroll_area)

        self.setLayout(main_layout)

    # ... (inside DesignerApp class)

    def _reset_pdf_display_label(self, message="PDF page will appear here"):
        """Helper to reset the display label to its default state."""
        self.pdf_display_label.clear() # Clears pixmap
        self.pdf_display_label.setText(message)
        # Reset to default minimum size and allow it to adjust to text
        self.pdf_display_label.setMinimumSize(self.default_min_display_width, self.default_min_display_height)
        self.pdf_display_label.adjustSize()

    def displayPdfPage(self, page_num):
        if not self.pdf_document or page_num < 0 or page_num >= self.pdf_document.page_count:
            self._reset_pdf_display_label("Invalid page number or no PDF loaded.")
            return

        try:
            page = self.pdf_document.load_page(page_num)
            zoom_factor = 1.5 
            mat = fitz.Matrix(zoom_factor, zoom_factor)
            pix = page.get_pixmap(matrix=mat)
            img_format = QImage.Format.Format_RGB888 if pix.alpha == 0 else QImage.Format.Format_RGBA8888
            qimage = QImage(pix.samples, pix.width, pix.height, pix.stride, img_format)
            qpixmap = QPixmap.fromImage(qimage)

            self.pdf_display_label.setPixmap(qpixmap)
            # **** MODIFIED SIZING LOGIC ****
            # Set the minimum size of the label to the pixmap's actual size
            self.pdf_display_label.setMinimumSize(qpixmap.width(), qpixmap.height())
            # Then call adjustSize. With widgetResizable=True on scrollArea, 
            # this *should* make the label want to be this big.
            self.pdf_display_label.adjustSize() 

            self.current_page_num = page_num
            self.info_label.setText(f"Displaying page {page_num + 1} of {self.pdf_document.page_count} "
                                    f"({self.pdf_document.name.split('/')[-1]})")

        except Exception as e:
            QMessageBox.critical(self, "Error Displaying Page", f"Could not display page {page_num + 1}: {e}")
            self._reset_pdf_display_label(f"Error displaying page {page_num + 1}")

    def openPdfFile(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open PDF File", "", 
                                                "PDF Files (*.pdf);;All Files (*)")

        if file_name:
            if self.pdf_document:
                self.pdf_document.close()
                self.pdf_document = None
            self._reset_pdf_display_label() # Reset before loading new

            try:
                doc = fitz.open(file_name)
                if not doc.is_pdf:
                    doc.close()
                    QMessageBox.critical(self, "Error", 
                                        f"The selected file '{file_name.split('/')[-1]}' is not a PDF document.")
                    self._reset_pdf_display_label("File is not a PDF. Please select a PDF file.")
                    return

                self.pdf_document = doc
                self.info_label.setText(f"Loaded: {file_name.split('/')[-1]} ({self.pdf_document.page_count} pages)")
                self.displayPdfPage(0)

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open or process file: {e}")
                self.pdf_document = None # Ensure it's None
                self._reset_pdf_display_label("Failed to load. Please try another file.")
        # No 'else' needed here for resetting label if already handled by _reset_pdf_display_label

def main():
    app = QApplication(sys.argv)
    ex = DesignerApp()
    ex.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
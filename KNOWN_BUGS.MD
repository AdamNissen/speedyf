# SpeedyF - Known Bugs & Issues
This document lists known bugs, visual glitches, and issues in the SpeedyF application.

## Current Known Issues
1. PDF Display Does Not Clear on "New Project" (Windows)
* ID: KB001

* Date Reported: 2025-05-28

* Severity: Minor (Visual Glitch)

* Status: Open / To Be Investigated Further

* Affected Component: DesignerApp - PDF Display Area (InteractivePdfLabel within QScrollArea)

* Environment:

    * Operating System: Windows [User to specify their Windows version, e.g., Windows 11 Pro 23H2]

    * Python Version: [User to specify their Python version, e.g., 3.11.4]

    * PyQt6 Version: [User to specify their PyQt6 version, e.g., 6.6.1]

* Description:
    When a PDF file is loaded and its first page is displayed, and then the user selects "File > New Project", the image of the previously loaded PDF page remains visually persistent in the main display area. Other UI elements (defined area rectangles, info labels, page navigation, menu item states) reset correctly as expected. The display area should clear and revert to its placeholder text (e.g., "Load a PDF to begin a new project.").

* Steps to Reproduce:

    1. Launch SpeedyF Designer application.

    2. Click "Load PDF" and select a valid PDF file. Observe the first page displayed.

    3. Go to "File > New Project".

    4. Observed Behavior: The image of the previously loaded PDF page remains visible in the display area.

    5. Expected Behavior: The PDF image should be cleared from the display area, and the placeholder text (e.g., "Load a PDF to begin a new project.") should be shown.

* Fixes Attempted (Unsuccessful):

    * pdf_display_label.clear()

    * pdf_display_label.setPixmap(QPixmap()) followed by pdf_display_label.setText(...)

    * pdf_display_label.adjustSize()
 
    * scroll_area.viewport().update()

    * pdf_display_label.hide() followed by pdf_display_label.show()

* Workaround:
    Loading a new PDF after selecting "New Project" will correctly replace the old, persistent image with the new PDF's content. The underlying data model is correctly reset by "New Project".

* Notes:
    This appears to be a visual refresh issue specific to the QLabel holding the pixmap, possibly in interaction with the QScrollArea or its viewport, when attempting to revert from displaying a large pixmap to displaying text. The data and application state are correctly reset.

(More bugs can be added here as they are discovered)


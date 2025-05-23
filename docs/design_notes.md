# SpeedyF - Design & Development Notes

This document outlines the development workflow and repository structure for the SpeedyF project.

## Table of Contents

1.  [Development Workflow](#development-workflow)
    * [Phase 0: Foundation & Setup](#phase-0-foundation--setup-week-0-1)
    * [Phase 1: PDF Display & Area Definition (Designer)](#phase-1-pdf-display--area-definition-designer---weeks-1-3)
    * [Phase 2: Core Filler App & Basic Export](#phase-2-core-filler-app--basic-export-weeks-3-5)
    * [Phase 3: Expanding Field Types (Designer & Filler)](#phase-3-expanding-field-types-designer--filler---weeks-5-8)
    * [Phase 4: Simple Rule Engine (Conditional Logic)](#phase-4-simple-rule-engine-conditional-logic---weeks-8-10-if-in-v1x)
    * [Phase 5: UI/UX Refinement, Error Handling & Documentation](#phase-5-uiux-refinement-error-handling--documentation-weeks-10-12)
    * [Phase 6: Final Testing, Packaging & Release Prep](#phase-6-final-testing-packaging--release-prep-week-12-13)
    * [Recurring Activities](#recurring-activities-throughout-all-phases)
2.  [Repository Structure](#repository-structure)

---

## Development Workflow

This workflow emphasizes building core functionality first, then incrementally adding features, with continuous testing and integration.

### Phase 0: Foundation & Setup (Week 0-1)

1.  **Project Initialization:**
    * **Version Control:** Initialize a Git repository. Create `main` and `develop` branches. Use feature branches for new work (e.g., `feature/pdf-display`).
    * **Repository Structure:** Set up the directory structure (see [Repository Structure](#repository-structure) below).
    * **Virtual Environments:** Create separate Python virtual environments for `designer_app` and `exported_program_template`.
    * **`.gitignore`:** Add a comprehensive `.gitignore` file.
2.  **Core Dependency Installation & Prototyping:**
    * Install core libraries: PyQt6/PySide6, PyMuPDF for `designer_app`; PyMuPDF, Pillow for `exported_program_template`.
    * **"Hello World" GUIs:** Minimal PyQt window (designer) & Tkinter window (filler).
3.  **Basic Packaging Test:**
    * Use `PyInstaller` to package "Hello World" versions for Windows & macOS.
    * Create initial build scripts.

### Phase 1: PDF Display & Area Definition (Designer - Weeks 1-3)

* **Feature: PDF Loading & Rendering (Designer)**
    * UI for PDF selection.
    * PyMuPDF to render pages in PyQt GUI.
    * Page navigation.
* **Feature: Visual Area Selection (Designer)**
    * Click-and-drag rectangle drawing on rendered PDF.
    * Capture coordinates; visually indicate selection.
* **Feature: Basic Area Metadata (Designer)**
    * Dialog for Field Name/ID, Prompt, Field Type (initially "Text Input").
* **Feature: Project Save/Load (Designer)**
    * Define JSON format for project data (PDF paths, area definitions).
    * Implement "Save Project" and "Open Project".

### Phase 2: Core Filler App & Basic Export (Weeks 3-5)

* **Feature: Filler App - Load Configuration & Display Prompts (Exported Program Template)**
    * Tkinter app loads JSON project file.
    * Iterate "Text Input" fields: display Prompt, provide `Entry` widget.
    * Implement "Next," "Previous," "Skip" buttons.
* **Feature: Filler App - Data Collection (Exported Program Template)**
    * Store user's text input.
* **Feature: PDF Generation with Text Input (Exported Program Template)**
    * On "Save," use PyMuPDF:
        * Open a *copy* of the original PDF.
        * Write collected text at stored coordinates.
        * Prompt user to save new filled PDF.
* **Feature: Basic Export Functionality (Designer)**
    * "Export Filler Program" button:
        * Copy `exported_program_template` source.
        * Copy project JSON & original PDF(s).
        * Run `PyInstaller` on `main_filler.py` to create executable.
* **End-to-End Test:** Design, export, run filler, check output PDF.

### Phase 3: Expanding Field Types (Designer & Filler - Weeks 5-8)

* Iteratively add support for each new field type:
    1.  **Static Pre-defined Text:** Designer UI, JSON update; Filler renders text.
    2.  **Signature/Initial Areas (Mouse Drawing):** Designer UI, JSON update; Filler uses Tkinter `Canvas`, saves drawing as image, PyMuPDF places image.
    3.  **Simple Drawings (Highlights, Markers):** Designer tools (shapes, color/size), JSON update; Filler draws using PyMuPDF.
    4.  **User-Selected Pre-defined Text (Dropdowns):** Designer UI (options), JSON update; Filler uses Tkinter `OptionMenu`/`ttk.Combobox`, writes selection.
* **Testing:** Test each field type end-to-end.

### Phase 4: Simple Rule Engine (Conditional Logic - Weeks 8-10, if in v1.x)

* **Feature: Rule Definition (Designer)**
    * UI for "control variable" (e.g., `client_type`).
    * UI to link elements to conditions (e.g., "Show if `client_type` is 'Rental'").
    * Store rules in JSON.
* **Feature: Rule Implementation (Filler)**
    * Prompt for control variable(s) on startup.
    * Parse rules; conditionally display/skip fields or apply highlights.
* **Testing:** Test various rule combinations.

### Phase 5: UI/UX Refinement, Error Handling & Documentation (Weeks 10-12)

* **UI/UX Polish (Both Apps):** Layouts, icons, tooltips, consistent styling, progress indicators.
* **Error Handling (Both Apps):** Robust handling (file not found, invalid PDF), user-friendly messages.
* **Documentation:** User Guides (Designer & Filler), code comments, project READMEs.
* **Cross-Platform Testing:** Rigorous testing on Windows & macOS.

### Phase 6: Final Testing, Packaging & Release Prep (Week 12-13)

* **Comprehensive Testing:** Unit tests, integration tests, User Acceptance Testing (UAT).
* **Finalize Packaging:** Optimize PyInstaller scripts; consider installers (DMG, Inno Setup).
* **Code Freeze & Release Candidate.**

### Recurring Activities (Throughout All Phases)

* **Version Control:** Commit regularly, use feature branches, merge to `develop`, then `main`.
* **Issue Tracking:** Use GitHub Issues or similar.
* **Code Reviews (if applicable).**
* **Regular Builds:** Build and test on Windows & macOS frequently.

---

## Repository Structure

speedyf/
├── designer_app/                 # Source code for the SpeedyF Designer application
│   ├── src/
│   │   ├── main_designer.py      # Main application entry point for designer
│   │   ├── ui/                   # GUI elements (designer: windows, dialogs)
│   │   ├── core/                 # Core logic (PDF handling, project saving/loading - designer)
│   │   └── assets_designer/      # Icons, images, etc. for the designer
│   ├── tests_designer/           # Unit/integration tests for the designer
│   ├── requirements_designer.txt # Python dependencies for the designer
│   └── README_designer.md        # Specific README for the designer app
│
├── exported_program_template/    # Template/core for the exported SpeedyF filler program
│   ├── src/
│   │   ├── main_filler.py        # Main script for the exported filler application
│   │   ├── pdf_operations.py     # PyMuPDF logic for writing data onto the PDF
│   │   ├── ui_filler.py          # Tkinter UI elements (dialogs, drawing canvas) for filler
│   │   └── assets_filler/        # Any assets needed by the filler (e.g., 'X' image)
│   ├── requirements_filler.txt   # Dependencies for the exported program (PyMuPDF, Pillow)
│   └── README_filler.md          # Specific README for the filler program template
│
├── docs/                         # Project documentation
│   ├── user_guide_designer.md
│   ├── user_guide_filler.md
│   ├── design_notes.md           # This file
│   └── technical_overview.md
│
├── examples/                     # Example projects created with SpeedyF
│   ├── rental_agreement/
│   │   ├── rental_agreement.pdf
│   │   └── rental_agreement_config.json # Example SpeedyF project file
│   └── ...
│
├── scripts/                      # Helper scripts (e.g., for building, packaging)
│   ├── build_designer_win.bat
│   ├── build_designer_mac.sh
│   ├── package_filler_win.bat    # Script used by PyInstaller for the filler
│   └── package_filler_mac.sh
│
├── .gitignore
├── LICENSE                       # Project License (To Be Determined)
└── README.md                     # Main project README (overview, setup for dev)
---
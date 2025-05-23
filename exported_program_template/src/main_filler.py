import tkinter as tk
from tkinter import ttk

class FillerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SpeedyF Filler - Hello World")
        self.root.geometry("300x150") # width x height

        # Create a style object for ttk widgets if you plan to use them
        # style = ttk.Style()
        # style.theme_use('clam') # Example theme, others: default, alt, classic

        main_frame = ttk.Frame(root, padding="20 20 20 20")
        main_frame.pack(expand=True, fill='both')

        label = ttk.Label(main_frame, text="Hello from SpeedyF Filler!")
        label.pack(padx=10, pady=10)

        # Example button
        # close_button = ttk.Button(main_frame, text="Close", command=root.destroy)
        # close_button.pack(pady=10)

def main():
    root = tk.Tk()
    app = FillerApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()
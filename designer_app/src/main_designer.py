import sys
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout

class DesignerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('SpeedyF Designer - Hello World')
        self.setGeometry(300, 300, 300, 150)  # x, y, width, height

        layout = QVBoxLayout()
        label = QLabel('Hello from SpeedyF Designer!', self)
        layout.addWidget(label)
        self.setLayout(layout)

def main():
    app = QApplication(sys.argv)
    ex = DesignerApp()
    ex.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
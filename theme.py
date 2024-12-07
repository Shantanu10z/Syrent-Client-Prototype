# theme.py

# Dark theme stylesheet
dark_stylesheet = """
QMainWindow, QDialog, QWidget {
    background-color: #121212;
    color: #FFFFFF;
}

QToolBar {
    background-color: #1F1F1F;
    spacing: 6px;
}

QToolButton {
    background-color: #333333;
    color: #FFFFFF;
    border: none;
    padding: 4px;
}

QToolButton:hover {
    background-color: #555555;
}

QLabel {
    color: #E0E0E0;
}

QProgressBar {
    background-color: #333333;
    color: #FFFFFF;
    border: 1px solid #555555;
    border-radius: 5px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #4CAF50;  /* Green color for progress */
}

QLineEdit, QPlainTextEdit, QTextEdit {
    background-color: #333333;
    color: #FFFFFF;
    border: 1px solid #555555;
    padding: 4px;
    border-radius: 5px;
}

QMenuBar {
    background-color: #1F1F1F;
    color: #E0E0E0;
}

QMenuBar::item:selected {
    background-color: #333333;
}

QMenu {
    background-color: #1F1F1F;
    color: #E0E0E0;
    border: 1px solid #333333;
}

QMenu::item:selected {
    background-color: #333333;
}

QScrollBar:vertical, QScrollBar:horizontal {
    background-color: #333333;
    width: 12px;
}

QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background-color: #555555;
    border-radius: 5px;
}

QScrollBar::add-line, QScrollBar::sub-line {
    background-color: #333333;
    height: 0px;
    width: 0px;
}
"""

# Light theme stylesheet
light_stylesheet = """
QMainWindow, QDialog, QWidget {
    background-color: #FFFFFF;
    color: #000000;
}

QToolBar {
    background-color: #E0E0E0;
    spacing: 6px;
}

QToolButton {
    background-color: #F5F5F5;
    color: #000000;
    border: none;
    padding: 4px;
}

QToolButton:hover {
    background-color: #CCCCCC;
}

QLabel {
    color: #000000;
}

QProgressBar {
    background-color: #CCCCCC;
    color: #000000;
    border: 1px solid #AAAAAA;
    border-radius: 5px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #4CAF50;  /* Green color for progress */
}

QLineEdit, QPlainTextEdit, QTextEdit {
    background-color: #FFFFFF;
    color: #000000;
    border: 1px solid #AAAAAA;
    padding: 4px;
    border-radius: 5px;
}

QMenuBar {
    background-color: #E0E0E0;
    color: #000000;
}

QMenuBar::item:selected {
    background-color: #CCCCCC;
}

QMenu {
    background-color: #FFFFFF;
    color: #000000;
    border: 1px solid #AAAAAA;
}

QMenu::item:selected {
    background-color: #CCCCCC;
}

QScrollBar:vertical, QScrollBar:horizontal {
    background-color: #E0E0E0;
    width: 12px;
}

QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background-color: #AAAAAA;
    border-radius: 5px;
}

QScrollBar::add-line, QScrollBar::sub-line {
    background-color: #E0E0E0;
    height: 0px;
    width: 0px;
}
"""

# Utility function to get the appropriate stylesheet based on theme
def get_stylesheet(dark_mode: bool) -> str:
    return dark_stylesheet if dark_mode else light_stylesheet

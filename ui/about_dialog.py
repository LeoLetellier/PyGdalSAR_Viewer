import os

from qgis.PyQt import QtWidgets, uic

# Read the ui file
FORM_CLASS, BASE_CLASS = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "about_dialog.ui")
)


class AboutDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        # Link the button
        self.buttonBox.accepted.connect(self.accept)

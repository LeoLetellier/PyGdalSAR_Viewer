from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDockWidget, QLabel, QVBoxLayout, QWidget


class PygdalsarViewerSection(QDockWidget):
    """A dummy dock widget as a placeholder."""

    def __init__(self, parent=None):
        super().__init__("Placeholder: Future Widget", parent)

        # Create a central widget with minimal height
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(4, 4, 4, 4)  # Minimal margins

        # Add a label
        label = QLabel("This is a placeholder for a future widget.")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 12px; color: #666;")
        layout.addWidget(label)

        # Set the central widget
        self.setWidget(central_widget)
        self.setMinimumHeight(30)  # Minimal height
        self.setMaximumHeight(50)  # Prevent vertical expansion

    def closeEvent(self, event):
        """Emit the closingPlugin signal when the dock widget is closed."""
        self.closingPlugin.emit()
        super().closeEvent(event)

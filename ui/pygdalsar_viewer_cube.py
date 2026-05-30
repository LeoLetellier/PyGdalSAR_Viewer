import os
from datetime import datetime

from numpy import loadtxt
from qgis.core import QgsMapLayerProxyModel
from qgis.PyQt import QtGui, QtWidgets, uic
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QLabel

from ..tools.band_switch_tool import BandSwitchTool

# Load the UI file
FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "pygdalsar_viewer_cube.ui")
)


class PygdalsarViewerCube(QtWidgets.QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(PygdalsarViewerCube, self).__init__(parent)
        self.setupUi(self)

        # Initialize the band switch tool
        self._band_switch_tool = BandSwitchTool()
        self._connecting = False

        # Dates and file handling
        self.loaded_dates = []
        self.is_file_valid = True
        self.is_file_length_ok = False
        self.label_mode = "band index"  # Default mode

        # Populate label mode combo box
        self.band_label_mode.addItems(["band index", "band description", "file label"])

        # Connect signals
        self._connect_signals()

        # Initialize UI
        self._reset_ui()

        # Flag to track resize connection
        self._resize_connection = False

    def _connect_signals(self):
        """Connect all signals to slots."""
        self.layerCombo.layerChanged.connect(self._on_layer_changed)
        self.bandSlider.valueChanged.connect(self._on_slider_moved)
        self.filewidget_date.fileChanged.connect(self._on_file_selected)
        self.band_label_mode.currentTextChanged.connect(self._on_label_mode_change)

    def _on_label_mode_change(self, mode):
        """Update label mode and refresh current label."""
        self.label_mode = mode
        self.filewidget_date.setEnabled(self.label_mode == "file label")
        self._refresh_labels(self.bandSlider.value() - 1)

    def _on_layer_changed(self, layer):
        """Handle layer changes."""
        self._band_switch_tool.set_layer(layer)
        info = self._band_switch_tool.layer_info()

        if info is None:
            self._reset_ui()
            return

        self._connecting = True
        self.bandSlider.setMinimum(1)
        self.bandSlider.setMaximum(info["band_count"])
        self.bandSlider.setValue(1)  # Reset slider to band 1
        self._connecting = False

        # Enable/disable file widget based on label mode
        self.filewidget_date.setEnabled(self.label_mode == "file label")

    def _on_slider_moved(self, index: int):
        """Handle slider movement."""
        if self._connecting:
            return
        band = index  # Slider value is already 1-based
        self._band_switch_tool.switch_band(band)
        self._refresh_labels(index - 1)  # Convert to 0-based for labels

    def _on_file_selected(self, file_path):
        """Handle file selection for external dates."""
        if not os.path.exists(file_path):
            self.is_file_valid = False
            self.is_file_length_ok = False
            print(f"File not found: {file_path}")
            self.filewidget_date.setEnabled(self.label_mode == "file label")
            return

        try:
            with open(file_path, "r") as f:
                self.loaded_dates = [
                    line.strip() for line in f.readlines() if line.strip()
                ]

            self.is_file_valid = True
            info = self._band_switch_tool.layer_info()
            if len(self.loaded_dates) != info["band_count"]:
                self.is_file_length_ok = False
            else:
                self.is_file_length_ok = True
                self._band_switch_tool.set_dates(self.loaded_dates)
                # Force refresh with the current slider value (1-based)
                self._refresh_labels(self.bandSlider.value() - 1)
        except Exception as e:
            self.is_file_valid = False
            self.is_file_length_ok = False
            print(f"Error loading file: {e}")
        finally:
            self.filewidget_date.setEnabled(self.label_mode == "file label")

    def _refresh_labels(self, index: int):
        """Update band info and current date label."""
        info = self._band_switch_tool.layer_info()
        if info is None:
            return

        band = index + 1  # Convert to 1-based for display

        # Determine the label to display
        if self.label_mode == "file label":
            if self.is_file_length_ok and index < len(self.loaded_dates):
                date_str = self.loaded_dates[index]
                self.band_info.setText(f"Band info: {date_str}")
            else:
                # Fallback to band index if file is not valid or not loaded
                self.band_info.setText(f"Band info: band {band} / {info['band_count']}")
        elif self.label_mode == "band index":
            self.band_info.setText(f"Band info: band {band} / {info['band_count']}")
        elif self.label_mode == "band description":
            band_desc = (
                self._band_switch_tool._layer.bandName(band)
                if self._band_switch_tool._layer
                else "—"
            )
            self.band_info.setText(f"Band info: {band_desc}")
        else:
            date_str = (
                info["dates"][index]
                if info["dates"] and index < len(info["dates"])
                else "—"
            )
            self.band_info.setText(
                f"Band info: band {band} / {info['band_count']} - {date_str}"
            )

    def _reset_ui(self):
        """Reset the UI to its initial state."""
        self.bandSlider.setMinimum(1)
        self.bandSlider.setMaximum(1)
        self.band_info.setText("Band info: select a raster to begin")

    def closeEvent(self, event):
        """Clean up when the dock widget is closed."""
        self._band_switch_tool.cleanup()
        self.closingPlugin.emit()
        event.accept()

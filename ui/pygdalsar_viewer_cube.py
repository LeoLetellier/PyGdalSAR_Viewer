import os

from qgis.PyQt import QtGui, QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal

from ..tools.band_switch_tool import BandSwitchTool

# Read the ui file
FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "pygdalsar_viewer_cube.ui")
)


class PygdalsarViewerCube(QtWidgets.QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(PygdalsarViewerCube, self).__init__(parent)
        # Setup ui widgets as attributes
        self.setupUi(self)

        # Init the tool
        self._tool = BandSwitchTool()

        self._connecting = False
        self._connect_signals()

    def _connect_signals(self):
        # React when selecting a layer or using the slider
        self.layerCombo.layerChanged.connect(self._on_layer_changed)
        self.bandSlider.valueChanged.connect(self._on_slider_moved)

    def _on_layer_changed(self, layer):
        """Called whenever the user picks a different layer in the combo"""
        self._tool.set_layer(layer)
        info = self._tool.layer_info()

        if info is None:
            self._reset_ui()
            return

        self._connecting = True
        # Slider is being initialized
        self.bandSlider.setMinimum(0)
        self.bandSlider.setMaximum(info["band_count"] - 1)
        self.bandSlider.setValue(info["current_band"] - 1)
        self._connecting = False

        self._refresh_labels(info["current_band"] - 1)

    def _on_slider_moved(self, index: int):
        """index is 0-based; band is index+1"""
        if self._connecting:
            # Don't update the map when a layer is being selected
            return
        band = index + 1
        self._tool.switch_band(band)
        self._refresh_labels(index)

    def _refresh_labels(self, index: int):
        info = self._tool.layer_info()
        if info is None:
            return
        band = index + 1
        date_str = info["dates"][index] if info["dates"] else "—"
        self.dateValueLabel.setText(date_str)
        self.bandValueLabel.setText(f"Band {band} / {info['band_count']}")

    def _reset_ui(self):
        self.bandSlider.setMinimum(0)
        self.bandSlider.setMaximum(0)
        self.dateValueLabel.setText("—")
        self.bandValueLabel.setText("Band — / —")
        self._dateAxis.setLabels([])

    def closeEvent(self, event):
        self._tool.cleanup()
        self.closingPlugin.emit()
        event.accept()

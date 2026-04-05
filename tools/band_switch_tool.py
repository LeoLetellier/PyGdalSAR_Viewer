from datetime import datetime
from typing import Optional

from qgis.core import (
    QgsContrastEnhancement,
    QgsMapLayer,
    QgsMultiBandColorRenderer,
    QgsProject,
    QgsRasterLayer,
    QgsRasterRenderer,
    QgsSingleBandGrayRenderer,
    QgsSingleBandPseudoColorRenderer,
)
from qgis.PyQt.QtCore import QDate


# ── public type ───────────────────────────────────────────────────────────────
class LayerInfo:
    """Snapshot of the layer state exposed to the UI."""

    __slots__ = ("band_count", "current_band", "dates")

    def __init__(self, band_count: int, current_band: int, dates: list[str]):
        self.band_count = band_count
        self.current_band = current_band
        self.dates = dates  # len == band_count, ISO strings or band names


# ── tool ──────────────────────────────────────────────────────────────────────
class BandSwitchTool:
    """
    Manages band switching for one raster layer at a time.

    Date list
    ---------
    Dates are discovered in this priority order:
      1. Explicitly set via set_dates()
      2. Band description strings that parse as dates (ISO 8601 or YYYYMMDD)
      3. Fallback : "Band N"
    """

    def __init__(self):
        self._layer: Optional[QgsRasterLayer] = None
        self._dates: list[str] = []  # user-supplied dates
        self._resolved_dates: list[str] = []  # final list used by the UI

    # ── public API ────────────────────────────────────────────────────────────

    def set_layer(self, layer: Optional[QgsMapLayer]):
        """Attach a new raster layer. Pass None to detach."""
        if layer is None or layer.type() != QgsMapLayer.RasterLayer:
            self._layer = None
            self._resolved_dates = []
            return
        self._layer = layer
        self._resolve_dates()

    def set_dates(self, dates: list[str]):
        """
        Provide an explicit date list (one entry per band).
        Call this *after* set_layer() if your dates come from an external source
        (CSV side-car, NetCDF metadata, …).
        """
        self._dates = list(dates)
        if self._layer is not None:
            self._resolve_dates()

    def layer_info(self) -> Optional[dict]:
        """Return a plain dict consumed by the UI, or None if no valid layer."""
        if self._layer is None:
            return None
        return {
            "band_count": self._layer.bandCount(),
            "current_band": self._current_band(),
            "dates": list(self._resolved_dates),
        }

    def switch_band(self, band: int):
        """
        Switch the displayed band to `band` (1-based).
        Preserves the renderer type and all its settings (contrast, color ramp…).
        Only the band index is mutated.
        """
        if self._layer is None:
            return
        band = max(1, min(band, self._layer.bandCount()))
        renderer = self._layer.renderer()
        if renderer is None:
            return

        rtype = renderer.type()

        if rtype == "singlebandgray":
            self._switch_singleband_gray(renderer, band)
        elif rtype == "singlebandpseudocolor":
            self._switch_singleband_pseudo(renderer, band)
        elif rtype == "multibandcolor":
            # For multiband we only update the first (gray/red) band by default.
            # Extend here if your use-case needs all three.
            self._switch_multiband(renderer, band)
        else:
            # Paletted, hillshade, etc. — best-effort: do nothing
            return

        self._layer.triggerRepaint()

    def cleanup(self):
        """Call when the dock is closed."""
        self._layer = None
        self._dates = []
        self._resolved_dates = []

    # ── private : renderer mutation ───────────────────────────────────────────

    @staticmethod
    def _switch_singleband_gray(renderer: QgsSingleBandGrayRenderer, band: int):
        """Clone contrast enhancement to new band, leave everything else."""
        old_ce = renderer.contrastEnhancement()
        new_ce = QgsContrastEnhancement(renderer.dataType(band))
        if old_ce is not None:
            new_ce.setContrastEnhancementAlgorithm(
                old_ce.contrastEnhancementAlgorithm(), False
            )
            new_ce.setMinimumValue(old_ce.minimumValue(), False)
            new_ce.setMaximumValue(old_ce.maximumValue())
        renderer.setGrayBand(band)
        renderer.setContrastEnhancement(new_ce)

    @staticmethod
    def _switch_singleband_pseudo(
        renderer: QgsSingleBandPseudoColorRenderer, band: int
    ):
        renderer.setBand(band)

    @staticmethod
    def _switch_multiband(renderer: QgsMultiBandColorRenderer, band: int):
        """Update red band only; green/blue stay untouched."""
        renderer.setRedBand(band)

    # ── private : current band detection ─────────────────────────────────────

    def _current_band(self) -> int:
        renderer = self._layer.renderer()
        if renderer is None:
            return 1
        rtype = renderer.type()
        if rtype == "singlebandgray":
            return renderer.grayBand()
        if rtype == "singlebandpseudocolor":
            return renderer.band()
        if rtype == "multibandcolor":
            return renderer.redBand()
        return 1

    # ── private : date resolution ─────────────────────────────────────────────

    def _resolve_dates(self):
        if self._layer is None:
            self._resolved_dates = []
            return

        n = self._layer.bandCount()

        # 1. User-supplied list
        if len(self._dates) == n:
            self._resolved_dates = list(self._dates)
            return

        # 2. Try to parse band descriptions
        parsed = []
        for i in range(1, n + 1):
            desc = self._layer.bandName(i)  # e.g. "2021-03-15" or "Band 1"
            date = _try_parse_date(desc)
            parsed.append(date if date else desc)

        self._resolved_dates = parsed

    # ── static helpers ────────────────────────────────────────────────────────

    @staticmethod
    def build_dates_from_filenames(paths: list[str]) -> list[str]:
        """
        Convenience: given a list of file paths, try to extract ISO dates
        from filenames. Useful when the stack was built from a folder of
        single-band GeoTIFFs named e.g. '20210315_VV.tif'.
        Returns a list of date strings (or original basenames on failure).
        """
        result = []
        for p in paths:
            base = p.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            stem = base.split(".")[0]
            date = _try_parse_date(stem)
            result.append(date if date else stem)
        return result


# ── module-level helpers ──────────────────────────────────────────────────────

_DATE_FORMATS = [
    "%Y-%m-%d",  # ISO 8601
    "%Y%m%d",  # compact
    "%d/%m/%Y",
    "%m/%d/%Y",
]


def _try_parse_date(s: str) -> Optional[str]:
    """Try several formats; return ISO string or None."""
    # Strip non-date prefix/suffix (e.g. "Band_20210315_VV")
    import re

    m = re.search(r"(\d{4}[-/]\d{2}[-/]\d{2}|\d{8})", s)
    token = m.group(0) if m else s.strip()
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(token, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None

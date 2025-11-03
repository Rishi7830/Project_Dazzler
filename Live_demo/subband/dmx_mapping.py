# dmx_mapping.py
import time
import numpy as np

# Assume your existing pyserial_dmx provides these:
from pyserial_dmx import SimpleDMX, CH_RED, CH_GREEN, CH_BLUE, CH_DIMMER, CH_STROBE

class LightingMapper:
    def __init__(self, dmx_port):
        self.dmx = SimpleDMX(port=dmx_port)
        self.base_dimmer = 128
        self.flash_env = 0.0
        self.flash_decay = 0.85
        self.thud_env = 0.0
        self.thud_decay = 0.90
        self.palette = [
            (255, 60, 60),
            (60, 255, 120),
            (60, 120, 255),
            (255, 200, 60),
            (180, 60, 255),
        ]
        self.color_idx = 0
        self.last_update = time.time()

    def start(self):
        self.dmx.start_broadcast()

    def stop(self):
        self.dmx.close()

    def _set_rgb(self, rgb):
        r, g, b = [int(np.clip(c, 0, 255)) for c in rgb]
        self.dmx.set_channel_internal(CH_RED, r)
        self.dmx.set_channel_internal(CH_GREEN, g)
        self.dmx.set_channel_internal(CH_BLUE, b)

    def _apply_envelopes(self):
        # Decay envelopes per frame
        self.flash_env *= self.flash_decay
        self.thud_env *= self.thud_decay

    def update_from_bands(self, onsets, intensities):
        # Call each audio block; manage short envelopes for smoothness
        self._apply_envelopes()

        # Low band: small thud on dimmer
        if onsets.get('low', False):
            self.thud_env += min(40 + int(intensities['low'] * 0.5), 80)  # modest bump
        dimmer = int(np.clip(self.base_dimmer + self.thud_env, 0, 255))
        self.dmx.set_channel_internal(CH_DIMMER, dimmer)

        # Mid band: change color on tom/snare
        if onsets.get('mid', False):
            self.color_idx = (self.color_idx + 1) % len(self.palette)
        self._set_rgb(self.palette[self.color_idx])

        # High band: crash flash using strobe or dimmer spike
        if onsets.get('high', False):
            self.flash_env = max(self.flash_env, min(255, int(120 + intensities['high'] * 0.8)))
        flash_level = int(np.clip(self.flash_env, 0, 255))

        # If fixture has strobe, use it; else add to dimmer briefly
        try:
            self.dmx.set_channel_internal(CH_STROBE, flash_level)  # optional channel
        except Exception:
            self.dmx.set_channel_internal(CH_DIMMER, int(np.clip(dimmer + flash_level, 0, 255)))

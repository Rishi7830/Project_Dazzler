# dazzler_subband_main.py
import time
import signal
import sys

from audio_preprocessor import AudioPreprocessor
from subband_onset import SubBandOnsetDetector
from dmx_mapping import LightingMapper

DMX_PORT = "COM14"  # set to your USB/tty DMX adapter port
AUDIO_DEVICE_ID = None  # None uses default input device

shutdown_flag = False
def signal_handler(sig, frame):
    global shutdown_flag
    if not shutdown_flag:
        print("\nShutting down...")
        shutdown_flag = True

def main():
    signal.signal(signal.SIGINT, signal_handler)
    print("=== Dazzler Sub-Band Real-Time Pipeline ===")

    # Initialize components
    pre = AudioPreprocessor(sample_rate=44100, block_size=1024, target_rms_db=-18.0, device=AUDIO_DEVICE_ID)
    det = SubBandOnsetDetector(
        sample_rate=44100,
        frame_size=1024,
        hop_size=1024,
        low_band=(20, 500),
        mid_band=(500, 2000),
        high_band=(2000, 20000),
        perc_window_sec=8.0,
        percentile=90.0,
        min_space_sec=0.12,
        smooth_tau_sec=0.12,
    )
    light = LightingMapper(dmx_port=DMX_PORT)

    # Start
    pre.start()
    light.start()
    print("Pipeline running. Play audio into the mixer input; press Ctrl+C to stop.")

    try:
        while not shutdown_flag:
            chunk = pre.get_normalized_chunk()
            if chunk is None or len(chunk) == 0:
                time.sleep(0.005)
                continue

            onsets, intensities, nov, thr = det.process(chunk)
            light.update_from_bands(onsets, intensities)

            # Optional console diagnostics
            if any(onsets.values()):
                print(f"[Onsets] low={onsets['low']}, mid={onsets['mid']}, high={onsets['high']} | "
                      f"int(low)={intensities['low']:.1f} int(mid)={intensities['mid']:.1f} int(high)={intensities['high']:.1f}")

            time.sleep(0.002)
    finally:
        light.stop()
        pre.stop()
        print("=== Pipeline stopped ===")

if __name__ == "__main__":
    main()

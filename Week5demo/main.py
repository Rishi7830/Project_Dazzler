"""
Main Audio Processing Pipeline
Orchestrates parallel processing of audio features for real-time lighting control
(Edited to integrate DMX via pyserial.SimpleDMX and keep original feature extraction)
"""
import os
import sys
import platform
import librosa
import numpy as np
import time
from multiprocessing import Pool
from pathlib import Path

# Import project modules
from tempo_detection import detect_tempo
from loudness_detection import detect_loudness
from mode_key_detection import detect_mode_key
from audio_analyzer import process_audio_features
from color_mapper import map_to_colors

# Try to import the DMX controller wrapper from local pyserial.py
# This expects a class SimpleDMX(port: str, num_channels: int)
try:
    from pyserial import SimpleDMX  # local module that wraps pySerial
except Exception as e:
    SimpleDMX = None
    print(f"[DMX] pyserial.SimpleDMX unavailable: {e}")

# ----------------------
# DMX helpers
# ----------------------

def _suggest_default_port() -> str:
    """Suggest a default serial device path based on platform.
    Windows uses COM ports (e.g., 'COM3'), macOS often '/dev/tty.usbserial*',
    Linux/WSL typically '/dev/ttyUSB0' or '/dev/ttyACM0'.
    """
    system = platform.system().lower()
    if system.startswith('win'):
        return os.environ.get('DAZZLER_DMX_PORT', 'COM3')
    if system == 'darwin':
        return os.environ.get('DAZZLER_DMX_PORT', '/dev/tty.usbserial')
    # Linux / WSL default
    return os.environ.get('DAZZLER_DMX_PORT', '/dev/ttyUSB0')

class _NoopDMX:
    """No-op fallback when DMX/hardware isn't available."""
    def start_broadcast(self):
        print("[DMX] Broadcast disabled (no hardware)")
    def stop_broadcast(self):
        pass
    def close(self):
        pass
    def update_lighting(self, rgbw_tuple, hue_speed):
        # Still print for visibility
        print(f"[DMX] (noop) update {rgbw_tuple} speed={hue_speed:.2f}")

def init_dmx_controller(port: str | None = None, num_channels: int = 8):
    """Initialize the DMX controller if available; fall back to no-op otherwise."""
    if SimpleDMX is None:
        return _NoopDMX()
    port = port or _suggest_default_port()
    try:
        dmx = SimpleDMX(port=port, num_channels=num_channels)
        dmx.start_broadcast()
        print(f"[DMX] Started on {port} with {num_channels} channels")
        return dmx
    except Exception as e:
        print(f"[DMX] Could not open serial port {port}: {e}")
        print("[DMX] Continuing without hardware (noop controller)")
        return _NoopDMX()

# ----------------------
# Feature extraction (unchanged logic from original main.py)
# ----------------------

def parallel_audio_analysis(audio_chunk, sample_rate):
    """Run tempo, loudness, and mode/key detection in parallel."""
    print(f" Processing audio chunk ({len(audio_chunk)/sample_rate:.1f}s)...")
    with Pool(processes=3) as pool:
        mode_key_result = pool.apply_async(detect_mode_key, (audio_chunk, sample_rate))
        tempo_result = pool.apply_async(detect_tempo, (audio_chunk, sample_rate))
        loudness_result = pool.apply_async(detect_loudness, (audio_chunk, sample_rate))
        mode, key = mode_key_result.get()
        tempo = tempo_result.get()
        loudness = loudness_result.get()
    print(f"Detected: {key} {mode}, {tempo:.1f} BPM, {loudness:.1f} dB")
    return mode, key, tempo, loudness

# ----------------------
# Processing functions
# ----------------------

def process_mp3_realtime(mp3_file_path, dmx_controller=None, chunk_duration=2.0, output_to_file=False):
    """Process MP3 file in real-time chunks for lighting control."""
    print(f"🎧 Loading audio: {mp3_file_path}")
    try:
        audio_data, sample_rate = librosa.load(mp3_file_path, sr=None, mono=True)
        total_duration = len(audio_data) / sample_rate
        print(f"Audio loaded: {total_duration:.1f}s, {sample_rate}Hz")
    except Exception as e:
        print(f" Error loading audio: {e}")
        return

    chunk_size = int(chunk_duration * sample_rate)
    num_chunks = len(audio_data) // chunk_size
    print(f"Processing {num_chunks} chunks of {chunk_duration}s each...\n")

    results_list = []
    for i in range(num_chunks):
        start_time = time.time()
        start_sample = i * chunk_size
        end_sample = start_sample + chunk_size
        chunk = audio_data[start_sample:end_sample]

        mode, key, tempo, loudness = parallel_audio_analysis(chunk, sample_rate)

        # Map features to color/hue
        color, hue_speed = process_audio_features(
            loudness=loudness,
            mode=mode,
            key=key,
            tempo=tempo,
        )
        color_dict = map_to_colors(color, hue_speed)
        rgb = color_dict['primary_color']['rgb']
        rgbw = (rgb, rgb[1], rgb[2], 0)  # White channel set to 0

        # Send to DMX if available
        if dmx_controller is not None:
            dmx_controller.update_lighting(rgbw, hue_speed)

        # Package lighting data
        chunk_time = i * chunk_duration
        lighting_data = {
            **color_dict,
            "chunk_number": i + 1,
            "time_position": chunk_time,
            "audio_features": {
                "mode": mode,
                "key": key,
                "tempo": tempo,
                "loudness": loudness,
            },
            "processing_time": time.time() - start_time,
            "lighting_output": {
                "color_name": color,
                "color_tuple": rgbw,
                "hue_speed": hue_speed,
            },
        }

        print(f"Chunk {i+1}/{num_chunks} | Time: {chunk_time:.1f}s")
        print(f"  {key} {mode} |  {tempo:.1f} BPM |  {loudness:.1f} dB")
        print(f"  Color: {color} {rgbw} |  Speed: {hue_speed:.2f}")
        print(f"  ⏱Processed in {lighting_data['processing_time']:.2f}s\n")

        if output_to_file:
            results_list.append(lighting_data)
        yield lighting_data

    if output_to_file and results_list:
        save_results_to_file(results_list, mp3_file_path)

def save_results_to_file(results_list, mp3_file_path):
    import json
    mp3_path = Path(mp3_file_path)
    # Save next to the script to avoid cwd surprises
    out_dir = Path(__file__).parent / 'outputs'
    out_dir.mkdir(parents=True, exist_ok=True)
    output_file = out_dir / f"lighting_data_{mp3_path.stem}.json"
    with open(output_file, 'w') as f:
        json.dump(results_list, f, indent=2)
    print(f" Results saved to: {output_file}")

def process_audio_stream(dmx_controller=None, audio_source="microphone", chunk_duration=1.0):
    """Process real-time audio stream (microphone input)."""
    try:
        import pyaudio
    except ImportError:
        print("PyAudio not installed. Install with: pip install pyaudio")
        return

    print("Starting real-time audio stream processing...")
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100

    p = pyaudio.PyAudio()
    try:
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
        print(" Recording... Press Ctrl+C to stop\n")
        buffer = np.array([], dtype=np.float32)
        buffer_size = int(chunk_duration * RATE)
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_chunk = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            buffer = np.append(buffer, audio_chunk)
            if len(buffer) >= buffer_size:
                mode, key, tempo, loudness = parallel_audio_analysis(buffer[:buffer_size], RATE)
                color, hue_speed = process_audio_features(loudness, mode, key, tempo)
                color_dict = map_to_colors(color, hue_speed)
                rgb = color_dict['primary_color']['rgb']
                rgbw = (rgb, rgb[1], rgb[2], 0)
                if dmx_controller is not None:
                    dmx_controller.update_lighting(rgbw, hue_speed)
                print(f"{key} {mode} | {tempo:.1f} BPM | {loudness:.1f} dB | {color} | Speed: {hue_speed:.2f}")
                buffer = buffer[buffer_size//2:]
    except KeyboardInterrupt:
        print("\n  Stopping audio stream...")
    except Exception as e:
        print(f"Stream error: {e}")
    finally:
        if 'stream' in locals():
            stream.stop_stream(); stream.close()
        p.terminate()

# ----------------------
# Entrypoint
# ----------------------

def main():
    print(" Audio-to-Lighting Pipeline")
    print("=" * 50)
    
    mp3_file = str(Path(__file__).with_name('scom.mp3'))  # next to script by default

    print("Choose processing mode:")
    print("1. Process MP3 file")
    print("2. Real-time microphone input")
    print("3. Demo with synthetic data")

    # Initialize DMX (will fall back to no-op if unavailable)
    dmx = init_dmx_controller(port=None, num_channels=8)

    try:
        choice = input("\nEnter choice (1-3): ").strip()
        if choice == '1':
            if not Path(mp3_file).exists():
                print(f" File not found: {mp3_file}")
                return
            print(f"\n Processing MP3 file: {mp3_file}")
            for _ in process_mp3_realtime(mp3_file, dmx_controller=dmx, chunk_duration=2.0, output_to_file=True):
                pass
        elif choice == '2':
            process_audio_stream(dmx_controller=dmx)
        elif choice == '3':
            demo_pipeline(dmx)
        else:
            print("Invalid choice. Please run again.")
    except KeyboardInterrupt:
        print("\n Goodbye!")
    finally:
        # Always stop DMX on exit
        if dmx:
            try:
                dmx.stop_broadcast()
                dmx.close()
            except Exception:
                pass

def demo_pipeline(dmx_controller=None):
    """Demonstrate the pipeline with synthetic audio data."""
    print("\nRunning demo with synthetic data...\n")
    sample_rate = 44100
    duration = 2.0
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio_data = 0.3 * np.sin(2 * np.pi * 440 * t)
    mode, key, tempo, loudness = parallel_audio_analysis(audio_data, sample_rate)
    color, hue_speed = process_audio_features(loudness, mode, key, tempo)
    color_dict = map_to_colors(color, hue_speed)
    rgb = color_dict['primary_color']['rgb']
    rgbw = (rgb, rgb[1], rgb[2], 0)
    if dmx_controller is not None:
        dmx_controller.update_lighting(rgbw, hue_speed)
    print("Demo completed successfully!")

if __name__ == '__main__':
    main()

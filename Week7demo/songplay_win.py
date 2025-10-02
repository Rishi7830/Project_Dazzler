"""
MP3 Player using ffmpeg + sounddevice
Plays MP3 audio on your laptop speakers.
"""

import subprocess
import numpy as np
import sounddevice as sd

def play_mp3(mp3_path: str, sample_rate: int = 44100, channels: int = 2, blocksize: int = 1024):
    cmd = [
        "ffmpeg",
        "-hide_banner", "-loglevel", "error",
        "-i", mp3_path,
        "-f", "f32le",              # 32-bit float raw PCM
        "-ac", str(channels),       # number of channels
        "-ar", str(sample_rate),    # sample rate
        "pipe:1"
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=blocksize * channels * 4)

    stream = sd.OutputStream(samplerate=sample_rate, channels=channels, dtype="float32", blocksize=blocksize)
    stream.start()

    bytes_per_frame = blocksize * channels * 4  # float32 = 4 bytes
    try:
        while True:
            raw = proc.stdout.read(bytes_per_frame)
            if not raw:
                break
            block = np.frombuffer(raw, dtype=np.float32)
            stream.write(block.reshape(-1, channels))
    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user")
    finally:
        stream.stop()
        stream.close()
        proc.stdout.close()
        proc.wait()

if __name__ == "__main__":
    mp3_file = "Subhanallah.mp3"  # change to your file path
    play_mp3(mp3_file)

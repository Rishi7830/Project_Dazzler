import PyDMXControl as DMX
import sys
# Add the directory to sys.path
sys.path.append('/Users/siddhiprakash/Desktop/Dazzler')
import Test002

if __name__ == "__main__":
    analysis_result = Test002.analyze_audio()

    if analysis_result:
        key, amplitude_db, octave, tempo, beats = analysis_result
        print(f"Key Estimate: {key}")
        print(f"Amplitude (dB):", amplitude_db)
        print(f"Octave: {octave}")
        print(f"Tempo (BPM): {float(tempo):.2f}")
        print(f"Beat Frames:", beats)

# Assume Light with 8 channels
# Channel for colour
# Channel for movement

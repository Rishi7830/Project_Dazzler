"""
Main Audio Processing Pipeline
Orchestrates parallel processing of audio features for real-time lighting control
"""

import librosa
import numpy as np
import time
from multiprocessing import Pool
from pathlib import Path

# Import your modules
from tempo_detection import detect_tempo
from loudness_detection import detect_loudness  
from mode_key_detection import detect_mode_key
from audio_analyzer import process_audio_features
from color_mapper import map_to_colors
#from pyserial import SimpleDMX

def parallel_audio_analysis(audio_chunk, sample_rate):
    """
    Run tempo, loudness, and mode/key detection in parallel
    
    Args:
        audio_chunk (np.array): Audio samples for analysis
        sample_rate (int): Sample rate in Hz
        
    Returns:
        tuple: (mode, key, tempo, loudness)
    """
    
    print(f" Processing audio chunk ({len(audio_chunk)/sample_rate:.1f}s)...")
    
    # Create a pool of 3 workers for parallel processing
    with Pool(processes=3) as pool:
        # Submit all three detection tasks simultaneously
        mode_key_result = pool.apply_async(detect_mode_key, (audio_chunk, sample_rate))
        tempo_result = pool.apply_async(detect_tempo, (audio_chunk, sample_rate))
        loudness_result = pool.apply_async(detect_loudness, (audio_chunk, sample_rate))
        
        # Get results (waits for all to complete)
        mode, key = mode_key_result.get()
        tempo = tempo_result.get()
        loudness = loudness_result.get()
    
    print(f"Detected: {key} {mode}, {tempo:.1f} BPM, {loudness:.1f} dB")
    return mode, key, tempo, loudness

def process_mp3_realtime(mp3_file_path, chunk_duration=2.0, output_to_file=False):
    """
    Process MP3 file in real-time chunks for lighting control
    
    Args:
        mp3_file_path (str): Path to MP3 file
        chunk_duration (float): Duration of each processing chunk in seconds
        output_to_file (bool): Whether to save results to file
        
    Yields:
        dict: Lighting data for each chunk
    """
    
    print(f"🎧 Loading audio: {mp3_file_path}")
    
    # Load MP3 file
    try:
        audio_data, sample_rate = librosa.load(mp3_file_path, sr=None, mono=True)
        total_duration = len(audio_data) / sample_rate
        print(f"Audio loaded: {total_duration:.1f}s, {sample_rate}Hz")
    except Exception as e:
        print(f" Error loading audio: {e}")
        return
    
    # Calculate chunk size in samples
    chunk_size = int(chunk_duration * sample_rate)
    num_chunks = len(audio_data) // chunk_size
    
    print(f"Processing {num_chunks} chunks of {chunk_duration}s each...\n")
    
    results_list = []  # For optional file output
    
    # Process audio in chunks
    for i in range(num_chunks):
        start_time = time.time()
        
        # Extract audio chunk
        start_sample = i * chunk_size
        end_sample = start_sample + chunk_size
        chunk = audio_data[start_sample:end_sample]
        
        # Run parallel analysis (Files 1, 2, 3)
        mode, key, tempo, loudness = parallel_audio_analysis(chunk, sample_rate)
        
        # Process features (File 4)
        color, hue_speed = process_audio_features(
            loudness=loudness,
            mode=mode,
            key=key,
            tempo=tempo
        )
        
        # Generate final lighting data (File 5)
        lighting_data = map_to_colors(color, hue_speed)
        
        # Add metadata
        chunk_time = i * chunk_duration
        lighting_data.update({
            "chunk_number": i + 1,
            "time_position": chunk_time,
            "audio_features": {
                "mode": mode,
                "key": key,
                "tempo": tempo,
                "loudness": loudness
            },
            "processing_time": time.time() - start_time
        })
        
        # Display results
        print(f"Chunk {i+1}/{num_chunks} | Time: {chunk_time:.1f}s")
        print(f"  {key} {mode} |  {tempo:.1f} BPM |  {loudness:.1f} dB")
        print(f"  Color: {color} |  Speed: {hue_speed:.2f}")
        print(f"  ⏱Processed in {lighting_data['processing_time']:.2f}s\n")

        #SimpleDMX(colour, hue_speed)
        
        # Store for optional file output
        if output_to_file:
            results_list.append(lighting_data)
        
        # Yield for real-time use
        yield lighting_data
        
        # Optional: Add delay to simulate real-time playback
        # time.sleep(max(0, chunk_duration - lighting_data['processing_time']))
    
    # Save results to file if requested
    if output_to_file and results_list:
        save_results_to_file(results_list, mp3_file_path)

def save_results_to_file(results_list, mp3_file_path):
    """
    Save processing results to JSON file
    
    Args:
        results_list (list): List of lighting data dicts
        mp3_file_path (str): Original MP3 file path
    """
    
    import json
    
    # Create output filename
    mp3_path = Path(mp3_file_path)
    output_file = f"lighting_data_{mp3_path.stem}.json"
    
    # Save to JSON
    with open(output_file, 'w') as f:
        json.dump(results_list, f, indent=2)
    
    print(f" Results saved to: {output_file}")

def process_audio_stream(audio_source="microphone", chunk_duration=1.0):
    """
    Process real-time audio stream (microphone input)
    
    Args:
        audio_source (str): Audio source type
        chunk_duration (float): Processing chunk duration
    """
    
    try:
        import pyaudio
    except ImportError:
        print("PyAudio not installed. Install with: pip install pyaudio")
        return
    
    print(f"Starting real-time audio stream processing...")
    
    # Audio stream parameters
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    
    # Initialize PyAudio
    p = pyaudio.PyAudio()
    
    try:
        # Open audio stream
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
        
        print(" Recording... Press Ctrl+C to stop\n")
        
        buffer = np.array([], dtype=np.float32)
        buffer_size = int(chunk_duration * RATE)
        
        while True:
            # Read audio data
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_chunk = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Add to buffer
            buffer = np.append(buffer, audio_chunk)
            
            # Process when buffer is full
            if len(buffer) >= buffer_size:
                # Process the chunk
                mode, key, tempo, loudness = parallel_audio_analysis(buffer[:buffer_size], RATE)
                color, hue_speed = process_audio_features(loudness, mode, key, tempo)
                lighting_data = map_to_colors(color, hue_speed)
                
                # Display results
                print(f"{key} {mode} | {tempo:.1f} BPM | {loudness:.1f} dB | {color}")
                
                # Remove processed data from buffer
                buffer = buffer[buffer_size//2:]  # Overlap for continuity
    
    except KeyboardInterrupt:
        print("\n  Stopping audio stream...")
    
    except Exception as e:
        print(f"Stream error: {e}")
    
    finally:
        # Cleanup
        if 'stream' in locals():
            stream.stop_stream()
            stream.close()
        p.terminate()

def main():
    """
    Main function - choose processing mode
    """
    
    print(" Audio-to-Lighting Pipeline")
    print("=" * 50)
    
    # Configuration
    mp3_file = "scom.mp3"  # Change this to your MP3 file
    
    print("Choose processing mode:")
    print("1. Process MP3 file")
    print("2. Real-time microphone input")
    print("3. Demo with sample data")
    
    try:
        choice = input("\nEnter choice (1-3): ").strip()
        
        if choice == "1":
            # Check if MP3 file exists
            if not Path(mp3_file).exists():
                print(f" File not found: {mp3_file}")
                print("Please place your MP3 file in the current directory and update the filename in main()")
                return
            
            # Process MP3 file
            print(f"\n Processing MP3 file: {mp3_file}")
            for lighting_data in process_mp3_realtime(mp3_file, chunk_duration=2.0, output_to_file=True):
                # In a real application, this is where you'd send data to lighting controller
                pass
        
        elif choice == "2":
            # Real-time microphone processing
            process_audio_stream()
        
        elif choice == "3":
            # Demo with synthetic data
            demo_pipeline()
        
        else:
            print("Invalid choice. Please run again.")
    
    except KeyboardInterrupt:
        print("\n Goodbye!")
    except Exception as e:
        print(f" Error: {e}")

def demo_pipeline():
    """
    Demonstrate the pipeline with synthetic audio data
    """
    
    print("\nRunning demo with synthetic data...\n")
    
    # Create synthetic audio data (2 seconds of 440Hz tone)
    sample_rate = 44100
    duration = 2.0
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio_data = 0.3 * np.sin(2 * np.pi * 440 * t)  # A4 note
    
    # Process the synthetic audio
    mode, key, tempo, loudness = parallel_audio_analysis(audio_data, sample_rate)
    color, hue_speed = process_audio_features(loudness, mode, key, tempo)
    lighting_data = map_to_colors(color, hue_speed)
    
    print("Demo completed successfully!")
    
if __name__ == "__main__":
    main()

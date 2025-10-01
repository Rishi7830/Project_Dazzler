"""
Integration Helper Script

This script provides utility functions to help integrate all components
of the music-to-lighting system.
"""

import os
import sys
from pathlib import Path

def check_dependencies():
    """Check if all required modules are available."""
    required_modules = [
        'librosa',
        'numpy',
        'pyserial',
        'csv'
    ]
    
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
            print(f"✓ {module}")
        except ImportError:
            missing_modules.append(module)
            print(f"✗ {module} - MISSING")
    
    if missing_modules:
        print(f"\nMissing modules: {', '.join(missing_modules)}")
        print("Install them with: pip install " + " ".join(missing_modules))
        return False
    
    return True

def check_audio_files(directory="."):
    """Check for audio files in the specified directory."""
    audio_extensions = ['.wav', '.mp3', '.flac', '.m4a', '.aac', '.ogg']
    audio_files = []
    
    for ext in audio_extensions:
        audio_files.extend(Path(directory).glob(f"**/*{ext}"))
    
    if audio_files:
        print(f"Found {len(audio_files)} audio files:")
        for file in audio_files[:10]:  # Show first 10
            print(f"  - {file}")
        if len(audio_files) > 10:
            print(f"  ... and {len(audio_files) - 10} more")
    else:
        print("No audio files found in current directory")
    
    return audio_files

def test_dmx_connection(port="COM14"):
    """Test DMX connection."""
    try:
        from pyserial import SimpleDMX
        dmx = SimpleDMX(port=port, num_channels=8)
        
        if dmx.ser:
            print(f"✓ DMX connection successful on {port}")
            dmx.close()
            return True
        else:
            print(f"✗ DMX connection failed on {port}")
            return False
    except Exception as e:
        print(f"✗ DMX connection error: {e}")
        return False

def list_available_ports():
    """List available serial ports."""
    try:
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        
        if ports:
            print("Available serial ports:")
            for port in ports:
                print(f"  - {port.device}: {port.description}")
        else:
            print("No serial ports found")
        
        return [port.device for port in ports]
    except Exception as e:
        print(f"Error listing ports: {e}")
        return []

def create_sample_config():
    """Create a sample configuration file."""
    config_content = """# Music-to-Light System Configuration

# Audio Settings
SAMPLE_RATE = 44100
WINDOW_SIZE = 5.0  # seconds
HOP_SIZE = 2.5     # seconds

# DMX Settings
DMX_PORT = "COM14"
DMX_CHANNELS = 8

# Default Settings
DEFAULT_GENRE = "pop"
DEFAULT_LIGHTING_MODE = "high"  # "high" or "low"

# File Paths
AUDIO_DIRECTORY = "./audio"
OUTPUT_DIRECTORY = "./results"

# Mood Mapping
ENABLE_STROBE_FOR_HIGH_ENERGY = True
STROBE_TRIGGER_MOODS = ["Excitement", "Arousal", "Pleasure"]

# Debug Settings
VERBOSE_LOGGING = True
SAVE_CSV_RESULTS = True
"""
    
    with open("config.py", "w") as f:
        f.write(config_content)
    
    print("Created sample config.py file")

def run_system_check():
    """Run complete system check."""
    print("=== Music-to-Light System Check ===\n")
    
    print("1. Checking Python dependencies...")
    deps_ok = check_dependencies()
    print()
    
    print("2. Checking for audio files...")
    audio_files = check_audio_files()
    print()
    
    print("3. Listing available serial ports...")
    ports = list_available_ports()
    print()
    
    print("4. Testing DMX connection...")
    dmx_ok = test_dmx_connection()
    print()
    
    print("5. Checking required files...")
    required_files = [
        "Buffer_Manager_Week7.py",
        "Mode_Extraction_Week7.py",
        "Tempo_detection_week7.py",
        "Loudness_detection_Week7.py",
        "Rhythm_Detection_Week7.py",
        "Harmony_detection_Week7.py",
        "KNN_Week7.py"
    ]
    
    missing_files = []
    for file in required_files:
        if os.path.exists(file):
            print(f"✓ {file}")
        else:
            missing_files.append(file)
            print(f"✗ {file} - MISSING")
    
    print("\n=== System Check Summary ===")
    print(f"Dependencies: {'✓' if deps_ok else '✗'}")
    print(f"Audio files: {'✓' if audio_files else '✗'}")
    print(f"DMX connection: {'✓' if dmx_ok else '✗'}")
    print(f"Required files: {'✓' if not missing_files else '✗'}")
    
    if deps_ok and audio_files and not missing_files:
        print("\n🎉 System ready to run!")
        if not dmx_ok:
            print("⚠️  DMX connection issue - lighting may not work")
    else:
        print("\n❌ System not ready - please fix the issues above")
    
    print("\nTo start the system, run: python main_Week7_updated.py")

def quick_test():
    """Run a quick test of the color mapping system."""
    try:
        from mood_color_map_updated import map_mood_to_genre_color, test_mapping
        print("=== Quick Color Mapping Test ===")
        test_mapping()
        print("\n✓ Color mapping system working correctly")
    except ImportError:
        print("✗ Could not import mood_color_map_updated.py")
    except Exception as e:
        print(f"✗ Error in color mapping test: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "check":
            run_system_check()
        elif sys.argv[1] == "test":
            quick_test()
        elif sys.argv[1] == "config":
            create_sample_config()
        elif sys.argv[1] == "ports":
            list_available_ports()
        else:
            print("Available commands: check, test, config, ports")
    else:
        print("Music-to-Light Integration Helper")
        print("\nAvailable commands:")
        print("  python integration_helper.py check   - Run full system check")
        print("  python integration_helper.py test    - Test color mapping")
        print("  python integration_helper.py config  - Create sample config")
        print("  python integration_helper.py ports   - List serial ports")

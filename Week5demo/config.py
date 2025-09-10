"""
Configuration Settings for Audio-to-Lighting Pipeline
Centralized configuration for easy adjustments
"""

import os
from pathlib import Path

# =============================================================================
# AUDIO PROCESSING SETTINGS
# =============================================================================

# Audio file settings
SUPPORTED_AUDIO_FORMATS = ['.mp3', '.wav', '.flac', '.m4a', '.ogg']
DEFAULT_SAMPLE_RATE = 44100  # Hz
DEFAULT_CHUNK_DURATION = 2.0  # seconds per processing chunk

# Analysis window settings
TEMPO_WINDOW_SIZE = 2048
TEMPO_HOP_SIZE = 512

LOUDNESS_WINDOW_SIZE = 2048  
LOUDNESS_HOP_SIZE = 512

MODE_KEY_WINDOW_SIZE = 8192  # Larger window for key detection
MODE_KEY_HOP_SIZE = 4096

# =============================================================================
# PARALLEL PROCESSING SETTINGS
# =============================================================================

# Number of parallel processes (adjust based on your CPU)
NUM_PROCESSES = 3  # One for each: tempo, loudness, mode/key
MAX_PROCESSES = os.cpu_count() or 4  # Fallback to 4 if can't detect

# Processing timeouts (seconds)
PROCESS_TIMEOUT = 30.0  # Maximum time to wait for a single chunk
OVERALL_TIMEOUT = 300.0  # Maximum time for entire file processing

# =============================================================================
# COLOR MAPPING SETTINGS
# =============================================================================

# Color wheel mapping (degrees for each key)
KEY_COLOR_MAPPING = {
    "C": 0,     # Red
    "C#": 30,   # Red-Orange
    "Db": 30,   # Red-Orange (enharmonic)
    "D": 60,    # Yellow
    "D#": 90,   # Yellow-Green
    "Eb": 90,   # Yellow-Green
    "E": 120,   # Green
    "F": 150,   # Green-Cyan
    "F#": 180,  # Cyan
    "Gb": 180,  # Cyan
    "G": 210,   # Cyan-Blue
    "G#": 240,  # Blue
    "Ab": 240,  # Blue
    "A": 270,   # Blue-Magenta
    "A#": 300,  # Magenta
    "Bb": 300,  # Magenta
    "B": 330    # Magenta-Red
}

# Mode brightness/saturation settings
MODE_SETTINGS = {
    "major": {
        "saturation": 0.8,
        "brightness": 0.9,
        "color_multiplier": 1.0
    },
    "minor": {
        "saturation": 0.6,
        "brightness": 0.6,
        "color_multiplier": 0.8
    }
}

# Loudness mapping (dB to brightness multiplier)
LOUDNESS_RANGE = {
    "min_db": -60.0,  # Very quiet
    "max_db": -10.0,  # Very loud
    "min_brightness": 0.2,
    "max_brightness": 1.2
}

# Tempo mapping (BPM to hue cycling speed)
TEMPO_RANGE = {
    "min_bpm": 60,    # Slow
    "max_bpm": 180,   # Fast
    "min_speed": 0.1, # Slow cycling
    "max_speed": 2.0  # Fast cycling
}

# =============================================================================
# LIGHTING OUTPUT SETTINGS
# =============================================================================

# Color transition settings
TRANSITION_DURATION = 0.5  # seconds for smooth color transitions
FADE_ENABLED = True
STROBE_THRESHOLD = 1.5  # Hue speed threshold for strobe effects

# Lighting zones configuration
LIGHTING_ZONES = {
    "main_stage": {
        "intensity_multiplier": 1.0,
        "color_multiplier": 1.0,
        "effects_enabled": True
    },
    "background": {
        "intensity_multiplier": 0.3,  # 30% of main brightness
        "color_multiplier": 0.7,
        "effects_enabled": False
    },
    "accent": {
        "intensity_multiplier": 0.5,
        "color_multiplier": 1.2,  # More vibrant
        "effects_enabled": True,
        "use_complementary_colors": True
    }
}

# =============================================================================
# FILE I/O SETTINGS
# =============================================================================

# Directory paths
INPUT_DIR = Path("input")  # Place MP3 files here
OUTPUT_DIR = Path("output")  # Results saved here
LOGS_DIR = Path("logs")  # Log files

# Create directories if they don't exist
for directory in [INPUT_DIR, OUTPUT_DIR, LOGS_DIR]:
    directory.mkdir(exist_ok=True)

# File naming patterns
LIGHTING_DATA_PREFIX = "lighting_data_"
RESULTS_EXTENSION = ".json"
LOG_EXTENSION = ".log"

# =============================================================================
# REAL-TIME PROCESSING SETTINGS
# =============================================================================

# Microphone input settings
MIC_SAMPLE_RATE = 44100
MIC_CHANNELS = 1  # Mono
MIC_CHUNK_SIZE = 1024
MIC_BUFFER_DURATION = 2.0  # seconds of audio to accumulate before processing

# Stream processing
STREAM_OVERLAP = 0.5  # Overlap ratio between chunks (0.0-0.9)
REALTIME_MODE = True  # Enable real-time optimizations

# =============================================================================
# GENRE DETECTION SETTINGS
# =============================================================================

# Simple genre classification thresholds
GENRE_THRESHOLDS = {
    "electronic": {
        "min_tempo": 120,
        "min_loudness": -20,
        "color_boost": 1.3,
        "speed_boost": 1.5
    },
    "ballad": {
        "max_tempo": 80,
        "mode": "minor",
        "color_boost": 0.7,
        "speed_boost": 0.5
    },
    "classical": {
        "max_tempo": 100,
        "max_loudness": -25,
        "color_boost": 0.8,
        "speed_boost": 0.7
    },
    "rock": {
        "min_tempo": 100,
        "max_tempo": 160,
        "min_loudness": -25,
        "color_boost": 1.1,
        "speed_boost": 1.2
    }
}

# =============================================================================
# DEBUG AND LOGGING SETTINGS
# =============================================================================

# Logging levels
DEBUG_MODE = True
VERBOSE_OUTPUT = True
LOG_PROCESSING_TIMES = True
LOG_AUDIO_FEATURES = True

# Console output formatting
CONSOLE_COLORS = {
    "info": "\033[94m",     # Blue
    "success": "\033[92m",  # Green
    "warning": "\033[93m",  # Yellow
    "error": "\033[91m",    # Red
    "reset": "\033[0m"      # Reset
}

# Performance monitoring
MONITOR_CPU_USAGE = False  # Set to True for performance analysis
MONITOR_MEMORY_USAGE = False

# =============================================================================
# THURSDAY DEMO SETTINGS
# =============================================================================

# Demo-specific configurations
DEMO_MODE = False  # Set to True for demo optimizations
DEMO_CHUNK_DURATION = 1.5  # Shorter chunks for more responsive demo
DEMO_TRANSITION_SPEED = 0.3  # Faster transitions for demo

# Demo display settings
SHOW_PROCESSING_STEPS = True
SHOW_FEATURE_VALUES = True
SHOW_COLOR_PREVIEW = True

# =============================================================================
# VALIDATION AND LIMITS
# =============================================================================

# Input validation ranges
VALID_TEMPO_RANGE = (30, 300)    # BPM
VALID_LOUDNESS_RANGE = (-80, 0)  # dB
VALID_COLOR_RANGE = (0, 255)     # RGB values
VALID_SPEED_RANGE = (0.0, 5.0)   # Hue cycling speed

# Error handling
MAX_RETRIES = 3
FALLBACK_VALUES = {
    "tempo": 120.0,
    "loudness": -30.0,
    "mode": "major",
    "key": "C",
    "color": (128, 128, 128),  # Gray
    "hue_speed": 1.0
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_processing_config():
    """Get the current processing configuration as a dictionary"""
    return {
        "chunk_duration": DEFAULT_CHUNK_DURATION,
        "sample_rate": DEFAULT_SAMPLE_RATE,
        "num_processes": NUM_PROCESSES,
        "tempo_settings": {
            "window_size": TEMPO_WINDOW_SIZE,
            "hop_size": TEMPO_HOP_SIZE
        },
        "loudness_settings": {
            "window_size": LOUDNESS_WINDOW_SIZE,
            "hop_size": LOUDNESS_HOP_SIZE
        },
        "mode_key_settings": {
            "window_size": MODE_KEY_WINDOW_SIZE,
            "hop_size": MODE_KEY_HOP_SIZE
        }
    }

def validate_config():
    """Validate configuration settings"""
    errors = []
    
    if NUM_PROCESSES > MAX_PROCESSES:
        errors.append(f"NUM_PROCESSES ({NUM_PROCESSES}) exceeds MAX_PROCESSES ({MAX_PROCESSES})")
    
    if DEFAULT_CHUNK_DURATION <= 0:
        errors.append("DEFAULT_CHUNK_DURATION must be positive")
    
    if TRANSITION_DURATION < 0:
        errors.append("TRANSITION_DURATION cannot be negative")
    
    return errors

# Validate configuration on import
_config_errors = validate_config()
if _config_errors and DEBUG_MODE:
    print("⚠️  Configuration warnings:")
    for error in _config_errors:
        print(f"   - {error}")

# Export commonly used settings
__all__ = [
    'DEFAULT_CHUNK_DURATION',
    'DEFAULT_SAMPLE_RATE', 
    'NUM_PROCESSES',
    'KEY_COLOR_MAPPING',
    'MODE_SETTINGS',
    'LOUDNESS_RANGE',
    'TEMPO_RANGE',
    'get_processing_config',
    'validate_config'
]

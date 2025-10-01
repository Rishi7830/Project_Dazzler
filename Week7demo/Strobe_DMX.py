"""
Strobe DMX Controller

Enhanced strobe controller that can work with mood colors and energy levels.
Can be triggered for special high-energy moments or specific moods.
"""

import time
from pyserial import SimpleDMX
import serial

def rgb_to_rgbw(rgb_color, brightness=1.0):
    """Convert RGB color tuple to RGBW tuple."""
    r, g, b = rgb_color
    w = min(r, g, b)  # crude white channel
    return (
        int(r * brightness),
        int(g * brightness),
        int(b * brightness),
        int(w * brightness),
    )

def energy_to_strobe_pattern(energy_level):
    """Map energy level to strobe patterns."""
    patterns = {
        "high": {
            "on_time": 0.02,
            "off_time": 0.03,
            "burst_count": 5,
            "burst_pause": 0.2
        },
        "medium": {
            "on_time": 0.05,
            "off_time": 0.05,
            "burst_count": 3,
            "burst_pause": 0.3
        },
        "low": {
            "on_time": 0.1,
            "off_time": 0.1,
            "burst_count": 2,
            "burst_pause": 0.5
        }
    }
    return patterns.get(energy_level, patterns["medium"])

def should_trigger_strobe(mood):
    """Determine if strobe should be triggered based on mood."""
    strobe_moods = ["Excitement", "Arousal", "Pleasure"]
    return mood in strobe_moods

def run_strobe_dmx_chunk(mood_color, energy_level, port="COM14", duration=5.0):
    """
    Run strobe effect for a single chunk based on mood and energy.
    
    Args:
        mood_color (tuple): RGB color for the strobe
        energy_level (str): Energy level ("high", "medium", "low")
        port (str): DMX serial port
        duration (float): Duration to run strobe (seconds)
    """
    try:
        # Initialize DMX
        dmx = SimpleDMX(port=port, num_channels=8)
        if not dmx.ser:
            print(f"Warning: DMX controller not initialized on {port}")
            return
        
        dmx.start_broadcast()
        
        # Get strobe pattern based on energy level
        pattern = energy_to_strobe_pattern(energy_level)
        
        # Convert color to RGBW
        strobe_rgbw = rgb_to_rgbw(mood_color, brightness=1.0)
        black_rgbw = (0, 0, 0, 0)
        
        print(f"Strobe DMX: Color {mood_color}, Energy {energy_level}")
        
        start_time = time.time()
        
        while time.time() - start_time < duration:
            # Burst pattern
            for _ in range(pattern["burst_count"]):
                if time.time() - start_time >= duration:
                    break
                
                # Flash ON
                if dmx.ser and dmx.ser.is_open:
                    try:
                        dmx.update_lighting(strobe_rgbw, hue_speed=0)
                    except serial.SerialTimeoutException:
                        print("DMX write timeout, skipping frame")
                    except Exception as e:
                        print(f"DMX write error: {e}")
                
                time.sleep(pattern["on_time"])
                
                # Flash OFF
                if dmx.ser and dmx.ser.is_open:
                    try:
                        dmx.update_lighting(black_rgbw, hue_speed=0)
                    except serial.SerialTimeoutException:
                        pass
                    except Exception as e:
                        print(f"DMX write error: {e}")
                
                time.sleep(pattern["off_time"])
            
            # Pause between bursts
            time.sleep(pattern["burst_pause"])
        
        dmx.close()
        
    except Exception as e:
        print(f"Strobe DMX error: {e}")

def run_strobe_dmx(port="COM14", num_channels=8, strobe_speed=0.05):
    """
    Legacy function: Run a white strobe effect on DMX lights.
    
    Args:
        port (str): Serial port for DMX interface.
        num_channels (int): Number of DMX channels (usually 8 or more).
        strobe_speed (float): Time in seconds for each flash on/off.
    """
    # Initialize DMX controller
    dmx = SimpleDMX(port=port, num_channels=num_channels)
    if not dmx.ser:
        print("DMX controller not initialized.")
        return

    dmx.start_broadcast()
    print("DMX broadcast started. Press Ctrl+C to stop.")

    # White light at full brightness
    white_rgbw = (255, 255, 255, 255)
    black_rgbw = (0, 0, 0, 0)

    try:
        step = 0
        while True:
            # Flash ON
            if dmx.ser and dmx.ser.is_open:
                try:
                    dmx.update_lighting(white_rgbw, hue_speed=0)
                except serial.SerialTimeoutException:
                    print("Write timeout occurred, skipping frame")
                except Exception as e:
                    print(f"DMX write error: {e}")

            time.sleep(strobe_speed)

            # Flash OFF
            if dmx.ser and dmx.ser.is_open:
                try:
                    dmx.update_lighting(black_rgbw, hue_speed=0)
                except serial.SerialTimeoutException:
                    print("Write timeout occurred, skipping frame")
                except Exception as e:
                    print(f"DMX write error: {e}")

            time.sleep(strobe_speed)

            step += 1
            if step % 100 == 0:
                print(f"Strobe cycle {step}")

    except KeyboardInterrupt:
        print("\\nStopping strobe effect...")
    except Exception as e:
        print(f"Strobe error: {e}")
    finally:
        # Turn off lights
        try:
            if dmx.ser and dmx.ser.is_open:
                dmx.update_lighting(black_rgbw, hue_speed=0)
        except:
            pass
        
        dmx.close()
        print("DMX connection closed.")

# Test function
def test_strobe_dmx():
    """Test the strobe DMX controller."""
    print("Testing Strobe DMX Controller...")
    
    test_colors = [
        ((255, 0, 0), "high"),    # Red, high energy
        ((255, 255, 255), "high"), # White, high energy  
        ((255, 69, 0), "medium"), # Orange, medium energy
        ((255, 215, 0), "low"),   # Gold, low energy
    ]
    
    for color, energy in test_colors:
        print(f"\\nTesting: Color {color}, Energy {energy}")
        run_strobe_dmx_chunk(color, energy, duration=2.0)
        time.sleep(0.5)
    
    print("Test complete!")

if __name__ == "__main__":
    # Run test
    test_strobe_dmx()

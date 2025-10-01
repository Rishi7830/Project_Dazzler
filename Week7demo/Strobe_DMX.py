"""
Strobe DMX Controller

Flashes white light at full brightness as a strobe effect.
Very fast on/off cycles for high energy visual effect.
"""

import time
from pyserial import SimpleDMX
import serial

def run_strobe_dmx(port="COM4", num_channels=8, strobe_speed=0.05):
    """
    Run a white strobe effect on DMX lights.

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
                    print("DMX write error:", e)

            time.sleep(strobe_speed)

            # Flash OFF
            if dmx.ser and dmx.ser.is_open:
                try:
                    dmx.update_lighting(black_rgbw, hue_speed=0)
                except serial.SerialTimeoutException:
                    print("Write timeout occurred, skipping frame")
                except Exception as e:
                    print("DMX write error:", e)

            time.sleep(strobe_speed)
            step += 1

    except KeyboardInterrupt:
        print("Stopping Strobe DMX...")
    finally:
        dmx.close()
        print("DMX connection closed.")


if __name__ == "__main__":
    print("Strobe DMX Controller")
    run_strobe_dmx(port="COM4", strobe_speed=0.05)


# dmx_test.py

from dmx_controller import SimpleDMX
import time

# --- CONFIGURATION ---
DMX_PORT = '/dev/tty4' # Use the port name you found earlier

def run_test():
    print("--- DMX Light Test ---")
    dmx = SimpleDMX(port=DMX_PORT)

    if not dmx.ser:
        print("Could not connect to DMX controller. Exiting.")
        return

    try:
        dmx.start_broadcast()

        print("\n💡 Turning light RED for 3 seconds...")
        dmx.update_lighting((255, 0, 0, 0), is_strobe=False)
        time.sleep(3)

        print("💡 Turning light BLUE for 3 seconds...")
        dmx.update_lighting((0, 0, 255, 0), is_strobe=False)
        time.sleep(3)
        
        print("⚡️ Strobing WHITE for 3 seconds...")
        dmx.update_lighting((0, 0, 0, 255), is_strobe=True)
        time.sleep(3)

        print("⚫ Turning light OFF.")
        dmx.turn_off()
        time.sleep(1)

    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
    finally:
        dmx.close()
        print("\nTest complete.")

if __name__ == "__main__":
    run_test()

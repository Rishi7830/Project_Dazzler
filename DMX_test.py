import pyartnet
import asyncio
import numpy as np
import sys
# import time # time is not strictly needed when using asyncio.sleep

# --- Configuration ---
# IP address QLC+ is LISTENING ON for Art-Net Input
# Use '127.0.0.1' if Python and QLC+ are on the SAME computer
QLC_LISTENING_IP = '127.0.0.1'

# Art-Net Universe QLC+ is LISTENING FOR in its Input configuration
# Often defaults to 0 if QLC+ Output Universe is 1 and using default Art-Net mapping
ARTNET_TARGET_UNIVERSE = 0

# --- Main Asynchronous Function ---
async def main():
    """
    Main asynchronous function to connect to QLC+ via Art-Net
    and run a DMX light sequence.
    """
    node = None # Initialize node to None for reliable cleanup in finally block
    print(f"Setting up Art-Net node to send to QLC+ at {QLC_LISTENING_IP}, Universe {ARTNET_TARGET_UNIVERSE}")
    try:
        # --- Create Art-Net Node representation in Python ---
        # Connects to QLC+'s IP and the standard Art-Net port 6454.
        # max_fps limits how often packets *can* be sent if data changes rapidly.
        # This implicitly starts background asyncio tasks for sending.
        node = pyartnet.ArtNetNode(QLC_LISTENING_IP, 6454, max_fps=40)

        # --- Create a Universe Controller ---
        # Represents the specific Art-Net universe we are sending to.
        universe_controller = node.add_universe(ARTNET_TARGET_UNIVERSE)

        # --- Add a Channel Object to the Universe ---
        # This object represents the block of DMX channels we want to control.
        # start=1 because DMX channels are traditionally 1-indexed.
        # width=512 covers all possible DMX channels in the universe.
        dmx_channel = universe_controller.add_channel(start=1, width=512)

        # --- DMX Data Array (512 channels) ---
        # Using numpy for efficient array manipulation.
        # Index 0 corresponds to DMX Channel 1, Index 1 to Ch 2, ..., Index 511 to Ch 512.
        dmx_data = np.zeros(512, dtype=np.uint8) # Initialize all channels to 0 (blackout)

        print("Art-Net node, universe, and channel created. Starting color sequence...")
        print("--- Channel Mapping Used ---")
        print(" DMX Ch 1 (Index 0): Brightness")
        print(" DMX Ch 2 (Index 1): Red")
        print(" DMX Ch 3 (Index 2): Green")
        print(" DMX Ch 4 (Index 3): Blue")
        print("----------------------------")

        # --- Set Brightness to Full ---
        print("Setting Brightness (Ch 1) to Full")
        dmx_data[0] = 255  # Index 0 = DMX Channel 1 (Brightness)
        dmx_channel.set_values(dmx_data) # Send the updated DMX data
        await asyncio.sleep(1) # Pause for 1 second

        # --- Cycle Red ---
        print("Showing Red (Ch 2)")
        dmx_data[1] = 255  # Index 1 = DMX Channel 2 (Red)
        dmx_channel.set_values(dmx_data)
        await asyncio.sleep(2) # Pause for 2 seconds
        dmx_data[1] = 0    # Turn Red off
        dmx_channel.set_values(dmx_data)
        await asyncio.sleep(0.5)

        # --- Cycle Green ---
        print("Showing Green (Ch 3)")
        dmx_data[2] = 255  # Index 2 = DMX Channel 3 (Green)
        dmx_channel.set_values(dmx_data)
        await asyncio.sleep(2) # Pause for 2 seconds
        dmx_data[2] = 0    # Turn Green off
        dmx_channel.set_values(dmx_data)
        await asyncio.sleep(0.5)

        # --- Cycle Blue ---
        print("Showing Blue (Ch 4)")
        dmx_data[3] = 255  # Index 3 = DMX Channel 4 (Blue)
        dmx_channel.set_values(dmx_data)
        await asyncio.sleep(2) # Pause for 2 seconds
        dmx_data[3] = 0    # Turn Blue off
        dmx_channel.set_values(dmx_data)
        await asyncio.sleep(0.5)

        # --- Show Yellow (Red + Green) ---
        print("Showing Yellow (Ch 2 + Ch 3)")
        dmx_data[1] = 255  # Red on
        dmx_data[2] = 255  # Green on
        dmx_channel.set_values(dmx_data)
        await asyncio.sleep(3) # Pause for 3 seconds
        dmx_data[1] = 0    # Red off
        dmx_data[2] = 0    # Green off
        dmx_channel.set_values(dmx_data)
        await asyncio.sleep(0.5)

        # --- Fade Out Brightness ---
        print("Fading Out Brightness (Ch 1)")
        for i in range(255, -1, -1): # Loop from 255 down to 0
            dmx_data[0] = i # Set Brightness (Index 0)
            dmx_channel.set_values(dmx_data)
            # Use a shorter sleep for smoother fading
            await asyncio.sleep(0.015) # Approx 15ms delay per step

        print("Sequence complete. Final state is blackout.")
        # Ensure final blackout frame is sent
        dmx_data[:] = 0
        dmx_channel.set_values(dmx_data)
        await asyncio.sleep(0.2) # Keep running briefly to ensure final frame sent

    except KeyboardInterrupt:
        print("\nStopping DMX sequence due to Ctrl+C.")
        # Ensure lights go off on interrupt
        if 'dmx_channel' in locals() and 'dmx_data' in locals():
             print("Sending final blackout frame...")
             dmx_data[:] = 0
             dmx_channel.set_values(dmx_data)
             await asyncio.sleep(0.1) # Allow time for frame to send
    except ConnectionRefusedError:
         print(f"\nError: Connection refused. Is QLC+ running and listening on {QLC_LISTENING_IP}:6454?")
    except Exception as e:
        print(f"\nAn unexpected error occurred during operation: {e}")
        # You might want to uncomment the next line during debugging to see the full error details
        # raise e
    finally:
        # No explicit node.stop() needed for this version of pyartnet
        # The asyncio loop closure handles task cleanup.
        print("Script finished.")
        # Optional: Add a small delay if experiencing issues with the very last packet
        # await asyncio.sleep(0.1)


# --- Run the main async function ---
# This standard Python construct ensures the code runs only when the script is executed directly.
if __name__ == "__main__":
    try:
        # This starts the asyncio event loop and runs the main() coroutine until it completes.
        asyncio.run(main())
    except RuntimeError as e:
        # Handle cases where the event loop might already be running (e.g., in some IDEs/notebooks)
        if "Cannot run the event loop while another loop is running" in str(e):
            print("INFO: asyncio event loop is already running.")
            # If in an environment like Jupyter, you might need:
            # await main()
            # Or configure the environment's loop integration.
        else:
            print(f"RuntimeError occurred when starting asyncio: {e}")
    except Exception as e:
         print(f"An unexpected error occurred outside the main async function: {e}")

import serial
import time
import random

# Replace with your current Enttec USB DMX path
PORT = '/dev/tty.usbserial-A50285BI'
BAUD = 57600  # Standard for OpenDMX

# Open serial port
ser = serial.Serial(PORT, BAUD)

# DMX has 512 channels, index 0 is start code
dmx = bytearray([0]*512)

try:
    print("Sending continuous DMX frames. Press Ctrl+C to stop.")

    while True:
        #Example: random values for all channels (1-512)
        #for i in range(1, 512):
        #    dmx[i] = 250
        dmx[0] = 250
        dmx[1] = 250
        dmx[2] = 250
        dmx[3] = 250
        dmx[4] = 250
        dmx[5] = 250
        dmx[6] = 250
        dmx[7] = 250
        dmx[8] = 250
        dmx[9] = 250

        # Send DMX frame
        ser.break_condition = True
        time.sleep(0.001)  # DMX break
        ser.break_condition = False
        ser.write(dmx)

        # ~40 Hz refresh rate
        time.sleep(0.025)

except KeyboardInterrupt:
    print("Stopped by user")

finally:
    ser.close()

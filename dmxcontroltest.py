import serial
import ftdi
import time

def send_dmx(port, channel_data):
    # This function sends DMX data over the serial port
    ser = serial.Serial(port, baudrate=250000, bytesize=8, stopbits=2, parity='N')
    ser.write(bytes([0x00]))  # Send start code
    for i in range(512):
        if i in channel_data:
            ser.write(bytes([channel_data[i]]))
        else:
            ser.write(bytes([0]))
    ser.close()

try:
    print("Setting lights to Red")
    send_dmx('COM4', {1: 255})
    time.sleep(5)
    
    print("Setting lights to Green")
    send_dmx('COM4', {2: 255})
    time.sleep(5)

    print("Setting lights to Blue")
    send_dmx('COM4', {3: 255})
    time.sleep(5)

    print("Turning lights off")
    send_dmx('COM4', {})

except Exception as e:
    print(f"Error: {e}")
    print("Please check your port name and DMX device connection.")

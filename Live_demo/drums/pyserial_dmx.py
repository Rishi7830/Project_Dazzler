# pyserial_dmx.py
import serial, time, threading

# DMX channels for MH363 (9ch mode, address 1)
CH_PAN=1; CH_TILT=2; CH_STROBE=3; CH_RED=4; CH_GREEN=5; CH_BLUE=6; CH_WHITE=7; CH_DIMMER=8; CH_SOUND=9
VAL_LED_START=255  # constant-on band end

class SimpleDMX:
    def __init__(self, port: str, refresh_interval: float = 0.03):
        self.port=port
        self.num_channels=9
        self.data=[0]*self.num_channels
        self.running=False
        self.refresh_interval=refresh_interval
        self.thread=None
        try:
            self.ser=serial.Serial(port, baudrate=250000, bytesize=serial.EIGHTBITS,
                                   parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_TWO)
            print(f"Serial DMX port {self.port} opened successfully.")
            # Defaults: constant light, full dimmer, sound off
            self.set_channel_internal(CH_PAN,0)
            self.set_channel_internal(CH_TILT,0)
            self.set_channel_internal(CH_STROBE,VAL_LED_START)  # keep constant-on
            self.set_channel_internal(CH_DIMMER,255)
            self.set_channel_internal(CH_SOUND,0)
        except serial.SerialException as e:
            print(f"Error opening DMX port {self.port}: {e}")
            self.ser=None

    def set_channel_internal(self, ch:int, val:int):
        if self.ser and 1<=ch<=self.num_channels:
            self.data[ch-1]=max(0,min(255,int(val)))

    def set_channels_from_tuple(self, color):
        if not self.ser: return
        if len(color)>=4:
            r,g,b,w=color[:4]
            self.set_channel_internal(CH_RED,r)
            self.set_channel_internal(CH_GREEN,g)
            self.set_channel_internal(CH_BLUE,b)
            self.set_channel_internal(CH_WHITE,w)

    def send_frame(self):
        if not self.ser: return
        try:
            # Pseudo-break for cheaper adapters
            self.ser.baudrate=57600; self.ser.write(b'\x00'); self.ser.flush(); time.sleep(0.001)
            self.ser.baudrate=250000
            frame=bytes([0])+bytes(self.data)
            self.ser.write(frame); self.ser.flush()
        except serial.SerialException as e:
            print(f"DMX write error: {e}")

    def broadcast_loop(self):
        print("DMX broadcast thread started.")
        while self.running:
            self.send_frame()
            time.sleep(self.refresh_interval)
        print("DMX broadcast stopped.")

    def start_broadcast(self):
        if not self.ser:
            print("DMX serial port not available. Broadcast disabled.")
            return
        if not self.running:
            self.running=True
            self.thread=threading.Thread(target=self.broadcast_loop,daemon=True)
            self.thread.start()

    def stop_broadcast(self):
        if self.running and self.thread:
            self.running=False; self.thread.join(timeout=1.0)

    def close(self):
        self.stop_broadcast()
        if self.ser and self.ser.is_open:
            # Blackout on close
            for ch in (CH_RED,CH_GREEN,CH_BLUE,CH_WHITE): self.set_channel_internal(ch,0)
            self.set_channel_internal(CH_DIMMER,0)
            self.send_frame(); time.sleep(0.1)
            self.ser.close(); print(f"DMX port {self.port} closed.")

import numpy as np

class AudioBuffer:
    def __init__(self, window_size):
        self.window_size = window_size
        self.buffer = np.zeros(window_size, dtype=np.float32)

    def update(self, new_chunk):
        chunk_len = len(new_chunk)
        self.buffer = np.roll(self.buffer, -chunk_len)
        self.buffer[-chunk_len:] = new_chunk

    def get_window(self):
        return self.buffer.copy()

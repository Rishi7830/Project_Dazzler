import numpy as np

class AudioBuffer:
    def __init__(self, window_size):
        self.window_size = window_size
        self.buffer = np.zeros(window_size, dtype=np.float32)

    def update(self, new_chunk):
        chunk_len = len(new_chunk)
        if not isinstance(new_chunk, np.ndarray):
            print("[DEBUG] new_chunk is not a numpy array!")
        if new_chunk.dtype != np.float32:
            print(f"[DEBUG] new_chunk dtype is {new_chunk.dtype}, expected float32 - converting for safety.")
            new_chunk = new_chunk.astype(np.float32)
        # Optionally normalize if you suspect input scaling issues:
        if np.max(np.abs(new_chunk)) > 1.1:
            print(f"[DEBUG] new_chunk max {np.max(np.abs(new_chunk))} > 1, normalizing down.")
            new_chunk = new_chunk / np.max(np.abs(new_chunk))
        self.buffer = np.roll(self.buffer, -chunk_len)
        self.buffer[-chunk_len:] = new_chunk
         # Print buffer stats after update:
        print(f"[DEBUG] Buffer min: {self.buffer.min()}, max: {self.buffer.max()}, dtype: {self.buffer.dtype}")

    def get_window(self):
        return self.buffer.copy()

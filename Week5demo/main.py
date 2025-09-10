from src.loudness_detection import detect_loudness_simple

# Your parallel processing
with Pool(3) as pool:
    result1 = pool.apply_async(detect_mode_key, (audio_chunk, sample_rate))
    result2 = pool.apply_async(detect_tempo, (audio_chunk, sample_rate))
    result3 = pool.apply_async(detect_loudness_simple, (audio_chunk, sample_rate))  # ✅
    
    mode, key = result1.get()
    tempo = result2.get()
    loudness = result3.get()  # Single loudness value per chunk

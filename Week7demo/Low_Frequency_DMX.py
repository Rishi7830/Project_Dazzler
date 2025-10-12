import time
import random
from dmx_controller import SimpleDMX
import serial

# Utility Functions
def rgb_to_rgbw(rgb_color, brightness=1.0):
    r, g, b = rgb_color
    w = min(r, g, b)
    return (
        int(r * brightness),
        int(g * brightness),
        int(b * brightness),
        int(w * brightness),
    )

def hex_to_rgbw(hex_code, brightness=1.0):
    hex_code = hex_code.lstrip("#")
    r, g, b = tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))
    w = min(r, g, b)
    return (
        int(r * brightness),
        int(g * brightness),
        int(b * brightness),
        int(w * brightness),
    )

def crossfade_colors(rgbw1, rgbw2, steps=60):  # More steps for smoothness
    for i in range(steps + 1):
        t = i / steps
        yield tuple(int(a + (b - a) * t) for a, b in zip(rgbw1, rgbw2))

def energy_to_brightness(energy_level):
    energy_map = {
        "high": 0.8,
        "medium": 0.6,
        "low": 0.4
    }
    return energy_map.get(energy_level, 0.5)

def create_ambient_colors(base_color, count=3):
    colors = [base_color]
    r, g, b = base_color
    for i in range(1, count):
        factor = 0.8 + (i * 0.1)
        if i % 2 == 0:  # Warmer tones
            r_var = min(255, int(r * factor + 10))
            g_var = max(0, int(g * factor - 5))
            b_var = max(0, int(b * factor - 10))
        else:  # Cooler tones
            r_var = max(0, int(r * factor - 10))
            g_var = max(0, int(g * factor - 5))
            b_var = min(255, int(b * factor + 10))
        colors.append((r_var, g_var, b_var))
    return colors

def run_low_frequency_dmx_chunk(dmx, mood_color, energy_level, duration=5.0):
    import time
    def rgb_to_rgbw(rgb_color, brightness=1.0):
        r, g, b = rgb_color
        w = min(r, g, b)
        return (int(r * brightness), int(g * brightness), int(b * brightness), int(w * brightness))
    def crossfade_colors(rgbw1, rgbw2, steps=60):
        for i in range(steps + 1):
            t = i / steps
            yield tuple(int(a + (b - a) * t) for a, b in zip(rgbw1, rgbw2))
    brightness = {"high": 0.8, "medium": 0.6, "low": 0.4}.get(energy_level, 0.5)
    fade_steps = 60
    fade_speed = 0.15
    ambient_colors = [mood_color] * 3
    start_time = time.time()
    color_index = 0
    while time.time() - start_time < duration:
        current_color = ambient_colors[color_index % len(ambient_colors)]
        next_color = ambient_colors[(color_index + 1) % len(ambient_colors)]
        current_rgbw = rgb_to_rgbw(current_color, brightness)
        next_rgbw = rgb_to_rgbw(next_color, brightness)
        for fade_color in crossfade_colors(current_rgbw, next_rgbw, fade_steps):
            if time.time() - start_time >= duration:
                break
            dmx.update_lighting(fade_color, hue_speed=0.3)
            time.sleep(fade_speed)
        color_index += 1


# Optional: Test function for visual preview (not called in normal pipeline)
def test_low_frequency_dmx():
    print("Testing Low Frequency DMX Controller...")
    test_colors = [
        ((255, 0, 0), "high"),
        ((0, 255, 0), "medium"),
        ((0, 0, 255), "low"),
        ((135, 206, 250), "low"),
    ]
    for color, energy in test_colors:
        print(f"\nTesting: Color {color}, Energy {energy}")
        run_low_frequency_dmx_chunk(color, energy, duration=3.0)
        time.sleep(0.5)
    print("Test complete!")

if __name__ == "__main__":
    test_low_frequency_dmx()


"""
Color Mapper Module (File 5)
Maps color and hue cycling speed to final lighting output
Handles color cycling, transitions, and lighting device communication
"""

import numpy as np
import time
import colorsys
from typing import Dict, List, Tuple

class ColorMapper:
    """
    Handles color mapping, cycling, and lighting output
    """
    
    def __init__(self):
        self.current_time = 0.0
        self.last_color = (255, 255, 255)  # White default
        self.transition_duration = 0.5  # Smooth transitions
    
    def map_to_colors(self, base_color: tuple, hue_speed: float, current_time: float = None) -> Dict:
        """
        Map base color and hue speed to final lighting output
        
        Args:
            base_color (tuple): RGB color tuple (r, g, b)
            hue_speed (float): Hue cycling speed (0.0-2.0)
            current_time (float): Current time in seconds (optional)
            
        Returns:
            dict: Final lighting data with cycling colors
        """
        
        if current_time is None:
            current_time = time.time()
        
        # Generate cycling color based on time and speed
        cycling_color = self._generate_cycling_color(base_color, hue_speed, current_time)
        
        # Apply smooth transition from previous color
        final_color = self._smooth_transition(cycling_color, current_time)
        
        # Generate lighting commands for different zones/devices
        lighting_data = self._generate_lighting_commands(final_color, hue_speed)
        
        self.last_color = final_color
        self.current_time = current_time
        
        return lighting_data
    
    def _generate_cycling_color(self, base_color: tuple, hue_speed: float, current_time: float) -> tuple:
        """
        Generate color with hue cycling based on speed and time
        
        Args:
            base_color (tuple): Base RGB color
            hue_speed (float): Cycling speed
            current_time (float): Current time
            
        Returns:
            tuple: Cycling RGB color
        """
        
        r, g, b = base_color
        
        # Convert to HSV for easier hue manipulation
        h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
        
        # Calculate hue offset based on time and speed
        # Complete cycle every (2.0 / hue_speed) seconds
        cycle_period = 2.0 / max(hue_speed, 0.1)  # Avoid division by zero
        hue_offset = (current_time / cycle_period) % 1.0
        
        # Apply hue cycling
        new_hue = (h + hue_offset) % 1.0
        
        # Convert back to RGB
        r_new, g_new, b_new = colorsys.hsv_to_rgb(new_hue, s, v)
        
        return (int(r_new * 255), int(g_new * 255), int(b_new * 255))
    
    def _smooth_transition(self, target_color: tuple, current_time: float) -> tuple:
        """
        Apply smooth color transitions to avoid jarring changes
        
        Args:
            target_color (tuple): Target RGB color
            current_time (float): Current time
            
        Returns:
            tuple: Smoothed RGB color
        """
        
        if hasattr(self, '_transition_start_time'):
            # Calculate transition progress (0.0 to 1.0)
            elapsed = current_time - self._transition_start_time
            progress = min(elapsed / self.transition_duration, 1.0)
            
            # Linear interpolation between colors
            r1, g1, b1 = self.last_color
            r2, g2, b2 = target_color
            
            r = int(r1 + (r2 - r1) * progress)
            g = int(g1 + (g2 - g1) * progress)
            b = int(b1 + (b2 - b1) * progress)
            
            return (r, g, b)
        else:
            self._transition_start_time = current_time
            return target_color
    
    def _generate_lighting_commands(self, color: tuple, hue_speed: float) -> Dict:
        """
        Generate commands for different lighting zones/devices
        
        Args:
            color (tuple): RGB color
            hue_speed (float): Hue cycling speed
            
        Returns:
            dict: Lighting commands for different zones
        """
        
        r, g, b = color
        
        # Convert to different formats for various devices
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        hsv_color = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
        
        # Calculate brightness and saturation
        brightness = int(hsv_color[2] * 100)  # 0-100%
        saturation = int(hsv_color[1] * 100)  # 0-100%
        hue = int(hsv_color[0] * 360)  # 0-360 degrees
        
        return {
            "primary_color": {
                "rgb": color,
                "hex": hex_color,
                "hsv": (hue, saturation, brightness)
            },
            "zones": {
                "main_stage": {
                    "rgb": color,
                    "intensity": brightness,
                    "strobe_speed": self._speed_to_strobe(hue_speed)
                },
                "background": {
                    "rgb": self._dim_color(color, 0.3),  # 30% dimmer
                    "intensity": max(20, brightness // 2),
                    "fade_speed": hue_speed
                },
                "accent": {
                    "rgb": self._complement_color(color),  # Complementary color
                    "intensity": brightness // 3,
                    "pulse_rate": hue_speed
                }
            },
            "effects": {
                "cycling_enabled": hue_speed > 0.5,
                "transition_speed": hue_speed,
                "pulse_enabled": brightness > 70,
                "strobe_enabled": hue_speed > 1.5
            },
            "timestamp": time.time()
        }
    
    def _speed_to_strobe(self, hue_speed: float) -> int:
        """
        Convert hue speed to strobe rate (flashes per minute)
        
        Args:
            hue_speed (float): Hue cycling speed
            
        Returns:
            int: Strobe rate (0-120 FPM)
        """
        
        if hue_speed > 1.5:
            return int(hue_speed * 40)  # Fast strobing
        else:
            return 0  # No strobing
    
    def _dim_color(self, color: tuple, factor: float) -> tuple:
        """
        Dim a color by a factor
        
        Args:
            color (tuple): RGB color
            factor (float): Dimming factor (0.0-1.0)
            
        Returns:
            tuple: Dimmed RGB color
        """
        
        r, g, b = color
        return (int(r * factor), int(g * factor), int(b * factor))
    
    def _complement_color(self, color: tuple) -> tuple:
        """
        Generate complementary color (opposite on color wheel)
        
        Args:
            color (tuple): RGB color
            
        Returns:
            tuple: Complementary RGB color
        """
        
        r, g, b = color
        h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
        
        # Shift hue by 180 degrees (0.5 in normalized range)
        comp_hue = (h + 0.5) % 1.0
        
        # Convert back to RGB
        r_comp, g_comp, b_comp = colorsys.hsv_to_rgb(comp_hue, s, v)
        
        return (int(r_comp * 255), int(g_comp * 255), int(b_comp * 255))

# Convenience function for simple usage
def map_to_colors(base_color: tuple, hue_speed: float) -> Dict:
    """
    Simple function interface for color mapping
    
    Args:
        base_color (tuple): RGB color tuple
        hue_speed (float): Hue cycling speed
        
    Returns:
        dict: Lighting data
    """
    
    mapper = ColorMapper()
    return mapper.map_to_colors(base_color, hue_speed)

def generate_lighting_show(color_data_list: List[Tuple[tuple, float]], duration_per_step: float = 2.0) -> List[Dict]:
    """
    Generate a sequence of lighting commands for a show
    
    Args:
        color_data_list (list): List of (color, hue_speed) tuples
        duration_per_step (float): Duration of each step in seconds
        
    Returns:
        list: Sequence of lighting commands
    """
    
    mapper = ColorMapper()
    show_sequence = []
    
    start_time = time.time()
    
    for i, (color, hue_speed) in enumerate(color_data_list):
        step_time = start_time + (i * duration_per_step)
        lighting_data = mapper.map_to_colors(color, hue_speed, step_time)
        
        lighting_data["step"] = i + 1
        lighting_data["duration"] = duration_per_step
        show_sequence.append(lighting_data)
    
    return show_sequence

# For testing
if __name__ == "__main__":
    # Test color mapping
    test_color = (255, 100, 50)  # Orange-ish
    test_speed = 1.2
    
    result = map_to_colors(test_color, test_speed)
    print("Lighting data:", result)
    
    # Test show generation
    test_sequence = [
        ((255, 0, 0), 0.5),    # Red, slow
        ((0, 255, 0), 1.0),    # Green, medium
        ((0, 0, 255), 1.8),    # Blue, fast
    ]
    
    show = generate_lighting_show(test_sequence)
    print(f"Generated {len(show)} lighting steps")

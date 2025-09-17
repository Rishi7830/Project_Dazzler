import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw

def display_genre():
    """This function retrieves the genre from the combobox and displays it."""
    genre = genre_var.get()
    if genre:
        label.config(text=f"🎵 You selected: {genre}")
    else:
        label.config(text="")

# Create the main window
root = tk.Tk()
root.title("Dazzler Dashboard")
root.geometry("800x600")

# Image Loading and Background Setup
image_path = r"C:\Users\Rishi Moorthy\Desktop\dazzler\image.jpg"

try:
    pil_image = Image.open(image_path).resize((800, 600)).convert("RGBA")

    overlay = pil_image.copy()

    draw = ImageDraw.Draw(overlay, "RGBA")
    box_x1, box_y1 = 180, 330   # top-left corner
    box_x2, box_y2 = 620, 520   # bottom-right corner
    draw.rectangle([box_x1, box_y1, box_x2, box_y2], fill=(255, 255, 255, 160))  # RGBA (white, 160 alpha)

    # Blend overlay with original background
    blended = Image.alpha_composite(pil_image, overlay)
    background_image = ImageTk.PhotoImage(blended)

    background_label = tk.Label(root, image=background_image)
    background_label.place(x=0, y=0, relwidth=1, relheight=1)
    background_label.image = background_image
except Exception as e:
    print(f"Error loading image: {e}")

# Genre Options
genres = [
    "Blues", "Classical", "Country", "Electronica and Dance",
    "Folk", "Gospel", "Hip-Hop and Rap", "Indie", "Jazz",
    "Latin", "Metal", "Pop", "Reggae", "Rock", "Soul"
]

# Custom Styles
style = ttk.Style()
style.theme_use("clam")

# Combobox Style
style.configure("TCombobox",
                fieldbackground="white",
                background="lightgray",
                foreground="black",
                arrowcolor="black",
                font=("Helvetica", 12))

# Button Style
style.configure("Cool.TButton",
                font=("Helvetica", 12, "bold"),
                foreground="white",
                background="#4A90E2",
                padding=6)
style.map("Cool.TButton",
          background=[("active", "#357ABD")])  

# Dashboard Elements
# Title with shadow effect
shadow_label = tk.Label(root, text="Dazzler Dashboard",
                        font=("Helvetica", 20, "bold"),
                        fg="black", bg="white")   # shadow layer
shadow_label.place(relx=0.502, rely=0.48, anchor=tk.CENTER)

title_label = tk.Label(root, text="Dazzler Dashboard",
                       font=("Helvetica", 20, "bold"),
                       fg="#4A90E2", bg="white")   # main title
title_label.place(relx=0.5, rely=0.475, anchor=tk.CENTER)

# Instruction
instruction_label = tk.Label(root, text="Select your music genre:",
                             font=("Helvetica", 14, "bold"),
                             bg="white", fg="black")
instruction_label.place(relx=0.5, rely=0.63, anchor=tk.CENTER)

# Dropdown menu (Combobox)
genre_var = tk.StringVar()
genre_dropdown = ttk.Combobox(root, textvariable=genre_var,
                              values=genres, font=("Helvetica", 12),
                              state="readonly", width=28)
genre_dropdown.place(relx=0.5, rely=0.70, anchor=tk.CENTER)

# Button
button = ttk.Button(root, text="Submit 🎶", command=display_genre,
                    style="Cool.TButton")
button.place(relx=0.5, rely=0.77, anchor=tk.CENTER)

# Output Label
label = tk.Label(root, text="", font=("Helvetica", 14, "italic"),
                 fg="darkblue", bg="white")
label.place(relx=0.5, rely=0.85, anchor=tk.CENTER)

root.mainloop()






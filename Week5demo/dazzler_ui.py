import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw
import random

# Helper Classes
class ToolTip:
    """Create a tooltip for a given widget."""
    def __init__(self, widget, text="Tooltip"):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        widget.bind("<Enter>", self.show_tooltip)
        widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20
        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, background="lightyellow",
                         relief="solid", borderwidth=1,
                         font=("Helvetica", 10))
        label.pack(ipadx=4, ipady=2)

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None


# Main Application
class DazzlerDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Dazzler Dashboard")
        self.root.geometry("800x600")

        # Music fun facts
        self.music_facts = [
            "The world's largest playable guitar is over 43 feet long!",
            "Mozart composed over 600 works before his death at 35.",
            "The longest drumming marathon lasted over 122 hours!",
            "The most expensive musical instrument sold was a Stradivarius violin at $15.9 million.",
            "The Beatles hold the record for most number-one hits on the Billboard Hot 100."
        ]

        # Load background
        self.load_background()

        # Add menu bar
        self.create_menu()

        # Create main content box
        self.create_ui_box()

        # Create status bar
        self.create_status_bar()

    # UI Setup
    def load_background(self):
        """Load and place background with translucent overlay."""
        image_path = r"C:\Users\Rishi Moorthy\Desktop\dazzler\image.jpg" #change directory to image
        try:
            pil_image = Image.open(image_path).resize((800, 600)).convert("RGBA")
            overlay = pil_image.copy()
            draw = ImageDraw.Draw(overlay, "RGBA")
            draw.rectangle([180, 330, 620, 520], fill=(255, 255, 255, 160))
            blended = Image.alpha_composite(pil_image, overlay)
            background_image = ImageTk.PhotoImage(blended)
            self.background_label = tk.Label(self.root, image=background_image)
            self.background_label.image = background_image
            self.background_label.place(x=0, y=0, relwidth=1, relheight=1)
        except Exception as e:
            print(f"Error loading image: {e}")

    def create_menu(self):
        """Menu bar with basic options."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New", command=lambda: self.show_message("New File"))
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

    def create_ui_box(self):
        """Main interactive UI box with labels, dropdown, and button."""
        genres = [
            "Blues", "Classical", "Country", "Electronica and Dance",
            "Folk", "Gospel", "Hip-Hop and Rap", "Indie", "Jazz",
            "Latin", "Metal", "Pop", "Reggae", "Rock", "Soul"
        ]

        # Styles
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground="white", background="lightgray",
                        foreground="black", arrowcolor="black", font=("Helvetica", 12))
        style.configure("Cool.TButton", font=("Helvetica", 12, "bold"),
                        foreground="white", background="#4A90E2", padding=6)
        style.map("Cool.TButton", background=[("active", "#357ABD")])

        # Title
        shadow = tk.Label(self.root, text="Dazzler Dashboard",
                          font=("Helvetica", 20, "bold"), fg="black", bg="white")
        shadow.place(relx=0.502, rely=0.48, anchor=tk.CENTER)

        self.title_label = tk.Label(self.root, text="Dazzler Dashboard",
                                    font=("Helvetica", 20, "bold"),
                                    fg="#4A90E2", bg="white")
        self.title_label.place(relx=0.5, rely=0.475, anchor=tk.CENTER)

        # Instruction
        instruction = tk.Label(self.root, text="Select your favorite music genre:",
                               font=("Helvetica", 14, "bold"),
                               bg="white", fg="black")
        instruction.place(relx=0.5, rely=0.63, anchor=tk.CENTER)

        # Dropdown
        self.genre_var = tk.StringVar()
        self.genre_dropdown = ttk.Combobox(self.root, textvariable=self.genre_var,
                                           values=genres, font=("Helvetica", 12),
                                           state="readonly", width=28)
        self.genre_dropdown.place(relx=0.5, rely=0.70, anchor=tk.CENTER)

        ToolTip(self.genre_dropdown, "Pick a music genre from the list!")

        # Button
        self.button = ttk.Button(self.root, text="Submit 🎶",
                                 command=self.display_genre,
                                 style="Cool.TButton")
        self.button.place(relx=0.5, rely=0.77, anchor=tk.CENTER)
        ToolTip(self.button, "Click to confirm your choice")

        # Output label
        self.output_label = tk.Label(self.root, text="", font=("Helvetica", 14, "italic"),
                                     fg="darkblue", bg="white")
        self.output_label.place(relx=0.5, rely=0.85, anchor=tk.CENTER)

        # Fun fact label
        self.fact_label = tk.Label(self.root, text="", font=("Helvetica", 11),
                                   fg="darkgreen", bg="white", wraplength=600,
                                   justify="center")
        self.fact_label.place(relx=0.5, rely=0.92, anchor=tk.CENTER)

    def create_status_bar(self):
        """Status bar at the bottom."""
        self.status_var = tk.StringVar(value="Ready")
        status = tk.Label(self.root, textvariable=self.status_var,
                          bd=1, relief="sunken", anchor="w",
                          font=("Helvetica", 9))
        status.pack(side="bottom", fill="x")

    # Functionalities
    def display_genre(self):
        """Show selected genre and random fact."""
        genre = self.genre_var.get()
        if genre:
            self.output_label.config(text=f"🎵 You selected: {genre}")
            fact = random.choice(self.music_facts)
            self.fact_label.config(text=f"Fun Fact: {fact}")
            self.status_var.set(f"Genre '{genre}' selected successfully!")
        else:
            self.output_label.config(text="")
            self.fact_label.config(text="")
            self.status_var.set("No genre selected.")

    def show_message(self, msg):
        messagebox.showinfo("Info", msg)

    def show_about(self):
        messagebox.showinfo("About",
                            "Dazzler Dashboard\n\n Automate Stage Lighting.")


# Run App
if __name__ == "__main__":
    root = tk.Tk()
    app = DazzlerDashboard(root)
    root.mainloop()

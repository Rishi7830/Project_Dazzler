import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw
import random
import os

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
        # Adjusted placement slightly to avoid covering the cursor
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
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
        image_path = r"C:\Users\Rishi Moorthy\Desktop\dazzler\image.jpg"
        
        self.label_bg_color = "#E5E5E5" 
        
        try:
            pil_image = Image.open(image_path).resize((800, 600)).convert("RGBA")
            overlay = pil_image.copy()
            draw = ImageDraw.Draw(overlay, "RGBA")
            
            
            blended = Image.alpha_composite(pil_image, overlay)
            background_image = ImageTk.PhotoImage(blended)
            self.background_label = tk.Label(self.root, image=background_image)
            self.background_label.image = background_image
            self.background_label.place(x=0, y=0, relwidth=1, relheight=1)
        except Exception as e:

            self.background_label = tk.Label(self.root, bg="#DDDDDD")
            self.background_label.place(x=0, y=0, relwidth=1, relheight=1)
            self.label_bg_color = "#DDDDDD" 
            print(f"Error loading image. Using solid background: {e}")

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
        """Main interactive UI box with labels, dropdowns, and buttons."""
        genres = [
            "Blues", "Classical", "Country", "Electronica and Dance",
            "Folk", "Gospel", "Hip-Hop and Rap", "Indie", "Jazz",
            "Latin", "Metal", "Pop", "Reggae", "Rock", "Soul"
        ]

        # Styles
        style = ttk.Style()
        style.theme_use("clam")
        
        # Style for Combobox (Genre)
        style.configure("TCombobox", fieldbackground="white", background="lightgray",
                         foreground="black", arrowcolor="black", font=("Helvetica", 12))
        
        # Style for Entry (COM Port, Song Name)
        style.configure("TEntry", fieldbackground="white", foreground="black",
                        insertcolor="black", font=("Helvetica", 12))
        
        # Style for the master submit button
        style.configure("Master.TButton", font=("Helvetica", 12, "bold"),
                         foreground="white", background="#4CAF50", padding=8) 
        style.map("Master.TButton", background=[("active", "#388E3C")]) 

        # Input Fields
        start_y = 0.35 
        y_step = 0.08
        
        # Genre Input (Dropdownn)
        tk.Label(self.root, text="Select Music Genre:",
                 font=("Helvetica", 12, "bold"), bg=self.label_bg_color, fg="black").place(relx=0.5, rely=start_y, anchor=tk.CENTER)
        
        self.genre_var = tk.StringVar()
        self.genre_dropdown = ttk.Combobox(self.root, textvariable=self.genre_var,
                                           values=genres, font=("Helvetica", 12),
                                           state="readonly", width=30)
        self.genre_dropdown.place(relx=0.5, rely=start_y + y_step, anchor=tk.CENTER)
        ToolTip(self.genre_dropdown, "Pick a music genre from the list!")
        
        # COM Port Input
        com_port_y = start_y + 2 * y_step
        
        tk.Label(self.root, text="Enter COM Port (e.g., COM3):",
                 font=("Helvetica", 12, "bold"), bg=self.label_bg_color, fg="black").place(relx=0.5, rely=com_port_y, anchor=tk.CENTER)
        
        self.com_port_var = tk.StringVar(value="COM3") 
        self.com_port_entry = ttk.Entry(self.root, textvariable=self.com_port_var,
                                        style="TEntry", width=32)
        self.com_port_entry.place(relx=0.5, rely=com_port_y + y_step, anchor=tk.CENTER)
        ToolTip(self.com_port_entry, "Specify the COM port for the lighting controller.")

        # Song Name Input
        song_name_y = start_y + 4 * y_step
        
        tk.Label(self.root, text="Enter Song Name/Path:",
                 font=("Helvetica", 12, "bold"), bg=self.label_bg_color, fg="black").place(relx=0.5, rely=song_name_y, anchor=tk.CENTER)
        
        self.song_name_var = tk.StringVar(value="My_Amazing_Track.mp3") 
        self.song_name_entry = ttk.Entry(self.root, textvariable=self.song_name_var,
                                         style="TEntry", width=32)
        self.song_name_entry.place(relx=0.5, rely=song_name_y + y_step, anchor=tk.CENTER)
        ToolTip(self.song_name_entry, "Type the name or path of the song file.")

        # Master Submit Button (Green)
        submit_y = start_y + 6 * y_step - 0.01 
        
        self.master_button = ttk.Button(self.root, text="Start Dazzling!",
                                         command=self.master_submit,
                                         style="Master.TButton")
        self.master_button.place(relx=0.5, rely=submit_y, anchor=tk.CENTER)
        ToolTip(self.master_button, "Click to submit all data and start automation.")

        # Output/Fact Labels
        output_y = submit_y + 0.06 
        fact_y = output_y + 0.05   
        
        # Output label
        self.output_label = tk.Label(self.root, text="", font=("Helvetica", 12, "italic"),
                                     fg="darkblue", bg=self.label_bg_color)
        self.output_label.place(relx=0.5, rely=output_y, anchor=tk.CENTER)

        # Fun fact label
        self.fact_label = tk.Label(self.root, text="", font=("Helvetica", 10),
                                   fg="darkgreen", bg=self.label_bg_color, wraplength=600,
                                   justify="center")
        self.fact_label.place(relx=0.5, rely=fact_y, anchor=tk.CENTER)

    def create_status_bar(self):
        """Status bar at the bottom."""
        self.status_var = tk.StringVar(value="Ready")
        status = tk.Label(self.root, textvariable=self.status_var,
                          bd=1, relief="sunken", anchor="w",
                          font=("Helvetica", 9))
        status.pack(side="bottom", fill="x")

    # Functionalities
    def master_submit(self):
        """Collects all inputs and simulates the start of the automation process."""
        genre = self.genre_var.get()
        com_port = self.com_port_var.get()
        song_name = self.song_name_var.get()
        
        if not all([genre, com_port, song_name]):
            messagebox.showwarning("Incomplete Data", "Please ensure a **Genre**, **COM Port**, and **Song Name** are all entered.")
            self.status_var.set("Submission failed: Missing input.")
            return

        # Display all collected data
        self.output_label.config(text=f"Selected: Genre='{genre}' | Port='{com_port}' | Song='{song_name}'")

        # Show a random fun fact
        fact = random.choice(self.music_facts)
        self.fact_label.config(text=f"Fun Fact: {fact}")
        
        # Update status bar
        self.status_var.set(f"All data submitted. Starting automation for '{song_name}' on {com_port} with {genre} profile.")

    def show_message(self, msg):
        messagebox.showinfo("Info", msg)

    def show_about(self):
        messagebox.showinfo("About",
                            "Dazzler Dashboard\n\nAutomate Stage Lighting.")


# Run App
if __name__ == "__main__":
    root = tk.Tk()
    app = DazzlerDashboard(root)
    root.mainloop()

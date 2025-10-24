# run_pipeline.py

import multiprocessing
import os
import time
from pathlib import Path

# Import necessary functions and classes from your existing scripts
from dazzler_ui import DazzlerDashboard
from audio_playback import play_audio
from main_dashboard import stream_mp3_realtime, init_dmx_controller
import tkinter as tk

def run_ui_and_get_inputs():
    """
    Launches the DazzlerDashboard UI and waits for the user to submit the required information.
    This function will block until the UI is closed or submitted.
    """
    root = tk.Tk()
    app = DazzlerDashboard(root)
    app.submission_successful = False

    def master_submit_and_close():
        """Modified submit action for multiprocessing."""
        app.master_submit()
        if app.genre_var.get() and app.com_port_var.get() and app.song_name_var.get():
            app.submission_successful = True
            root.quit()  # Stop the mainloop to return control
        else:
            print("UI validation failed. Please check inputs.")

    app.master_button.config(command=master_submit_and_close)
    root.mainloop()

    if app.submission_successful:
        # Retrieve data from the UI instance
        user_inputs = {
            "genre": app.genre_var.get().lower(),
            "filepath": app.song_name_var.get().strip().strip('"'),
            "dmx_port": app.com_port_var.get().strip(),
        }
        root.destroy()
        return user_inputs
    else:
        root.destroy()
        return None

if __name__ == "__main__":
    # This is essential for multiprocessing to work correctly
    multiprocessing.freeze_support()

    # 1. Get user inputs from the UI in the main process
    print("🚀 Launching Dazzler Dashboard...")
    user_inputs = run_ui_and_get_inputs()

    if not user_inputs:
        print("\n[END] Operation cancelled from the UI. Exiting.")
    else:
        # Unpack the inputs
        selected_genre = user_inputs["genre"]
        mp3_file_path = user_inputs["filepath"]
        dmx_port = user_inputs["dmx_port"]

        # Validate file path before starting processes
        if not os.path.exists(Path(mp3_file_path).expanduser()):
            print(f"\n[ERROR] File not found: {mp3_file_path}. Please restart and provide a valid path.")
        else:
            print("\n--- Configuration Summary ---")
            print(f"🎶 Song: {mp3_file_path}")
            print(f"🎨 Genre: {selected_genre.title()}")
            print(f"💡 DMX Port: {dmx_port}")
            print("-----------------------------\n")

            # Initialize DMX controller
            dmx = init_dmx_controller(port=dmx_port)

            try:
                # 2. Create separate processes for playback and analysis
                print("Preparing processes for audio playback and analysis...")

                # Process for audio playback
                playback_process = multiprocessing.Process(
                    target=play_audio,
                    args=(mp3_file_path,)
                )

                # Process for real-time analysis and DMX control
                analysis_process = multiprocessing.Process(
                    target=stream_mp3_realtime,
                    args=(mp3_file_path, dmx, selected_genre)
                )

                print("\n[START] Starting audio playback and lighting analysis...")
                print("Press Ctrl+C in this terminal to stop all processes.")

                # 3. Start the processes
                # We start analysis slightly before playback to prepare the stream
                analysis_process.start()
                time.sleep(1) # Give it a moment to initialize
                playback_process.start()

                # 4. Wait for the processes to complete
                # The main script will wait here. You can stop everything with Ctrl+C.
                analysis_process.join()
                playback_process.join()

            except KeyboardInterrupt:
                print("\n[STOP] Keyboard interrupt detected. Terminating processes...")
            finally:
                # Ensure all child processes are terminated
                if 'playback_process' in locals() and playback_process.is_alive():
                    playback_process.terminate()
                    playback_process.join()
                if 'analysis_process' in locals() and analysis_process.is_alive():
                    analysis_process.terminate()
                    analysis_process.join()

                # Cleanly shut down the DMX controller
                dmx.stop_broadcast()
                dmx.close()
                print("\n[END] All processes terminated and DMX port closed. Goodbye!")

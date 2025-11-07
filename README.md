# Dazzler: Music‑aware DMX lighting, live and file-based.​

What is Dazzler
Dazzler listens to music and drives stage lights in real time, prioritizing musical feel over canned cues. It maps audio features like loudness and banded onsets to colors, strobes, and movement so looks “breathe” with the song.​

Two ways to run
DEMO (MP3 files): Run the full pipeline on a local audio file to see end‑to‑end behavior without a mixer. Good for first-time setup and reproducible tests.​

LIVE DEMO (Mixer input): Drive lights from a live input device (your audio interface/mixer) for on‑stage responsiveness and timing. Great for jams and shows.​

Quick start
Clone and set up a virtual environment, then install requirements (Python 3.10+ recommended).​

Connect your USB‑to‑DMX adapter; if none is available, the app can run in a safe “noop” mode so you can still verify analysis and logs.​

Choose DEMO for MP3 or LIVE DEMO for a mixer device; follow the prompts to pick source, genre preset, fixture profile, and DMX port.​

Requirements
Python packages: librosa, numpy, sounddevice (plus standard scientific stack).​

Hardware: any USB‑DMX adapter; pro interfaces (e.g., ENTTEC) improve reliability, but simple adapters work for testing.​

Running the demos
DEMO (MP3):

Launch the demo script and select “File” as the source, then provide a path to your MP3. The pipeline analyzes the track in short windows, generates onsets and novelty, and drives DMX frames accordingly.​

Use this mode to validate mapping and colors, or to record fixtures’ responses without live inputs.​

LIVE DEMO (Mixer):

Launch the live demo and select your input device by index/name. The system levels the live signal and reacts with low latency to banded onsets, then renders DMX in lockstep.​

If you see silence or device errors, pick a valid capture device and confirm levels; common issues include invalid IDs or muted channels.​

What you’ll see
LEDs/fixtures syncing to kicks, hats, and section hits with clean one‑shot triggers rather than flurries.​

Wash color and intensity that track mood and energy, with strobe pops on crisp moments and palette changes tied to structure.​

Tips for a smooth run
Start with DEMO to confirm features and mappings; move to LIVE DEMO once basics look right. This avoids chasing device problems while tuning visuals.​

If DMX isn’t connected, keep noop mode on to iterate safely; switch to hardware once visuals feel good.​

Contributing
Open an issue for bugs and feature requests; share device info (OS, audio device ID, DMX port) and a short log to help reproduce.​

Pull requests that improve stability, reduce latency, or enhance musical feel are welcome; small, focused changes merge fastest.​

Why this exists
The goal is a rig that feels like part of the band: fewer menus, more music, and a show that reacts honestly to what’s being played instead of chasing prebuilt timelines.

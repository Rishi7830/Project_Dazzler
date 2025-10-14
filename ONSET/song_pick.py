#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv, re
from pathlib import Path
import pandas as pd

# IMPORTANT: set to the repo root (folder containing 'metadata.csv' and 'annotations/')
ROOT = Path('salami-data-public')  # <-- update to absolute path if needed

OUT = Path('./dataset_rock15')
(OUT / 'annotations').mkdir(parents=True, exist_ok=True)
(OUT / 'audio').mkdir(parents=True, exist_ok=True)

meta = pd.read_csv(ROOT / 'metadata.csv')

def is_rock_row(r):
    text = ' '.join(str(r.get(col,'')) for col in ['GENRE','CLASS','SOURCE','SONG_TITLE','ARTIST']).lower()
    return 'rock' in text

cand = meta[meta.apply(is_rock_row, axis=1)]
print('Rock candidates:', len(cand))

def parse_lines_simple(path: Path):
    txt = path.read_text(encoding='utf-8', errors='ignore')
    pairs = []
    for ln in txt.splitlines():
        s = ln.strip()
        if not s:
            continue
        parts = re.split(r'\s+', s, maxsplit=2)
        if len(parts) == 2:
            try:
                t = float(parts[0]); lab = parts[1]; pairs.append((t, lab))
            except:
                pass
        elif len(parts) >= 3:
            try:
                t = float(parts[0]); lab = parts[2]; pairs.append((t, lab))
            except:
                pass
    pairs = sorted({(round(t,6), lab) for t, lab in pairs})
    return pairs

def find_functions_path_unpadded(sid_str: str):
    base = ROOT / 'annotations' / sid_str / 'parsed'
    if not base.exists():
        return None
    # Try exact names you specified
    candidates = [
        base / 'textfile2_functions',
        base / 'textfile2_functions.txt',
        base / 'textfile1_functions',
        base / 'textfile1_functions.txt',
        base / 'functions',
        base / 'functions.txt'
    ]
    for p in candidates:
        if p.exists():
            return p
    # Fallback: any file containing 'function' in its name
    hits = sorted([p for p in base.iterdir() if p.is_file() and 'function' in p.name.lower()])
    return hits[0] if hits else None

checked = []
picked = []
for _, r in cand.iterrows():
    sid = int(r['SONG_ID'])
    sid_str = str(sid)  # unpadded directory name
    use = find_functions_path_unpadded(sid_str)
    checked.append((sid_str, str(use) if use else '(none)', bool(use)))
    if use is None:
        continue
    pairs = parse_lines_simple(use)
    if len(pairs) < 4:
        continue
    outp = (OUT / 'annotations' / f'{sid_str}_functions.txt')
    with outp.open('w', encoding='utf-8') as f:
        for t, lab in pairs:
            f.write(f'{t}\t{lab}\n')
    picked.append({
        'SONG_ID': sid_str,
        'annotator': 'annotator2' if use.name.startswith('textfile2') else ('annotator1' if use.name.startswith('textfile1') else 'unknown'),
        'ann_src_path': str(use.relative_to(ROOT)),
        'ann_saved_path': str(outp.resolve()),
        'artist': r.get('ARTIST',''),
        'title': r.get('SONG_TITLE',''),
        'genre': r.get('GENRE',''),
        'class': r.get('CLASS',''),
        'expected_audio_path': str((OUT / 'audio' / f'{sid_str}.mp3').resolve()),
    })
    if len(picked) >= 15:
        break

print(f'Saved {len(picked)} tracks to {OUT / "annotations"}')

if not picked:
    print('Diagnostics (first 30 Rock IDs checked):')
    for sid_str, path_str, ok in checked[:30]:
        print(f'{sid_str}: exists={ok} path={path_str}')
else:
    man_csv = OUT / 'manifest_rock15.csv'
    with open(man_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(picked[0].keys()))
        w.writeheader(); w.writerows(picked)
    print('Manifest:', man_csv)
    for row in picked:
        print(f"{row['SONG_ID']} | {row['annotator']} | {row['ann_src_path']} -> {row['ann_saved_path']}")
        print('Put MP3 at:', row['expected_audio_path'])

import numpy as np, pandas as pd
from pathlib import Path
import essentia.standard as es

# Config
ANN_DIR = Path('annotations')
AUDIO_DIR = Path('audio')

def frame_loudness_db(frame):
    import numpy as np
    rms = np.sqrt(np.mean(frame**2) + 1e-12)
    return 20*np.log10(rms + 1e-12)

def extract_hfc_loudness(path, frame_size=1024, hop_size=512):
    loader = es.MonoLoader(filename=str(path))
    audio = loader(); sr = loader.paramValue('sampleRate')
    w = es.Windowing(type='hann'); fft = es.FFT(); c2p = es.CartesianToPolar(); od = es.OnsetDetection(method='hfc')
    frames = list(es.FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size, startFromZero=True))
    hfc, loud = [], []
    for fr in frames:
        mag, ph = c2p(fft(w(fr)))
        hfc.append(od(mag, ph))
        loud.append(frame_loudness_db(fr))
    hfc = np.array(hfc); loud = np.array(loud)
    times = np.arange(len(hfc)) * (hop_size / sr)
    # causal smoothing
    def ema(x, tau_sec):
        a = (hop_size/sr) / max(tau_sec, hop_size/sr)
        y = np.empty_like(x, dtype=float); acc = None
        for i, xi in enumerate(x):
            acc = xi if acc is None else a*xi + (1-a)*acc
            y[i] = acc
        return y
    hfc_f = ema(hfc, 0.25); hfc_s = ema(hfc, 1.0); loud_s = ema(loud, 0.25)
    return times, hfc_f, hfc_s, loud_s

def novelty_detect(times, hfc_f, hfc_s, loud_s, weights=(0.6,0.2,0.2), percentile=85, pre=1.0, post=0.8, min_space=5.0):
    def diff_abs(x):
        if len(x) < 2: return np.zeros_like(x)
        d = np.abs(np.diff(x)); return np.concatenate([[d[0]], d])
    d1, d2, d3 = diff_abs(hfc_f), diff_abs(hfc_s), diff_abs(loud_s)
    w1,w2,w3 = weights
    nov = w1*d1 + w2*d2 + w3*d3
    hop = times[1]-times[0] if len(times)>1 else 0.01
    # rolling percentile threshold
    win = max(1, int(15.0 / hop))
    thr = np.zeros_like(nov)
    from collections import deque
    buf = deque(maxlen=win)
    for i,v in enumerate(nov):
        buf.append(v); thr[i] = np.percentile(np.array(buf), percentile)
    # candidates
    min_dist = max(1, int(min_space / hop))
    import scipy.signal as ss
    idx, _ = ss.find_peaks(nov, distance=min_dist)
    idx = [i for i in idx if nov[i] > thr[i]]
    # confirm pre/post
    preN, postN = max(1,int(pre/hop)), max(1,int(post/hop))
    med = np.median(hfc_f); mad = np.median(np.abs(hfc_f-med))+1e-8
    out = []
    for i in idx:
        a=max(0,i-preN); b=i; c=i; d=min(len(hfc_f), i+postN)
        if b<=a or d<=c: continue
        hj = abs(np.mean(hfc_f[c:d]) - np.mean(hfc_f[a:b]))/mad
        lj = abs(np.mean(loud_s[c:d]) - np.mean(loud_s[a:b]))
        if hj>=0.8 or lj>=1.5:
            out.append(times[i])
    return np.array(out)

def load_truth(ann_path):
    # lines: time \t label
    ts = []
    for ln in Path(ann_path).read_text(encoding='utf-8', errors='ignore').splitlines():
        parts = ln.strip().split()
        if not parts: continue
        try:
            ts.append(float(parts[0]))
        except: pass
    return np.array(sorted(set(ts)))

def fmetrics(det, tru, tol):
    if len(tru)==0: return (0,0,0)
    used = set(); m=0
    for d in det:
        j = np.argmin(np.abs(tru - d))
        if abs(tru[j]-d)<=tol and j not in used:
            used.add(j); m+=1
    P = m/max(1,len(det)); R = m/max(1,len(tru)); F = 0 if P+R==0 else 2*P*R/(P+R)
    return (P,R,F)

# Gather IDs from saved annotations
ids = sorted([p.stem.replace('_functions','') for p in ANN_DIR.glob('*_functions.txt')])

rows=[]
for sid in ids:
    ann = ANN_DIR / f'{sid}_functions.txt'
    aud = AUDIO_DIR / f'{sid}.mp3'
    if not aud.exists(): 
        print('Missing audio:', aud); continue
    t, hf, hs, ls = extract_hfc_loudness(aud)
    truth = load_truth(ann)
    # small grid
    configs = [((0.6,0.2,0.2),85), ((0.5,0.3,0.2),85), ((0.5,0.2,0.3),85), ((0.6,0.2,0.2),90)]
    best=None; bestF=-1
    for w,pct in configs:
        det = novelty_detect(t,hf,hs,ls,weights=w,percentile=pct)
        P05,R05,F05 = fmetrics(det, truth, 0.5)
        P3,R3,F3 = fmetrics(det, truth, 3.0)
        if F3>bestF:
            bestF=F3; best=(w,pct,P05,R05,F05,P3,R3,F3)
    rows.append((sid,)+best)

df = pd.DataFrame(rows, columns=['SONG_ID','weights','percentile','P@0.5','R@0.5','F@0.5','P@3','R@3','F@3'])
print(df)
print('Mean F@3:', df['F@3'].mean())
win = df.sort_values('F@3', ascending=False).head(5)
print('Top configs (per-song best):')
print(win)

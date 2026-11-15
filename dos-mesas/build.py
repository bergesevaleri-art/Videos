#!/usr/bin/env python3
"""Reel "lo simple en gris es superior": genera index.html, la música (120 bpm) y los efectos.

Todo sale de una grilla de 120 bpm (un tiempo = 0.5 s): los cortes caen en el pulso, cada letra
escrita tiene su golpe de tecla y las transiciones su whoosh.

Uso: python3 build.py   (desde la carpeta dos-mesas/)
"""
import html
import json
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
SR = 44100
BEAT = 0.5
DUR = 18.0
PUSH = 0.3

# ---------------------------------------------------------------- grilla
HOOK = [("f1", 0.0), ("f2", 0.5), ("f3", 1.0), ("f4", 1.5), ("f5", 2.0)]   # cortes flash de 0.5 s
MESAS = [
    # título, inicio, tomas (clip, duración), una palabra por corte
    ("gris + natural", 2.5, [("m1a", 1.0), ("m1b", 1.5), ("m1c", 1.0), ("m1d", 1.5), ("m1e", 1.0)],
     ["simple", "cálido", "atemporal", "combina con todo", "nunca aburre"]),
    ("gris + cuadrillé", 8.5, [("m2a", 1.5), ("m2b", 1.0), ("m2c", 1.5), ("m2d", 1.0), ("m2e", 1.0)],
     ["fresco", "prolijo", "para todos los días", "con onda", "siempre elegante"]),
]
START = MESAS[0][1]
SPLIT, SPLIT_END = 14.5, 18.0
CIERRE = SPLIT_END


def typed(text, start, step):
    out, t = [], start
    for ch in text:
        out.append(round(t, 3))
        t += step * (0.5 if ch == " " else 1)
    return out


# Un solo texto en el centro y una frase de cierre; las palabras con * van en cursiva.
SENAL = [["esta es tu ", "*señal"], ["para renovar tu ", "*vajilla"]]
FRASE = [["lo simple en ", "*gris"], ["es superior"]]
SENAL_T0, TECLA = 0.15, 0.045
FRASE_T = SPLIT + 0.4                    # aparece con los brillitos


def chars(lines):
    """Letras en orden, con su marca de cursiva."""
    out = []
    for li, parts in enumerate(lines):
        for part in parts:
            acc = part.startswith("*")
            for ch in part.lstrip("*"):
                out.append((li, ch, acc))
    return out


senal_chars = chars(SENAL)
senal_t, t = [], SENAL_T0
for _, ch, _ in senal_chars:
    senal_t.append(round(t, 3))
    t += TECLA * (0.5 if ch == " " else 1)

# ---------------------------------------------------------------- audio
rng = np.random.default_rng(11)


def load(name):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(ROOT / "assets/sfx" / name), "-ac", "2", "-ar", str(SR),
                          "-f", "f32le", "-"], check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy()


def place(buf, clip, t, gain=1.0):
    i = int(t * SR)
    n = min(len(clip), len(buf) - i)
    if n > 0:
        buf[i:i + n] += clip[:n] * gain


def write_m4a(buf, name, rms_db=None, peak=0.89):
    if rms_db is not None:
        rms = np.sqrt(np.mean(buf ** 2)) or 1
        buf = buf * (10 ** (rms_db / 20) / rms)
        buf = np.tanh(buf / peak) * peak            # limitador suave
    else:
        buf = buf / (np.max(np.abs(buf)) or 1) * peak
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "aac", "-b:a", "192k", str(ROOT / "assets/audio" / name)],
                   input=buf.astype(np.float32).tobytes(), check=True)


# efectos
sfx = np.zeros((int(DUR * SR), 2), dtype=np.float32)
key, pop, wsh, clk = load("key-press.mp3"), load("pop.mp3"), load("whoosh-short.mp3"), load("click-soft.mp3")
for (_, ch, _), t in zip(senal_chars, senal_t):
    if ch != " ":
        place(sfx, key, t, 0.5 * rng.uniform(0.8, 1.0))
for _, t in HOOK[1:]:
    place(sfx, clk, t, 0.5)
for _, s, shots, _ in MESAS:
    place(sfx, pop, s, 0.6)
    t = s
    for _, d in shots[:-1]:
        t += d
        place(sfx, clk, t, 0.35)
for b in (MESAS[1][1], SPLIT):
    place(sfx, wsh, b - PUSH - 0.05, 0.8)
place(sfx, load("sparkle.mp3"), FRASE_T - 0.05, 0.75)   # brillitos de la frase final
write_m4a(sfx, "sfx.m4a")

# música original, 120 bpm, pensada para que se escuche bien en el parlante del celular
mus = np.zeros((int(DUR * SR), 2), dtype=np.float32)


def hz(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def put(sig, t, pan=0.0, g=1.0):
    i = int(t * SR)
    n = min(len(sig), len(mus) - i)
    if n > 0:
        mus[i:i + n, 0] += sig[:n] * g * (1 - pan)
        mus[i:i + n, 1] += sig[:n] * g * (1 + pan)


def pluck(f, dur=0.5):
    n, p = int(dur * SR), max(2, int(SR / f))
    buf, out = rng.uniform(-1, 1, p), np.zeros(int(dur * SR))
    for i in range(n):
        out[i] = buf[i % p]
        buf[i % p] = 0.5 * (buf[i % p] + buf[(i + 1) % p]) * 0.994
    return out.astype(np.float32)


def stab(notes, dur=0.35):
    t = np.arange(int(dur * SR)) / SR
    s = sum(np.sign(np.sin(2 * np.pi * hz(n) * t)) * 0.3 + np.sin(2 * np.pi * hz(n) * t) for n in notes)
    return (s * np.exp(-t / 0.12) * np.minimum(t / 0.004, 1) / len(notes)).astype(np.float32)


def kick():
    t = np.arange(int(0.3 * SR)) / SR
    return (np.sin(2 * np.pi * (48 + 90 * np.exp(-t / 0.025)) * t) * np.exp(-t / 0.13)).astype(np.float32)


def clap():
    t = np.arange(int(0.2 * SR)) / SR
    n = rng.normal(0, 1, len(t))
    n = np.convolve(n, [1, -0.9], "same")                     # más brillo
    env = np.exp(-t / 0.06) * (1 + 0.6 * (np.sin(2 * np.pi * 90 * t) > 0))
    return (n * env * 0.5).astype(np.float32)


def hat():
    t = np.arange(int(0.06 * SR)) / SR
    return (np.diff(rng.normal(0, 1, len(t) + 1)) * np.exp(-t / 0.012) * 0.35).astype(np.float32)


# Am7  Fmaj7  C  G  (un acorde por compás de 2 s)
CH = [[57, 60, 64, 67], [53, 57, 60, 64], [48, 52, 55, 60], [55, 59, 62, 67]]
BASS = [45, 41, 48, 43]
K, C, H = kick(), clap(), hat()
n_beats = int(DUR / BEAT)
for b in range(n_beats):
    t = b * BEAT
    bar = b // 4
    ch, bass = CH[bar % 4], BASS[bar % 4]
    split = SPLIT <= t < SPLIT_END
    outro = t >= CIERRE + 1.0
    if t >= START and not split and not outro:
        put(K, t, g=0.9)                                      # bombo en cada tiempo
        tt = np.arange(int(BEAT * SR)) / SR
        bs = (np.sin(2 * np.pi * hz(bass) * tt) + 0.5 * np.sin(4 * np.pi * hz(bass) * tt)) * np.exp(-tt / 0.3) * 0.45
        put(bs.astype(np.float32), t + BEAT / 2)              # bajo a contratiempo
    if b % 2 == 1 and not outro:
        put(C, t, g=0.8 if not split else 0.5)               # palmas en 2 y 4
    if not outro:
        put(H, t + BEAT / 2, pan=0.2)
        if t >= START:
            put(H * 0.6, t + BEAT / 4, pan=-0.2)
            put(H * 0.6, t + 3 * BEAT / 4, pan=-0.2)
    # pluck en corcheas con la escala del acorde
    arp = [ch[0] + 12, ch[2] + 12, ch[1] + 12, ch[3] + 12]
    for k in range(2):
        if not outro or b * 2 + k < int((CIERRE + 2.0) / (BEAT / 2)):
            put(pluck(hz(arp[(b * 2 + k) % 4]), 0.45), t + k * BEAT / 2, pan=0.35 if k else -0.35, g=0.5)
    if b % 4 == 0:
        put(stab([n + 12 for n in ch], 0.5 if not outro else 2.0), t, g=0.55)
    elif b % 4 == 2 and not split:
        put(stab([n + 12 for n in ch], 0.25), t + BEAT / 2, g=0.4)
# reverb corta
ir_t = np.arange(int(0.8 * SR)) / SR
ir = rng.normal(0, 1, len(ir_t)) * np.exp(-ir_t / 0.18)
ir /= np.sqrt(np.sum(ir ** 2))
for c in range(2):
    mus[:, c] = mus[:, c] + np.convolve(mus[:, c], ir)[: len(mus)] * 0.18
fade = np.ones(len(mus))
fade[-int(1.2 * SR):] = np.linspace(1, 0, int(1.2 * SR)) ** 1.5
mus *= fade[:, None]
write_m4a(mus, "musica.m4a", rms_db=-15)

# ---------------------------------------------------------------- html


def rich(lines, prefix=None):
    """Arma las líneas; con prefix cada letra es un span (para escribirla de a una)."""
    out, i = [], 0
    for parts in lines:
        row = ""
        for part in parts:
            acc = part.startswith("*")
            txt = part.lstrip("*")
            if prefix:
                inner = "".join(f'<span id="{prefix}{i + j}" class="ch">{"&nbsp;" if c == " " else html.escape(c)}</span>' for j, c in enumerate(txt))
                i += len(txt)
            else:
                inner = html.escape(txt).replace(" ", "&nbsp;")
            row += f'<span class="acento">{inner}</span>' if acc else inner
        out.append(f"<div>{row}</div>")
    return "".join(out)


sets = [(f"#s{i}", t) for i, t in enumerate(senal_t)]
videos, js = "", []
for clip, t in HOOK:
    videos += f'''
      <video id="v-{clip}" class="clip toma" src="assets/clips/{clip}.mp4" muted playsinline data-start="{t:.2f}" data-duration="0.5" data-track-index="0"></video>'''
    js.append(f'tl.fromTo("#v-{clip}", {{ scale: 1.18 }}, {{ scale: 1.0, duration: 0.45, ease: "power3.out" }}, {t:.2f});')
    js.append(f'tl.set("#flash", {{ opacity: 0.55 }}, {t:.2f});')
    js.append(f'tl.to("#flash", {{ opacity: 0, duration: 0.14, ease: "power1.out" }}, {t:.2f});')

for k, (name, s, shots, words) in enumerate(MESAS, 1):
    t = s
    for j, (clip, d) in enumerate(shots):
        pre = PUSH if (j == 0 and k > 1) else 0.0
        videos += f'''
      <video id="v-{clip}" class="clip toma" src="assets/clips/{clip}.mp4" muted playsinline data-start="{t - pre:.2f}" data-duration="{d + pre:.2f}" data-track-index="0"></video>'''
        js.append(f'tl.fromTo("#v-{clip}", {{ scale: 1.14 }}, {{ scale: 1.0, duration: 0.35, ease: "power3.out" }}, {t:.2f});')
        js.append(f'tl.to("#v-{clip}", {{ scale: 1.05, duration: {d - 0.35:.2f}, ease: "none" }}, {t + 0.35:.2f});')
        t += d

js.append(f'tl.to("#v-m1e", {{ x: -1080, duration: {PUSH}, ease: "power3.inOut" }}, {MESAS[1][1] - PUSH:.2f});')
js.append(f'tl.fromTo("#v-m2a", {{ x: 1080 }}, {{ x: 0, duration: {PUSH}, ease: "power3.inOut" }}, {MESAS[1][1] - PUSH:.2f});')

set_js = "\n".join(f'      tl.set("{a}", {{ opacity: 1 }}, {t});' for a, t in sets)
all_js = "\n".join("      " + x for x in js)
SENAL_END = SPLIT - PUSH

doc = f'''<!doctype html>
<html lang="es">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <script src="assets/vendor/gsap.min.js"></script>
    <style>
      @font-face {{ font-family: "Comfortaa"; src: url("assets/fonts/Comfortaa-VariableFont_wght.ttf") format("truetype"); font-weight: 100 900; }}
      @font-face {{ font-family: "Playfair Display Italic"; src: url("assets/fonts/playfair-display-latin-500-italic.woff2") format("woff2"); font-weight: 500; font-style: italic; }}
      /* paleta del design system Nido */
      :root {{ --pincipal: #9b4c26; --secundario: #7b745a; --terciario: #e0b7a6; --blanco: #ffffff; }}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: 1080px; height: 1920px; overflow: hidden; background: var(--blanco); }}
      body {{ font-family: "Comfortaa", sans-serif; color: var(--pincipal); }}
      .ch {{ opacity: 0; }}
      .toma {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; object-fit: cover; z-index: 1; }}
      #flash {{ position: absolute; inset: 0; background: var(--blanco); opacity: 0; z-index: 4; }}
      .mitad {{ position: absolute; top: 0; width: 537px; height: 1920px; object-fit: cover; z-index: 5; }}
      #v-s1 {{ left: 0; }} #v-s2 {{ left: 543px; }}

      /* textos en el centro, sin velos: un borde blanco nítido los separa de la imagen */
      .texto {{ position: absolute; left: 0; width: 1080px; text-align: center; font-weight: 700; letter-spacing: -0.02em; line-height: 1.32;
        -webkit-text-stroke: 10px var(--blanco); paint-order: stroke fill; }}
      .acento {{ font-family: "Playfair Display Italic", serif; font-style: italic; font-weight: 500; letter-spacing: 0; font-size: 1.22em; }}
      #senal {{ top: 850px; font-size: 64px; }}
      #frase {{ top: 860px; font-size: 58px; }}
      #capa-senal, #capa-frase {{ position: absolute; inset: 0; z-index: 7; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{DUR:.2f}" data-width="1080" data-height="1920">
      <audio id="musica" class="clip" src="assets/audio/musica.m4a" data-start="0" data-duration="{DUR:.2f}" data-track-index="10" data-volume="1"></audio>
      <audio id="efectos" class="clip" src="assets/audio/sfx.m4a" data-start="0" data-duration="{DUR:.2f}" data-track-index="11" data-volume="0.8"></audio>
{videos}
      <div id="flash" class="clip" data-start="0" data-duration="{START:.2f}" data-track-index="4" data-track-kind="graphics"></div>

      <video id="v-s1" class="clip mitad" src="assets/clips/s1.mp4" muted playsinline data-start="{SPLIT - PUSH:.2f}" data-duration="{SPLIT_END - SPLIT + PUSH:.2f}" data-track-index="0"></video>
      <video id="v-s2" class="clip mitad" src="assets/clips/s2.mp4" muted playsinline data-start="{SPLIT - PUSH:.2f}" data-duration="{SPLIT_END - SPLIT + PUSH:.2f}" data-track-index="0"></video>

      <div id="capa-senal" class="clip" data-start="0" data-duration="{SENAL_END:.2f}" data-track-index="6" data-track-kind="graphics">
        <div id="senal" class="texto">{rich(SENAL, "s")}</div>
      </div>
      <div id="capa-frase" class="clip" data-start="{FRASE_T:.2f}" data-duration="{DUR - FRASE_T:.2f}" data-track-index="6" data-track-kind="graphics">
        <div id="frase" class="texto">{rich(FRASE)}</div>
      </div>
    </div>

    <script>
      const tl = gsap.timeline({{ paused: true }});

      // cortes y zooms de impacto
{all_js}

      // "esta es tu señal…" se escribe letra por letra, con su golpe de tecla
{set_js}
      tl.to("#senal", {{ opacity: 0, duration: 0.2, ease: "power1.in" }}, {SENAL_END - 0.22:.2f});

      // las dos mitades entran desde arriba y desde abajo
      tl.fromTo("#v-s1", {{ y: -1920 }}, {{ y: 0, duration: {PUSH + 0.1}, ease: "power3.out" }}, {SPLIT - PUSH:.2f});
      tl.fromTo("#v-s2", {{ y: 1920 }}, {{ y: 0, duration: {PUSH + 0.1}, ease: "power3.out" }}, {SPLIT - PUSH:.2f});

      // frase final con brillitos
      tl.fromTo("#frase", {{ opacity: 0, scale: 0.9 }}, {{ opacity: 1, scale: 1, duration: 0.5, ease: "back.out(1.6)" }}, {FRASE_T:.2f});

      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
'''
(ROOT / "index.html").write_text(doc)
print(json.dumps({"dur": DUR, "senal_end_typing": senal_t[-1], "frase": FRASE_T}))

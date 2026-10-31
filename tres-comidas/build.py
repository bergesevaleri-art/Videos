#!/usr/bin/env python3
"""Genera index.html y la mezcla de efectos de "mismo plato, 3 comidas".

La música es la pista del primer video (con sus golpes de máquina de escribir); cada texto
se escribe sobre su tanda de golpes y los cortes caen donde cortaba el video original.

Uso: python3 build.py   (desde la carpeta tres-comidas/)
"""
import html
import json
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
SR = 44100
DUR = 15.13            # largo de la pista del primer video

# ---------------------------------------------------------------- grilla (atada a la pista original)
# La pista trae música + golpes de máquina de escribir; cada texto se escribe sobre su tanda de golpes.
HOOK_END = 3.0
MOMENTOS = [                            # (palabra, hora, inicio, largo, tanda de golpes)
    ("desayuno", "08:30", 3.0, 4.0, (3.58, 4.18)),
    ("merienda", "17:00", 7.0, 4.0, (7.47, 8.01)),
    ("cena", "21:00", 11.0, 1.8, (11.68, 12.22)),
]
CIERRE = 12.8


def even(text, a, b):
    n = len(text)
    return [round(a + (b - a) * i / (n - 1), 3) for i in range(n)]


T1, T2 = "mismo plato", "3 comidas"
t1 = [0.067, 0.1, 0.133, 0.167, 0.2, 0.433, 0.433, 0.467, 0.533, 0.8, 0.867]
t2 = [0.933, 0.96, 1.0, 1.067, 1.1, 1.367, 1.4, 1.5, 1.733]
mom_times = [even(w, *g) for w, _, _, _, g in MOMENTOS]
CTA1 = "comentá MESA"
cta_times = [CIERRE + 0.3] * len(CTA1)

# ---------------------------------------------------------------- audio helpers


def load(name):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(ROOT / "assets/sfx" / name), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
        check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy()


def place(buf, clip, t, gain=1.0):
    i = int(t * SR)
    n = min(len(clip), len(buf) - i)
    if n > 0:
        buf[i:i + n] += clip[:n] * gain


def write_m4a(buf, name):
    peak = np.max(np.abs(buf)) or 1
    buf = buf / peak * 0.7
    out = ROOT / "assets/audio" / name
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "aac", "-b:a", "192k", str(out)], input=buf.astype(np.float32).tobytes(), check=True)


# ---------------------------------------------------------------- efectos (se suman a la pista original)
sfx = np.zeros((int(DUR * SR), 2), dtype=np.float32)
pop = load("pop.mp3")
for i in range(3):
    place(sfx, pop, 1.85 + i * 0.12, 0.45)
place(sfx, load("whoosh.mp3"), 2.3, 0.8)                  # la foto del desayuno se expande
wsh = load("whoosh-short.mp3")
for b in (MOMENTOS[1][2], MOMENTOS[2][2], CIERRE):
    place(sfx, wsh, b - 0.32, 0.7)                           # cortina rosa
place(sfx, load("sparkle.mp3"), CIERRE + 0.2, 0.55)          # logo
write_m4a(sfx, "sfx.m4a")

# música: la pista del primer video, tal cual
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(ROOT.parent / "mismo-plato/assets/plato.mp4"), "-vn",
                "-c:a", "copy", str(ROOT / "assets/audio/musica.m4a")], check=True)

# ---------------------------------------------------------------- html


def spans(text, prefix):
    return "".join(
        f'<span id="{prefix}{i}" class="ch">{"&nbsp;" if c == " " else html.escape(c)}</span>' for i, c in enumerate(text))


sets = [(f"#a{i}", t) for i, t in enumerate(t1)] + [(f"#b{i}", t) for i, t in enumerate(t2)]
sets += [(f"#c{i}", t) for i, t in enumerate(cta_times)]
videos, textos, cortinas = "", "", ""
moment_js = []
for k, ((word, hora, s, L, _), mt) in enumerate(zip(MOMENTOS, mom_times), 1):
    sets += [(f"#m{k}c{i}", t) for i, t in enumerate(mt)]
    for part, off in (("a", 0.0), ("b", L / 2)):
        videos += f'''
      <video id="v-{word}-{part}" class="clip toma" src="assets/clips/{word}-{part}.mp4" muted playsinline data-start="{s + off:.2f}" data-duration="{L / 2:.2f}" data-track-index="0"></video>'''
    textos += f'''
      <div id="t-{word}" class="clip momento" data-start="{s:.2f}" data-duration="{L:.2f}" data-track-index="2" data-track-kind="graphics">
        <div class="velo"></div>
        <div class="hora" id="h-{word}"><img class="mini-star" src="assets/brand/estrella.png" alt="" />{hora}</div>
        <div class="palabra">{spans(word, f"m{k}c")}</div>
        <div class="paso" id="p-{word}">comida {k} de 3</div>
      </div>'''
    moment_js.append((word, s, L))
for i, b in enumerate([MOMENTOS[1][2], MOMENTOS[2][2], CIERRE], 1):
    cortinas += f'''
      <div id="cortina{i}" class="clip cortina" data-start="{b - 0.3:.2f}" data-duration="0.6" data-track-index="4" data-track-kind="graphics"><img src="assets/brand/estrella.png" alt="" /></div>'''

set_js = "\n".join(f'      tl.set("{a}", {{ opacity: 1 }}, {t});' for a, t in sets)
mom_js = "\n".join(
    f'''      tl.fromTo("#h-{w}", {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: 0.4, ease: "power2.out" }}, {s + 0.1:.2f});
      tl.fromTo("#p-{w}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.4, ease: "power1.out" }}, {s + 0.35:.2f});
      tl.fromTo("#v-{w}-a", {{ scale: 1.0 }}, {{ scale: 1.07, duration: {L / 2:.2f}, ease: "none" }}, {s:.2f});
      tl.fromTo("#v-{w}-b", {{ scale: 1.12 }}, {{ scale: 1.02, duration: {L / 2:.2f}, ease: "power1.out" }}, {s + L / 2:.2f});'''
    for w, s, L in moment_js)
cort_js = "\n".join(
    f'''      tl.fromTo("#cortina{i} ", {{ x: 1080 }}, {{ x: 0, duration: 0.3, ease: "power3.in" }}, {b - 0.3:.2f});
      tl.to("#cortina{i}", {{ x: -1080, duration: 0.3, ease: "power3.out" }}, {b:.2f});
      tl.fromTo("#cortina{i} img", {{ rotation: -90 }}, {{ rotation: 90, duration: 0.6, ease: "none" }}, {b - 0.3:.2f});'''
    for i, b in enumerate([MOMENTOS[1][2], MOMENTOS[2][2], CIERRE], 1)).replace('"#cortina1 "', '"#cortina1"').replace('"#cortina2 "', '"#cortina2"').replace('"#cortina3 "', '"#cortina3"')

# tile del desayuno: 316x560 en (46, 700) → pantalla completa
TILE_SCALE = 316 / 1080
TILE_X = (46 + 158) - 540
TILE_Y = (700 + 280) - 960

doc = f'''<!doctype html>
<html lang="es">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <script src="assets/vendor/gsap.min.js"></script>
    <style>
      @font-face {{ font-family: "Comfortaa"; src: url("assets/fonts/Comfortaa-VariableFont_wght.ttf") format("truetype"); font-weight: 100 900; }}
      /* paleta del design system Nido */
      :root {{ --pincipal: #9b4c26; --secundario: #7b745a; --terciario: #e0b7a6; --blanco: #ffffff; }}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: 1080px; height: 1920px; overflow: hidden; background: var(--blanco); }}
      body {{ font-family: "Comfortaa", sans-serif; color: var(--pincipal); }}
      .ch {{ opacity: 0; }}

      /* fondo: la foto del desayuno con opacidad baja */
      .fondo {{ position: absolute; inset: 0; background: var(--blanco); overflow: hidden; }}
      #fondo-a, #fondo-b {{ position: absolute; inset: 0; width: 1080px; height: 1920px; object-fit: cover; opacity: 0.28; }}

      #titulo {{ position: absolute; left: 0; top: 330px; width: 1080px; text-align: center; font-weight: 700; letter-spacing: -0.02em; line-height: 1.02; font-size: 124px; }}
      .foto {{ position: absolute; top: 700px; width: 316px; height: 560px; border-radius: 24px; overflow: hidden; }}
      .foto img, #expande img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
      #f1 {{ left: 46px; }} #f2 {{ left: 382px; }} #f3 {{ left: 718px; }}
      .pie {{ position: absolute; top: 1290px; width: 316px; text-align: center; font-size: 40px; font-weight: 600; }}
      #pie1 {{ left: 46px; }} #pie2 {{ left: 382px; }} #pie3 {{ left: 718px; }}
      #expande {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; overflow: hidden; z-index: 6; }}

      .toma {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; object-fit: cover; z-index: 1; }}

      .momento {{ position: absolute; inset: 0; z-index: 3; }}
      .velo {{ position: absolute; left: 0; top: 0; width: 1080px; height: 820px;
        background: linear-gradient(180deg, rgba(255,255,255,0.9) 0%, rgba(255,255,255,0.78) 42%, rgba(255,255,255,0) 100%); }}
      .hora {{ position: absolute; left: 0; top: 250px; width: 1080px; text-align: center; font-size: 46px; font-weight: 600; color: var(--secundario); letter-spacing: 0.02em; }}
      .mini-star {{ width: 40px; height: 40px; vertical-align: -6px; margin-right: 14px; }}
      .palabra {{ position: absolute; left: 0; top: 318px; width: 1080px; text-align: center; font-size: 168px; font-weight: 700; letter-spacing: -0.03em; line-height: 1.1; }}
      .paso {{ position: absolute; left: 0; top: 520px; width: 1080px; text-align: center; font-size: 38px; font-weight: 600; }}

      .cortina {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; background: var(--terciario); z-index: 8; }}
      .cortina img {{ position: absolute; left: 470px; top: 890px; width: 140px; height: 140px; }}

      #cierre {{ z-index: 5; }}
      #logo {{ position: absolute; left: 370px; top: 560px; width: 340px; height: auto; }}
      #cta1 {{ position: absolute; left: 0; top: 880px; width: 1080px; text-align: center; font-size: 104px; font-weight: 700; letter-spacing: -0.02em; }}
      #cta2 {{ position: absolute; left: 0; top: 1020px; width: 1080px; text-align: center; font-size: 56px; font-weight: 500; }}
      #star-a {{ position: absolute; left: 150px; top: 470px; width: 70px; height: 70px; }}
      #star-b {{ position: absolute; left: 850px; top: 1180px; width: 48px; height: 48px; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{DUR:.2f}" data-width="1080" data-height="1920">
      <audio id="musica" class="clip" src="assets/audio/musica.m4a" data-start="0" data-duration="{DUR:.2f}" data-track-index="10" data-volume="1"></audio>
      <audio id="efectos" class="clip" src="assets/audio/sfx.m4a" data-start="0" data-duration="{DUR:.2f}" data-track-index="11" data-volume="0.7"></audio>

      <div id="apertura" class="clip fondo" data-start="0" data-duration="{HOOK_END + 0.3:.2f}" data-track-index="1" data-track-kind="graphics" style="z-index: 2">
        <img id="fondo-a" src="assets/fotos/fondo.jpg" alt="" />
        <div id="titulo">
          <div id="t1">{spans(T1, "a")}</div>
          <div id="t2">{spans(T2, "b")}</div>
        </div>
        <div id="f1" class="foto"><img src="assets/fotos/desayuno.jpg" alt="" /></div>
        <div id="f2" class="foto"><img src="assets/fotos/merienda.jpg" alt="" /></div>
        <div id="f3" class="foto"><img src="assets/fotos/cena.jpg" alt="" /></div>
        <div id="pie1" class="pie">desayuno</div>
        <div id="pie2" class="pie">merienda</div>
        <div id="pie3" class="pie">cena</div>
      </div>

      <div id="expande" class="clip" data-start="2.40" data-duration="{HOOK_END + 0.35 - 2.4:.2f}" data-track-index="3" data-track-kind="graphics">
        <img src="assets/fotos/desayuno.jpg" alt="" />
      </div>
{videos}
{textos}

      <div id="cierre" class="clip fondo" data-start="{CIERRE:.2f}" data-duration="{DUR - CIERRE:.2f}" data-track-index="1" data-track-kind="graphics">
        <img id="fondo-b" src="assets/fotos/fondo.jpg" alt="" />
        <img id="star-a" src="assets/brand/estrella.png" alt="" />
        <img id="logo" src="assets/brand/logo-nido-home-deco-pincipal.png" alt="nido home &amp; deco" />
        <div id="cta1">{spans(CTA1, "c")}</div>
        <div id="cta2">y armamos la tuya</div>
        <img id="star-b" src="assets/brand/estrella.png" alt="" />
      </div>
{cortinas}
    </div>

    <script>
      const tl = gsap.timeline({{ paused: true }});

      // apertura: la foto de fondo respira, las tres fotos entran con un pop
      tl.fromTo("#fondo-a", {{ scale: 1.0 }}, {{ scale: 1.08, duration: {HOOK_END:.2f}, ease: "none" }}, 0);
      ["#f1", "#f2", "#f3"].forEach((s, i) => tl.fromTo(s, {{ y: 60, scale: 0.92, opacity: 0 }}, {{ y: 0, scale: 1, opacity: 1, duration: 0.45, ease: "back.out(1.6)" }}, 1.85 + i * 0.12));
      tl.fromTo(".pie", {{ opacity: 0, y: 10 }}, {{ opacity: 1, y: 0, duration: 0.35, ease: "power2.out" }}, 2.15);

      // la foto del desayuno se expande y de ahí arranca el video
      tl.set("#expande", {{ x: {TILE_X}, y: {TILE_Y}, scale: {TILE_SCALE:.5f}, borderRadius: {24 / TILE_SCALE:.0f} }}, 2.4);
      tl.set("#f1", {{ opacity: 0 }}, 2.4);
      tl.to(["#f2", "#f3", "#pie2", "#pie3"], {{ y: 80, opacity: 0, duration: 0.3, ease: "power2.in", stagger: 0.04 }}, 2.4);
      tl.to(["#titulo", "#pie1"], {{ opacity: 0, duration: 0.25, ease: "power1.in" }}, 2.45);
      tl.to("#expande", {{ x: 0, y: 0, scale: 1, borderRadius: 0, duration: 0.55, ease: "power3.inOut" }}, 2.45);
      tl.to("#expande", {{ opacity: 0, duration: 0.3, ease: "power1.inOut" }}, {HOOK_END:.2f});

      // escritura letra por letra (cada letra tiene su golpe de tecla en la pista de efectos)
{set_js}

      // comidas: hora, paso y movimiento de cámara en cada toma
{mom_js}

      // cortinas rosas con la estrella entre comidas
{cort_js}

      // cierre
      tl.fromTo("#fondo-b", {{ scale: 1.08 }}, {{ scale: 1.0, duration: {DUR - CIERRE:.2f}, ease: "none" }}, {CIERRE:.2f});
      tl.fromTo("#logo", {{ opacity: 0, y: 24 }}, {{ opacity: 1, y: 0, duration: 0.5, ease: "power2.out" }}, {CIERRE + 0.2:.2f});
      tl.fromTo("#cta1", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.45, ease: "power2.out" }}, {CIERRE + 0.3:.2f});
      tl.fromTo("#cta2", {{ opacity: 0, y: 12 }}, {{ opacity: 1, y: 0, duration: 0.45, ease: "power2.out" }}, {CIERRE + 0.3:.2f});
      tl.fromTo(["#star-a", "#star-b"], {{ rotation: -60, scale: 0.4, opacity: 0 }}, {{ rotation: 0, scale: 1, opacity: 1, duration: 0.8, ease: "back.out(1.6)", stagger: 0.12 }}, {CIERRE + 0.3:.2f});

      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
'''
(ROOT / "index.html").write_text(doc)
print(json.dumps({"dur": DUR, "t1": t1[:3], "cta_end": cta_times[-1]}))

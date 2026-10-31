# Videos

Proyectos de video hechos con [HyperFrames](https://github.com/heygen-com/hyperframes) (HTML → MP4).

## Qué hay aquí

- `.claude/skills/` – skills de HyperFrames para Claude Code (`/hyperframes`, `/hyperframes-cli`, `/hyperframes-registry`, `/media-use`). Se cargan solas al abrir el repo.
- `mi-video/` – proyecto de ejemplo (1920x1080, 10 s). La composición está en `mi-video/index.html`.

## Uso

Requisitos: Node.js 22+ y FFmpeg.

```bash
cd mi-video
npm install          # instala gsap (copiado en assets/vendor)
npm run dev          # vista previa en el navegador
npm run check        # valida la composición
npm run render       # renderiza a MP4 en renders/
```

Proyecto nuevo: `npx hyperframes init otro-video --non-interactive`

Con Claude Code basta con pedir, por ejemplo:
> Usando /hyperframes, crea un video vertical de 15 segundos para Instagram presentando un producto.

Nota: en el entorno en la nube, el navegador headless no puede descargar scripts de CDN,
así que las librerías (como GSAP) se cargan desde `assets/vendor/`.

## Actualizar las skills

```bash
npx hyperframes skills update
cp -r ~/.claude/skills/{hyperframes,hyperframes-cli,hyperframes-registry,media-use} .claude/skills/
```

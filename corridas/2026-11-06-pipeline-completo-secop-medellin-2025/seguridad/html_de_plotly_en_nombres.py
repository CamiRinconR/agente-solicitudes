"""grafico.py (líneas 153, 157, 199 y 204) pasa el nombre de la entidad a Plotly sin neutralizar «<» y «>».

Plotly lee ese texto como seudo-HTML (<a href>, <span style>, <br>) en las etiquetas del eje y en el cuadro
del puntero. Un nombre con un enlace queda como enlace en el gráfico publicado (grafico.html, que el informe
final muestra en un iframe). plotly.js no deja pasar javascript:, así que no corre código: el riesgo es un
enlace o un texto falso dentro del gráfico. Datos sintéticos; no modifica el código revisado.

Uso: .venv/bin/python -B seguridad/html_de_plotly_en_nombres.py [--navegador]
  --navegador además abre el HTML en Chrome sin ventana (--dump-dom) y busca el enlace dentro del SVG.
Sale con 0 e imprime REPRODUCIDO si el patrón se reproduce; con 1 si ya no.
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
CORRIDA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CORRIDA))
import plotly  # noqa: E402

import grafico  # noqa: E402

ENLACE = "https://ejemplo.org/x"
NOMBRE = f'<a href="{ENLACE}">ENTIDAD X</a>'   # 45 caracteres: cabe entero en la etiqueta del eje (52)
FILAS = [
    {"nit_entidad": "800000001", "entidad": NOMBRE, "valor_contratado": 5e9, "numero_contratos": 3},
    {"nit_entidad": "800000002", "entidad": "OTRA ENTIDAD", "valor_contratado": 1e9, "numero_contratos": 1},
]
PLOTLY_JS = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"

fig = grafico.graficar(FILAS, {})
traza = json.loads(fig.to_json())["data"][0]
en_eje = NOMBRE in traza["y"]
en_cuadro = any(fila[0] == NOMBRE for fila in traza["customdata"])
js = PLOTLY_JS.read_text(encoding="utf-8")
plotly_lee_enlaces = r'href\s*=\s*("([^"]*)"' in js and '"mailto:"' in js
print(f"etiqueta del eje con el HTML crudo: {en_eje} · cuadro del puntero con el HTML crudo: {en_cuadro} · "
      f"plotly.js interpreta <a href=...> en el texto: {plotly_lee_enlaces}")
ok = en_eje and en_cuadro and plotly_lee_enlaces

if "--navegador" in sys.argv:
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    with tempfile.TemporaryDirectory() as t:
        html = Path(t) / "g.html"
        fig.write_html(str(html), include_plotlyjs=PLOTLY_JS.as_uri(), full_html=True)
        p = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                            "--disable-extensions", f"--user-data-dir={t}/perfil", "--allow-file-access-from-files",
                            "--virtual-time-budget=10000", "--dump-dom", html.as_uri()],
                           capture_output=True, text=True, timeout=120)
        enlaces = re.findall(r'<a [^>]*href="' + re.escape(ENLACE) + '"', p.stdout)
        print(f"en el DOM que dibujó Chrome hay {len(enlaces)} enlace(s) a {ENLACE} dentro del gráfico")
        ok = ok and bool(enlaces)

print("REPRODUCIDO" if ok else "NO SE REPRODUJO")
sys.exit(0 if ok else 1)

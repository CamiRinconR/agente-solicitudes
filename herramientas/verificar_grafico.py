#!/usr/bin/env python3
"""Visualización: comprueba el gráfico que generó la IA (sin IA) y lo deja en grafico.html.

Uso: python verificar_grafico.py <corrida>

La corrida trae:
  grafico.json  {"pregunta", "medida": columna de valores, "categoria": columna de claves, "periodo",
                 "periodo_incompleto": bool, "fuera_del_grafico": {"motivo", "valor"} (opcional)}
  grafico.py    def graficar(resultado, procedencia) -> plotly.graph_objects.Figure
                (resultado = filas aprobadas; procedencia = la de la ingesta, con fuente y fecha)

Lista de comprobación (módulo 4 del curso):
  1. cuenta de control: lo que suma el gráfico + lo que se dejó fuera (declarado) = total de la tabla
  2. barras con el eje de valores desde cero; factor de mentira 1
  3. título con qué se mide y el período (un número)
  4. eje de valores con título (unidades)
  5. fuente y fecha de consulta visibles
  6. período incompleto marcado, si aplica
  7. sin datos personales en ningún texto del gráfico
El HTML lo escribe este verificador, no el código de la IA (que corre en la caja de arena y no escribe).
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import caja  # noqa: E402
import dependencias  # noqa: E402
import seguridad  # noqa: E402
from gobernanza import escanear_texto, parece_instruccion  # noqa: E402

RUNNER = r'''
import importlib.util, json, sys
ruta, resultado, procedencia = sys.argv[1], json.loads(sys.argv[2]), json.loads(sys.argv[3])
import types
m = types.ModuleType("graf"); m.__file__ = ruta
exec(compile(open(ruta, encoding="utf-8").read(), ruta, "exec"), m.__dict__)   # desde la fuente, sin .pyc
fig = m.graficar(resultado, procedencia)
print("MARCA" + fig.to_json())
'''.replace("MARCA", caja.MARCA)


def procedencia_de(c, spec):
    from rutas import resolver
    rutas = list((spec.get("datos_crudos") or {}).values()) + list(spec["datos"].values())   # la procedencia vive junto al dato crudo
    for p in [c / "procedencia.json"] + [Path(resolver(r)).parent / "procedencia.json" for r in rutas]:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return {}


def textos(fig):
    L = []
    lay = fig.get("layout", {})
    tit = lay.get("title", {})
    L.append(tit.get("text", "") if isinstance(tit, dict) else str(tit))
    for eje in ("xaxis", "yaxis"):
        t = (lay.get(eje) or {}).get("title", {})
        L.append(t.get("text", "") if isinstance(t, dict) else str(t))
    L += [a.get("text", "") for a in lay.get("annotations", [])]
    for tr in fig.get("data", []):
        for k in ("name", "text", "hovertemplate", "x", "y", "customdata"):
            v = tr.get(k)
            if isinstance(v, list):
                L += [json.dumps(x, ensure_ascii=False) if not isinstance(x, str) else x for x in v]
            elif isinstance(v, str):
                L.append(v)
    return L


def fechas_posibles(iso):
    try:
        d = date.fromisoformat(iso[:10])
    except (TypeError, ValueError):
        return []
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    return [f"{d:%d-%m-%Y}", f"{d:%d/%m/%Y}", d.isoformat(), f"{d.day} de {meses[d.month - 1]} de {d.year}",
            f"{d:%d} de {meses[d.month - 1]} de {d.year}"]


def valores_de(tr):
    h = tr.get("orientation") == "h"
    v = tr.get("x") if h else tr.get("y")
    if isinstance(v, dict) and "bdata" in v:       # plotly 6+: arreglos binarios en el JSON
        import base64
        import numpy as np
        v = np.frombuffer(base64.b64decode(v["bdata"]), dtype=np.dtype(v.get("dtype", "f8"))).tolist()
    return [float(x) for x in (v or []) if x is not None], ("xaxis" if h else "yaxis")


def comprobar(c):
    from rutas import resolver_datos
    spec = resolver_datos(json.loads((c / "spec.json").read_text(encoding="utf-8")))
    inf = json.loads((c / "informe.json").read_text(encoding="utf-8"))
    meta = json.loads((c / "grafico.json").read_text(encoding="utf-8"))
    resultado = inf.get("resultado_oficial") or []
    proc = procedencia_de(c, spec)
    checks = []
    gp = c / "grafico.py"
    dep = dependencias.revisar(gp)
    seg, _ = seguridad.revisar([gp])
    bloqueos = (dep.get("no_permitidas") or []) + (dep.get("intenta_instalar") or []) + [h["regla"] for h in seg[0]["bloquean"]]
    checks.append({"comprobacion": "compuertas de seguridad y librerías", "ok": not bloqueos, "detalle": str(bloqueos or "sin hallazgos")})
    if bloqueos:
        return checks, None
    fig_json, err = caja.correr(RUNNER, str(gp), json.dumps(resultado, ensure_ascii=False), json.dumps(proc, ensure_ascii=False))
    checks.append({"comprobacion": "el código del gráfico corre", "ok": err is None, "detalle": err or "devolvió una figura"})
    if err:
        return checks, None
    fig = fig_json
    lay = fig.get("layout", {})
    barras = [t for t in fig.get("data", []) if t.get("type") == "bar"]
    medida = meta.get("medida")
    total_tabla = sum(float(f.get(medida) or 0) for f in resultado) if medida else None
    suma_graf, eje = 0.0, "yaxis"
    for t in fig.get("data", []):
        vals, eje = valores_de(t)
        suma_graf += sum(vals)
    fuera = float((meta.get("fuera_del_grafico") or {}).get("valor") or 0)
    escala = float(meta.get("escala") or 1)       # p. ej. 1e9 si el gráfico muestra miles de millones
    if total_tabla is not None:
        en_pesos = suma_graf * escala
        ok = abs(en_pesos + fuera - total_tabla) <= max(0.5, 1e-9 * abs(total_tabla), 1e-6 * escala)
        checks.append({"comprobacion": "cuenta de control", "ok": ok,
                       "detalle": f"gráfico {en_pesos:,.2f} (escala {escala:g}) + fuera del gráfico {fuera:,.2f} · tabla {total_tabla:,.2f}"})
    if barras:
        ax = lay.get(eje, {}) or {}
        rango = ax.get("range")
        desde_cero = not (rango and rango[0] not in (0, None)) and ax.get("type") != "log" and not any(t.get("base") for t in barras)
        factor = 1.0
        if not desde_cero and rango:
            vals = [v for t in barras for v in valores_de(t)[0] if v > 0]
            if vals and min(vals) > rango[0]:
                factor = round(((max(vals) - rango[0]) / (min(vals) - rango[0])) / (max(vals) / min(vals)), 2)
        checks.append({"comprobacion": "barras desde cero (factor de mentira 1)", "ok": desde_cero,
                       "detalle": "el eje de valores empieza en 0" if desde_cero else f"el eje empieza en {rango[0]}: factor de mentira {factor}"})
        tit_eje = (ax.get("title") or {}).get("text") if isinstance(ax.get("title"), dict) else ax.get("title")
        checks.append({"comprobacion": "eje de valores con título y unidades", "ok": bool(tit_eje and str(tit_eje).strip()),
                       "detalle": str(tit_eje or "sin título")})
    t = lay.get("title", {})
    titulo = t.get("text", "") if isinstance(t, dict) else str(t or "")
    checks.append({"comprobacion": "título con qué se mide y el período", "ok": len(titulo) >= 15 and bool(re.search(r"\d", titulo)),
                   "detalle": titulo or "sin título"})
    todo = " ".join(textos(fig))
    fuente = (proc.get("fuente") or {}).get("titulo", "")
    palabra = (fuente.split()[0] if fuente else "fuente").lower()
    fechas = fechas_posibles(proc.get("consultado", ""))
    tiene_fuente = palabra in todo.lower()
    tiene_fecha = any(f in todo for f in fechas) if fechas else True
    checks.append({"comprobacion": "fuente y fecha de consulta visibles", "ok": tiene_fuente and tiene_fecha,
                   "detalle": f"fuente «{palabra}»: {'sí' if tiene_fuente else 'no'} · fecha {fechas[:1]}: {'sí' if tiene_fecha else 'no'}"})
    if meta.get("periodo_incompleto"):
        marcado = bool(re.search(r"\b(incomplet\w*|parcial\w*|corte|hasta el)\b", todo, re.I))   # «Recorte» no cuenta
        checks.append({"comprobacion": "período incompleto marcado", "ok": marcado, "detalle": "marcado" if marcado else "no se marca"})
    # El riesgo: un texto de los DATOS que trae «<» (p. ej. un nombre con <a href>) y llega sin escapar, o enlaces y
    # scripts en cualquier parte. El formato que pone el graficador (<b>, <br>, <span>) es legítimo en Plotly.
    crudos = sorted({v for f in resultado for v in f.values() if isinstance(v, str) and "<" in v})
    sin_escapar = [v[:60] for v in crudos if v in todo]
    peligrosas = sorted(set(re.findall(r"<\s*(a|img|iframe|script|object|embed|link|meta)\b", todo, re.I)))
    ok_html = not sin_escapar and not peligrosas
    checks.append({"comprobacion": "sin HTML de los datos sin escapar, ni enlaces o scripts", "ok": ok_html,
                   "detalle": "ninguno" if ok_html else (f"texto de los datos sin escapar: {sin_escapar}" if sin_escapar else "")
                   + (f" · etiquetas peligrosas {peligrosas}" if peligrosas else "") + " (Plotly interpreta HTML; escape «<» como &lt;)"})
    invisibles = [t[:40] for t in textos(fig) if re.search(r"[\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff]", t)]
    checks.append({"comprobacion": "sin caracteres invisibles o bidireccionales en el texto publicado", "ok": not invisibles,
                   "detalle": "ninguno" if not invisibles else f"{len(invisibles)} textos (pueden voltear o disfrazar lo que se lee): {invisibles[:2]}"})
    # procedencia: con una procedencia falsa, el gráfico debe mostrar ESA fuente y ESA fecha (nada escrito a mano)
    falsa = dict(proc or {})
    falsa.update({"fuente": {**(proc.get("fuente") or {}), "titulo": "FUENTE-DE-CONTROL"}, "consultado": "2000-01-02T00:00:00"})
    fig_f, err_f = caja.correr(RUNNER, str(gp), json.dumps(resultado, ensure_ascii=False), json.dumps(falsa, ensure_ascii=False))
    if fig_f is not None:
        tf = " ".join(textos(fig_f))
        sigue = any(f in tf for f in fechas_posibles(proc.get("consultado", "")))
        usa = any(f in tf for f in fechas_posibles("2000-01-02"))
        checks.append({"comprobacion": "la fuente y la fecha salen de la procedencia, no del código", "ok": usa and not sigue,
                       "detalle": "con una procedencia de control, el gráfico muestra su fecha" if usa and not sigue
                       else "el gráfico muestra una fecha escrita en el código, no la de la procedencia"})
    ordenes = [t[:60] for t in textos(fig) if parece_instruccion(t)]
    checks.append({"comprobacion": "sin textos con forma de instrucción para una IA", "ok": not ordenes,
                   "detalle": "ninguno" if not ordenes else f"{len(ordenes)}: {ordenes[:2]} (un dato con forma de orden no se publica como dato normal: revisarlo en la fuente)"})
    pii = escanear_texto(todo)
    checks.append({"comprobacion": "sin datos personales en el gráfico", "ok": not pii, "detalle": str(pii or "ninguno")})
    return checks, fig


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    c = Path(argv[0]).resolve()
    checks, fig = comprobar(c)
    if fig is not None:
        import plotly.io as pio
        pio.from_json(json.dumps(fig)).write_html(str(c / "grafico.html"), include_plotlyjs=True, full_html=True)
    ok = all(x["ok"] for x in checks)
    out = {"estado": "aprobado" if ok else "revisar", "comprobaciones": checks, "html": str(c / "grafico.html") if fig else None}
    (c / "grafico_verificacion.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    for x in checks:
        print(f"{'✓' if x['ok'] else '✗'} {x['comprobacion']}: {x['detalle']}")
    print("RESUMEN " + json.dumps({"estado": out["estado"], "fallas": [x["comprobacion"] for x in checks if not x["ok"]]}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

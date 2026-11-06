#!/usr/bin/env python3
"""Análisis: prueba las hipótesis que propuso la IA (sin IA).

Uso:
  python verificar_hipotesis.py <corrida> --sellar   sella hipotesis.json (registro previo, antes de probar)
  python verificar_hipotesis.py <corrida>            corre hipotesis.py y escribe hipotesis_resultado.json

hipotesis.json  (lo escribe el proponente ANTES de cualquier prueba):
  [{"id": "H1", "enunciado": "...", "medida": "qué número se calcula y sobre qué filas",
    "umbral": {"operador": ">" | ">=" | "<" | "<=" | "entre", "valor": número o [a, b]},
    "linea_base": "contra qué se compara", "por_que_importa": "..."}]
hipotesis.py    (lo escribe el probador, sin ver el razonamiento del proponente; calcula desde los CSV):
  from reglas_base import hipotesis
  @hipotesis("H1")
  def h1(datos): return {"valor": 0.42, "linea_base": 0.2, "detalle": "..."}
"""
import hashlib
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import caja  # noqa: E402
import dependencias  # noqa: E402
import seguridad  # noqa: E402

RUNNER = r'''
import importlib.util, json, math, sys
sys.path.insert(0, sys.argv[3])
ruta, datos = sys.argv[1], json.loads(sys.argv[2])
import reglas_base
s = importlib.util.spec_from_file_location("hip", ruta); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
out = {}
for hid, fn in reglas_base.HIPOTESIS.items():
    try:
        r = fn(dict(datos))
        r = {k: (v.item() if hasattr(v, "item") else v) for k, v in dict(r).items()}
        out[hid] = r
    except Exception as e:
        out[hid] = {"error": f"{type(e).__name__}: {e}"}
print("MARCA" + json.dumps(out, ensure_ascii=False, default=str))
'''.replace("MARCA", caja.MARCA)


def evaluar(umbral, valor):
    op, ref = umbral.get("operador"), umbral.get("valor")
    if valor is None:
        return None
    v = float(valor)
    if op == ">":
        return v > float(ref)
    if op == ">=":
        return v >= float(ref)
    if op == "<":
        return v < float(ref)
    if op == "<=":
        return v <= float(ref)
    if op == "entre":
        return float(ref[0]) <= v <= float(ref[1])
    raise ValueError(f"operador desconocido: {op}")


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    c = Path(argv[0]).resolve()
    hj = c / "hipotesis.json"
    sello = c / "sellos_hipotesis.json"
    if "--sellar" in argv:
        h = hashlib.sha256(hj.read_bytes()).hexdigest()
        if sello.exists() and json.loads(sello.read_text())["sha256"] != h:
            print("Las hipótesis ya estaban selladas y cambiaron: cambiarlas después de probar no vale.")
            return 1
        sello.write_text(json.dumps({"sha256": h}))
        print("Hipótesis selladas (registro previo).")
        return 0
    from rutas import resolver_datos
    spec = resolver_datos(json.loads((c / "spec.json").read_text(encoding="utf-8")))
    hips = json.loads(hj.read_text(encoding="utf-8"))
    problemas = []
    if not sello.exists():
        problemas.append("las hipótesis no se sellaron antes de probarlas")
    elif json.loads(sello.read_text())["sha256"] != hashlib.sha256(hj.read_bytes()).hexdigest():
        problemas.append("las hipótesis cambiaron después de sellarse")
    hp = c / "hipotesis.py"
    dep = dependencias.revisar(hp)
    seg, _ = seguridad.revisar([hp])
    bloqueos = (dep.get("no_permitidas") or []) + (dep.get("intenta_instalar") or []) + [h["regla"] for h in seg[0]["bloquean"]]
    if bloqueos:
        problemas.append(f"hipotesis.py no pasa las compuertas: {bloqueos}")
        salida = {}
    else:
        salida, err = caja.correr(RUNNER, str(hp), json.dumps(spec["datos"]), str(AQUI))
        if err:
            problemas.append(f"hipotesis.py falló: {err}")
            salida = {}
    filas = []
    for h in hips:
        r = salida.get(h["id"], {"error": "no hay prueba para esta hipótesis"})
        try:
            sostiene = None if "error" in r else evaluar(h["umbral"], r.get("valor"))
        except (ValueError, TypeError) as e:
            sostiene, r = None, {**r, "error": str(e)}
        filas.append({**h, "valor": r.get("valor"), "linea_base_valor": r.get("linea_base"),
                      "detalle": r.get("detalle") or r.get("error"),
                      "veredicto": "se sostiene" if sostiene else ("no se sostiene" if sostiene is False else "sin prueba")})
    sin = [f["id"] for f in filas if f["veredicto"] == "sin prueba"]
    if sin:
        problemas.append(f"hipótesis sin prueba: {sin}")
    out = {"hipotesis": filas, "problemas": problemas, "estado": "probadas" if not problemas else "revisar"}
    (c / "hipotesis_resultado.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    for f in filas:
        print(f"{f['id']} · {f['veredicto']}: {f['enunciado']} — valor {f['valor']} · umbral {f['umbral']} · base {f['linea_base_valor']}")
    for p in problemas:
        print(f"! {p}")
    print("RESUMEN " + json.dumps({"estado": out["estado"], "veredictos": {f["id"]: f["veredicto"] for f in filas},
                                   "problemas": problemas}, ensure_ascii=False))
    return 0 if not problemas else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

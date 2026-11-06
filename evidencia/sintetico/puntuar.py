#!/usr/bin/env python3
"""Compara implementaciones contra la respuesta correcta (oráculo) y diagnostica la trampa.

Uso: python puntuar.py verdad.json ventas.csv clientes.csv nombre=impl.py [nombre=impl.py ...]
"""
import json
import sys
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "herramientas"))
from verificar import ejecutar_impl, fmt  # noqa: E402


def vector(res):
    out = {}
    for f in res:
        k = str(f["region"])
        out[k] = out.get(k, 0) + float(f["ventas"] if "ventas" in f else f["ventas_netas"])
    return out


def distancia(a, b):
    return sum(abs(a.get(k, 0) - b.get(k, 0)) for k in set(a) | set(b))


def main():
    verdad = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    datos = {"ventas": sys.argv[2], "clientes": sys.argv[3]}
    v = {r["region"]: float(r["ventas"]) for r in verdad["resultado"]}
    alts = {n: {k: float(x) for k, x in a["por_region"].items()} for n, a in verdad["alternativas"].items()}
    filas = []
    for par in sys.argv[4:]:
        nombre, ruta = par.split("=", 1)
        res, err = ejecutar_impl(ruta, datos)
        if err:
            filas.append({"nombre": nombre, "error": err})
            continue
        r = vector(res)
        dif = {k: r.get(k, 0) - v.get(k, 0) for k in sorted(set(r) | set(v)) if abs(r.get(k, 0) - v.get(k, 0)) > 1}
        diag = []
        if dif:
            exactas = [n for n, a in alts.items() if distancia(a, r) <= 1]
            if exactas:
                diag = exactas
            else:
                # ¿dos trampas a la vez? se combinan los cambios de cada una sobre la verdad
                mejor = None
                for x, y in combinations(alts, 2):
                    comb = {k: alts[x].get(k, 0) + alts[y].get(k, 0) - v.get(k, 0) for k in set(alts[x]) | set(alts[y]) | set(v)}
                    d = distancia(comb, r)
                    if mejor is None or d < mejor[0]:
                        mejor = (d, [x, y])
                diag = (["combinación: " + " + ".join(mejor[1])] if mejor and mejor[0] <= 1 else
                        ["sin coincidencia exacta con una o dos trampas; la más cercana: "
                         + min(alts, key=lambda n: distancia(alts[n], r))])
        filas.append({"nombre": nombre, "total": sum(r.values()), "diferencia_total": sum(r.values()) - verdad["total"],
                      "regiones_distintas": len(dif), "correcto": not dif, "diferencias": dif, "diagnostico": diag})
    print(json.dumps(filas, ensure_ascii=False, indent=2))
    print()
    for f in filas:
        if "error" in f:
            print(f"{f['nombre']:14s} ERROR {f['error']}")
            continue
        estado = "✅ correcto" if f["correcto"] else f"❌ {f['regiones_distintas']} regiones distintas"
        print(f"{f['nombre']:14s} total {fmt(f['total']):>15s}  dif {fmt(f['diferencia_total']):>14s}  {estado}  {'; '.join(f['diagnostico'])}")


if __name__ == "__main__":
    main()

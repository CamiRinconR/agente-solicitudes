#!/usr/bin/env python3
"""Revisa los import del código que escribió la IA contra la lista de permitidas (sin IA).

Uso: python dependencias.py archivo.py [archivo.py ...]

Bloquea: paquetes que no son de la biblioteca estándar ni están en permitidas.json (un nombre
inventado puede registrarlo un atacante: slopsquatting) y cualquier intento de instalar paquetes
desde el código (pip, subprocess, os.system).
"""
import ast
import json
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
INSTALAR = re.compile(r"(pip(3)?\s+install|pip\.main|ensurepip|easy_install|conda\s+install|uv\s+pip)", re.I)


def permitidas():
    d = json.loads((AQUI / "permitidas.json").read_text(encoding="utf-8"))["permitidas"]
    return {v["import"] for v in d.values()}


def revisar(ruta):
    texto = Path(ruta).read_text(encoding="utf-8")
    try:
        arbol = ast.parse(texto)
    except SyntaxError as e:
        return {"archivo": str(ruta), "error": f"no se puede leer: {e}"}
    mods = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            mods.add(n.module.split(".")[0])
        elif isinstance(n, ast.Call) and getattr(n.func, "id", "") == "__import__":
            mods.add("__import__ dinámico")
    locales = {p.stem for p in Path(ruta).resolve().parent.glob("*.py")} | {"reglas_base"}
    std = set(sys.stdlib_module_names)
    ok = permitidas()
    no_permitidas = sorted(m for m in mods if m not in std and m not in ok and m not in locales)
    instala = sorted(set(m.group(0) for m in INSTALAR.finditer(texto)))
    return {"archivo": str(ruta), "importa": sorted(mods), "no_permitidas": no_permitidas, "intenta_instalar": instala}


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    malos = 0
    for r in argv:
        res = revisar(r)
        mal = res.get("error") or res["no_permitidas"] or res["intenta_instalar"]
        malos += bool(mal)
        print(f"{'✗' if mal else '✓'} {Path(r).name}: importa {', '.join(res.get('importa', [])) or '—'}"
              + (f" · NO PERMITIDAS: {res['no_permitidas']}" if res.get("no_permitidas") else "")
              + (f" · intenta instalar: {res['intenta_instalar']}" if res.get("intenta_instalar") else "")
              + (f" · {res['error']}" if res.get("error") else ""))
    print("RESUMEN " + json.dumps({"archivos": len(argv), "con_problemas": malos}))
    return 1 if malos else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

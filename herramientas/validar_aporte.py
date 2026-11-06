#!/usr/bin/env python3
"""Filtro automático de aportes (sin IA y sin llaves: no le gasta nada a nadie).

Uso: python herramientas/validar_aporte.py [--base origin/main]

Lo corre GitHub Actions en cada pull request, y también se puede correr a mano. Revisa:
  1. Archivos que no pueden entrar: datos (CSV de más de 200 KB, carpetas datos/ o limpio/, datos de SECOP),
     entornos, cachés, llaves y archivos de configuración de asistentes.
  2. Datos personales en todo lo que el aporte agrega (barrido de gobernanza).
  3. Seguridad de todo código Python agregado o cambiado (compuertas: librerías permitidas, reglas propias y
     Bandit). La excepción son las muestras de baterias/seguridad/malos/, que justamente deben bloquearse.
  4. Que no rompa nada: baterías, la corrida sintética verificada desde cero y las 12 mutantes atrapadas.
  5. Lo que el aporte agrega a las baterías: una muestra de código malo nueva la debe bloquear la compuerta
     de hoy; si no la bloquea, el aporte encontró un hueco, se marca y lo revisa el dueño.
No ejecuta ningún agente: la prueba de efecto con IA la hace solo el dueño, con su licencia (CONTRIBUTING.md).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "herramientas"))
from gobernanza import escanear_texto  # noqa: E402
import dependencias  # noqa: E402
import seguridad  # noqa: E402

PROHIBIDOS = re.compile(r"(^|/)(\.venv|venv|__pycache__|\.claude|\.cursor|\.env|node_modules)(/|$)|(^|/)(datos|limpio)/.*\.csv$"
                        r"|\.(pem|key|p12|pfx|sqlite|db|parquet|xlsx?|zip|gz)$|(^|/)ejemplo-secop/datos/", re.I)
CSV_PERMITIDOS = re.compile(r"^(ejemplo/datos/|baterias/|corridas/[^/]+/caso_conocido/)")
MAX_CSV = 200_000


def git(*a):
    return subprocess.run(["git", *a], cwd=RAIZ, capture_output=True, text=True).stdout


def correr(*a):
    p = subprocess.run([sys.executable, *a], cwd=RAIZ, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def main(argv):
    base = argv[argv.index("--base") + 1] if "--base" in argv else "origin/main"
    cambiados = [l.split("\t") for l in git("diff", "--name-status", f"{base}...HEAD").splitlines() if l.strip()]
    archivos = [(e[0][0], e[-1]) for e in cambiados]
    fallas, avisos = [], []

    for estado, ruta in archivos:
        if estado == "D":
            if ruta.startswith(("herramientas/", "baterias/", "agentes/", "DIRECTRICES", "flujo.js")):
                avisos.append(f"borra {ruta}: lo revisa el dueño")
            continue
        if PROHIBIDOS.search(ruta):
            fallas.append(f"archivo que no puede entrar: {ruta}")
            continue
        p = RAIZ / ruta
        if not p.exists():
            continue
        if ruta.endswith(".csv"):
            if not CSV_PERMITIDOS.match(ruta):
                fallas.append(f"CSV fuera de las carpetas permitidas (ejemplo/datos, baterias, caso_conocido): {ruta}")
            if p.stat().st_size > MAX_CSV:
                fallas.append(f"CSV de más de 200 KB (los datos no se publican): {ruta}")
        if p.suffix in (".py", ".md", ".json", ".csv", ".txt", ".js", ".yml", ".yaml", ".html") and "baterias/privacidad/" not in ruta:
            hall = escanear_texto(p.read_text(encoding="utf-8", errors="ignore"))
            if hall:
                fallas.append(f"posibles datos personales en {ruta}: {hall}")
        if p.suffix == ".py" and "baterias/seguridad/malos/" not in ruta:
            d = dependencias.revisar(p)
            s, _ = seguridad.revisar([p])
            bloqueos = (d.get("no_permitidas") or []) + (d.get("intenta_instalar") or []) + [h["regla"] for h in s[0]["bloquean"]]
            if bloqueos and not ruta.startswith("herramientas/"):
                fallas.append(f"código que no pasa las compuertas: {ruta}: {bloqueos[:4]}")
            elif bloqueos:
                avisos.append(f"herramienta con patrones que la compuerta marcaría: {ruta}: {bloqueos[:3]} (lo revisa el dueño)")
        if "baterias/seguridad/malos/" in ruta and estado == "A":
            d = dependencias.revisar(p)
            s, _ = seguridad.revisar([p])
            if not (d.get("no_permitidas") or d.get("intenta_instalar") or s[0]["bloquean"]):
                avisos.append(f"la muestra nueva {ruta} NO la bloquea la compuerta de hoy: encontró un hueco (valioso); hay que mejorar la compuerta antes de aceptar")

    for nombre, args in [("baterías", ["herramientas/baterias.py"]),
                         ("corrida sintética", ["herramientas/verificar.py", "corridas/2026-11-06-ventas-semestre"])]:
        rc, out = correr(*args)
        if rc != 0 and not any("NO la bloquea" in a for a in avisos):
            fallas.append(f"{nombre} no pasa: {out.strip().splitlines()[-1][:200] if out.strip() else rc}")
    mutantes = sorted((RAIZ / "evidencia/sintetico/mutantes").glob("m*.py"))
    lista = [f"{m.stem}={m}" for m in mutantes]
    rc, out = correr("herramientas/verificar.py", "corridas/2026-11-06-ventas-semestre", "--impl", *lista)
    (RAIZ / "corridas/2026-11-06-ventas-semestre/informe_extra.json").unlink(missing_ok=True)
    sin_fallas = re.findall(r"^(m\d+\w*): sin fallas", out, re.M)
    if sin_fallas != ["m00_referencia_sin_errores"]:
        fallas.append(f"el criterio ya no atrapa todas las mutantes o da falsas alarmas: sin fallas = {sin_fallas}")

    print(f"Aporte: {len(archivos)} archivo(s) cambiados frente a {base}")
    for e, r in archivos:
        print(f"  {e} {r}")
    for a in avisos:
        print(f"  · aviso: {a}")
    for f in fallas:
        print(f"  ✗ {f}")
    estado = "pasa el filtro automático" if not fallas else "no pasa el filtro automático"
    print(f"\n{'✓' if not fallas else '✗'} {estado}. " + ("Sigue la revisión del dueño." if not fallas else "Corrige lo marcado y vuelve a subir."))
    print("RESUMEN " + json.dumps({"fallas": fallas, "avisos": avisos}, ensure_ascii=False))
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

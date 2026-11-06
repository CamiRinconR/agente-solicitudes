#!/usr/bin/env python3
"""Regenera requirements.txt con la huella SHA-256 de cada distribución publicada en PyPI (sin IA).

Uso: python herramientas/fijar_dependencias.py
Toma las versiones ya fijadas en requirements.txt. Agregar una dependencia es una decisión humana (permitidas.json).
"""
import json
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def main():
    req = RAIZ / "requirements.txt"
    fijadas = [l.strip().rstrip("\\").strip() for l in req.read_text().splitlines() if "==" in l]
    salida = ["# Dependencias fijadas con su huella SHA-256 (todas las distribuciones publicadas en PyPI para esa versión).",
              "# Instalar SIEMPRE así:  pip install --require-hashes -r requirements.txt",
              "# Regenerar: python herramientas/fijar_dependencias.py (consulta pypi.org)."]
    for l in fijadas:
        nombre, version = l.split("==")
        url = f"https://pypi.org/pypi/{nombre}/{version}/json"
        d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "agente-solicitudes"}), timeout=60))  # nosec B310
        hs = sorted({u["digests"]["sha256"] for u in d["urls"]})
        salida.append(f"{nombre}=={version} \\")
        salida += [f"    --hash=sha256:{h}" + (" \\" if i < len(hs) - 1 else "") for i, h in enumerate(hs)]
    req.write_text("\n".join(salida) + "\n")
    print(f"requirements.txt: {len(fijadas)} dependencias con huella")


if __name__ == "__main__":
    main()

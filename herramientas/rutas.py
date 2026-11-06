"""Rutas portables: las specs selladas guardan rutas absolutas de la máquina donde se corrieron.
En un clon, cada ruta se busca de nuevo dentro de la carpeta del repositorio (lo que viene después de
«agente-solicitudes/»), sin tocar los archivos sellados."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MARCA = "agente-solicitudes/"


def resolver(ruta):
    # Primero la copia de ESTE repositorio: con dos clones en la misma máquina (el del dueño y el que revisa un aporte,
    # o un worktree), la ruta absoluta sellada existe pero apunta al OTRO clon; verificar contra esos archivos rompe el
    # linaje (y la caja de arena, con razón, no deja leerlos).
    s = str(ruta)
    if MARCA in s:
        q = RAIZ / s.split(MARCA, 1)[1]
        if q.exists():
            return str(q)
    return str(Path(ruta))


def resolver_datos(spec):
    spec["datos"] = {t: resolver(r) for t, r in spec["datos"].items()}
    return spec

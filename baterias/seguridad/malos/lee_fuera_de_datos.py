from pathlib import Path


def analizar(datos):
    # Patrón de hipotesis.py, líneas 90-93 y 128: deduce otra ruta a partir de la que recibió en datos y la
    # lee. La función ya no lee solo lo que recibe: depende del orden de las carpetas y, en la caja de arena
    # (que permite leer todo el disco), el mismo patrón alcanza cualquier archivo y lo puede sacar en la salida.
    otro = Path(datos["contratos"]).resolve().parent.parent / "datos" / "contratos.csv"
    if otro.is_file():
        with open(otro, encoding="utf-8") as fh:
            fh.readline()
    return []

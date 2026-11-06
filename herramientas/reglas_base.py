"""Base para escribir las reglas de una corrida (reglas.py).

Cada regla recibe `datos` ({tabla: ruta_csv}) y `resultado` (lista de filas) y devuelve
(ok, mensaje). Las reglas leen los CSV por su cuenta, así sirven igual para los datos
reales y para el caso con respuesta conocida.

    from reglas_base import regla, leer_csv, aprox

    @regla("R1", "conservacion", "El total del resultado es igual al total de la fuente")
    def r1(datos, resultado):
        ...
        return aprox(a, b), f"resultado {a:,.0f} · fuente {b:,.0f}"
"""
import csv

REGLAS = []


def regla(id, tipo, descripcion):
    def decorar(fn):
        REGLAS.append({"id": id, "tipo": tipo, "descripcion": descripcion, "fn": fn})
        return fn
    return decorar


def leer_csv(ruta):
    """Filas del CSV como diccionarios de texto, sin convertir nada. FAILFAST: una comilla sin cerrar o una
    fila con más o menos campos que el encabezado detienen la lectura; nunca se leen en silencio."""
    with open(ruta, newline="", encoding="utf-8-sig") as fh:
        lector = csv.DictReader(fh, strict=True)
        filas = list(lector)
        cab = lector.fieldnames or []
    if len(cab) == 1 and any(sep in cab[0] for sep in (";", "\t", "|")):
        raise ValueError(f"el encabezado tiene una sola columna con «;», tabulador o «|»: el separador no es la coma")
    for i, f in enumerate(filas, 2):
        if None in f or any(v is None for v in f.values()):
            raise ValueError(f"la línea {i} del CSV no tiene el mismo número de campos que el encabezado")
    return filas


def aprox(a, b, tol=0.5):
    return a is not None and b is not None and abs(float(a) - float(b)) <= tol


def suma(resultado, columna):
    return sum(float(f[columna]) for f in resultado if f.get(columna) is not None)


HIPOTESIS = {}


def hipotesis(id):
    """Registra la prueba de una hipótesis: fn(datos) -> {"valor": número, "linea_base": número o None, "detalle": texto}."""
    def decorar(fn):
        HIPOTESIS[id] = fn
        return fn
    return decorar

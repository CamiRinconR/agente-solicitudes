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
    """Filas del CSV como diccionarios de texto, sin convertir nada."""
    with open(ruta, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


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

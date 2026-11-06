"""Generador B: valor contratado en 2025 por entidad con sede en Medellín (SECOP II).

Solo biblioteca estándar (csv, collections, re, unicodedata); sin pandas.
Sigue spec.json de la corrida 2026-11-06-secop-medellin-2025:

1. Lee la tabla «contratos» fila a fila, en el orden del archivo.
2. Quita repetidos por id_contrato (sin espacios al inicio y al final, en
   mayúsculas) conservando la primera aparición, ANTES de filtrar y sumar.
3. Filtra ciudad = «medellin» (sin espacios, sin tildes, sin mayúsculas) y
   fecha_de_firma con año 2025 (solo la parte de fecha, nunca el texto con hora).
   No filtra por estado_contrato.
4. Agrupa solo por nit_entidad (texto, sin espacios al inicio y al final, sin
   convertirlo a número). Suma valor_del_contrato en aritmética decimal exacta
   (vacío = 0; los ceros cuentan como contrato) y cuenta los contratos.
5. El nombre de cada NIT es el nombre_entidad (solo sin espacios al inicio y al
   final) con más contratos que cuentan; en empate, el menor por puntos de código.
6. Ordena por valor_contratado de mayor a menor y, en empate, por nit_entidad
   ascendente como texto.
"""

import csv
import re
import unicodedata
from collections import Counter

TABLA = "contratos"
ANIO = 2025
CIUDAD = "medellin"

COL_NOMBRE = "nombre_entidad"
COL_NIT = "nit_entidad"
COL_CIUDAD = "ciudad"
COL_ID = "id_contrato"
COL_FECHA = "fecha_de_firma"
COL_VALOR = "valor_del_contrato"
COLUMNAS = (COL_NOMBRE, COL_NIT, COL_CIUDAD, COL_ID, COL_FECHA, COL_VALOR)

# Codificaciones que se prueban en orden; latin-1 nunca falla al decodificar.
CODIFICACIONES = ("utf-8-sig", "cp1252", "latin-1")

# Fecha con el año primero (aaaa-mm-dd, aaaa/mm/dd...) o al final (dd/mm/aaaa, mm/dd/aaaa).
_FECHA_ANIO_PRIMERO = re.compile(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})")
_FECHA_ANIO_AL_FINAL = re.compile(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})(?!\d)")

# Número decimal con punto como separador decimal y sin separador de miles.
_DECIMAL = re.compile(r"([+-]?)([0-9]*)(?:\.([0-9]*))?")


def _ruta_contratos(datos):
    """Ruta del CSV de contratos dentro de datos = {tabla: ruta_csv}."""
    if isinstance(datos, str):
        return datos
    if TABLA in datos:
        return datos[TABLA]
    if len(datos) == 1:
        return next(iter(datos.values()))
    raise KeyError("datos no trae la tabla '%s' (tablas: %s)" % (TABLA, sorted(datos)))


def _normalizar_ciudad(texto):
    """Sin espacios al inicio y al final, sin tildes y sin distinguir mayúsculas."""
    s = unicodedata.normalize("NFKD", texto.strip().casefold())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def _anio_de_firma(texto):
    """Año de la parte de fecha de fecha_de_firma; None si no se reconoce una fecha."""
    s = texto.strip()
    m = _FECHA_ANIO_PRIMERO.match(s)
    if m:
        return int(m.group(1))
    m = _FECHA_ANIO_AL_FINAL.match(s)
    if m:
        return int(m.group(3))
    return None


def _valor_exacto(texto):
    """valor_del_contrato como (entero, escala, resto): valor = entero / 10**escala + resto.

    El caso normal (dígitos con punto decimal opcional) se guarda exacto en
    enteros de Python, para que la suma no acumule errores de coma flotante.
    Vacío = 0. Lo que no tenga esa forma pero sí lea float() (p. ej. notación
    científica) va en «resto»; lo que no se pueda leer o no sea finito suma 0.
    """
    s = texto.strip()
    if not s:
        return 0, 0, 0.0
    m = _DECIMAL.fullmatch(s)
    if m and (m.group(2) or m.group(3)):
        signo, parte_entera, parte_decimal = m.group(1), m.group(2) or "", m.group(3) or ""
        digitos = (parte_entera + parte_decimal) or "0"
        entero = int(digitos)
        if signo == "-":
            entero = -entero
        return entero, len(parte_decimal), 0.0
    try:
        f = float(s)
    except ValueError:
        return 0, 0, 0.0
    if f != f or f in (float("inf"), float("-inf")):
        return 0, 0, 0.0
    return 0, 0, f


class _Entidad:
    """Acumulado de un NIT: suma exacta del valor, contratos y nombres vistos."""

    __slots__ = ("entero", "escala", "resto", "contratos", "nombres")

    def __init__(self):
        self.entero = 0
        self.escala = 0
        self.resto = 0.0
        self.contratos = 0
        self.nombres = Counter()

    def sumar(self, entero, escala, resto):
        if escala > self.escala:
            self.entero *= 10 ** (escala - self.escala)
            self.escala = escala
        self.entero += entero * 10 ** (self.escala - escala)
        self.resto += resto

    def valor(self):
        # int / int en Python da el float correctamente redondeado.
        return self.entero / 10 ** self.escala + self.resto

    def nombre(self):
        # Más contratos primero; en empate, el menor por puntos de código.
        return min(self.nombres.items(), key=lambda par: (-par[1], par[0]))[0]


def _indices(encabezado):
    """Posición de cada columna necesaria (nombres comparados sin espacios ni mayúsculas)."""
    normal = [h.strip().lstrip("﻿").strip().lower() for h in encabezado]
    indices = {}
    for col in COLUMNAS:
        if col not in normal:
            raise ValueError("falta la columna '%s' en el CSV (columnas: %s)" % (col, encabezado))
        indices[col] = normal.index(col)
    return indices


def _procesar(ruta, codificacion):
    entidades = {}
    with open(ruta, newline="", encoding=codificacion) as f:
        lector = csv.reader(f)
        encabezado = next(lector, None)
        if encabezado is None:
            return entidades
        ix = _indices(encabezado)
        i_nombre, i_nit, i_ciudad = ix[COL_NOMBRE], ix[COL_NIT], ix[COL_CIUDAD]
        i_id, i_fecha, i_valor = ix[COL_ID], ix[COL_FECHA], ix[COL_VALOR]
        ancho = max(ix.values()) + 1

        vistos = set()
        for fila in lector:
            if not fila:
                continue  # línea en blanco
            if len(fila) < ancho:
                fila = fila + [""] * (ancho - len(fila))

            # Contrato: id_contrato sin espacios y en mayúsculas; cuenta la
            # primera aparición en el archivo, antes de filtrar.
            clave = fila[i_id].strip().upper()
            if clave in vistos:
                continue
            vistos.add(clave)

            if _normalizar_ciudad(fila[i_ciudad]) != CIUDAD:
                continue
            if _anio_de_firma(fila[i_fecha]) != ANIO:
                continue

            nit = fila[i_nit].strip()
            ent = entidades.get(nit)
            if ent is None:
                ent = entidades[nit] = _Entidad()
            ent.sumar(*_valor_exacto(fila[i_valor]))
            ent.contratos += 1
            ent.nombres[fila[i_nombre].strip()] += 1
    return entidades


def analizar(datos):
    """Una fila por nit_entidad con contratos firmados en 2025 en Medellín.

    datos = {tabla: ruta_csv}; usa la tabla «contratos».
    Devuelve list[dict] con nit_entidad (texto), entidad (texto),
    valor_contratado (float, sin redondear) y numero_contratos (int),
    ordenada por valor_contratado descendente y nit_entidad ascendente.
    """
    ruta = _ruta_contratos(datos)
    entidades = None
    for codificacion in CODIFICACIONES:
        try:
            entidades = _procesar(ruta, codificacion)
            break
        except UnicodeDecodeError:
            continue

    filas = [
        {
            "nit_entidad": nit,
            "entidad": ent.nombre(),
            "valor_contratado": ent.valor(),
            "numero_contratos": ent.contratos,
        }
        for nit, ent in entidades.items()
    ]
    filas.sort(key=lambda fila: (-fila["valor_contratado"], fila["nit_entidad"]))
    return filas

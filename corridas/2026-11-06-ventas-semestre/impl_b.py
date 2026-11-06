"""Generador B: ventas netas sin IVA por región, primer semestre de 2026.

Solo biblioteca estándar (csv, datetime, decimal, io, re, unicodedata); sin pandas.
Sigue spec.json de la corrida 2026-11-06-ventas-semestre:

- Período: 2026-01-01 <= fecha <= 2026-06-30, bordes incluidos; cada documento en su fecha.
- Fechas: aaaa-mm-dd como ISO y toda fecha con barras como día/mes/año (también las
  ambiguas). Ningún otro formato se adivina: si aparece, el análisis se detiene.
- Documentos: se quitan repetidos por numero_documento (sin espacios, en mayúsculas)
  quedándose con la primera aparición, antes de filtrar y sumar.
- Ventas netas = suma de subtotal de FV menos suma de subtotal de NC (tipo sin espacios,
  en mayúsculas); otros tipos no cuentan; iva y total nunca se usan.
- Cliente: cliente_id sin espacios al inicio y al final y en mayúsculas, en ventas y en el
  maestro. La región es la del registro con fecha_actualizacion más reciente (empate: el
  último del archivo, S3). Sin cliente_id o con un código que no está en el maestro, el
  documento va a «Sin región».
- Regiones: se normalizan (sin espacios sobrantes, minúsculas, sin tildes, sin puntos) y se
  llevan a las cinco oficiales; si la región vigente de un cliente no encaja, el análisis se
  detiene con un error que nombra el cliente y la región (S2).
- Salida: siempre seis filas (S1): las cinco oficiales de mayor a menor ventas_netas
  (empates en el orden de la lista oficial) y «Sin región» de última.
"""

import csv
import datetime
import io
import re
import unicodedata
from decimal import Decimal, InvalidOperation

INICIO = datetime.date(2026, 1, 1)
FIN = datetime.date(2026, 6, 30)

REGIONES_OFICIALES = ("Antioquia", "Bogotá D.C.", "Caldas", "Risaralda", "Valle del Cauca")
SIN_REGION = "Sin región"

# Clave normalizada de la región -> etiqueta oficial, tal cual la lista de la spec.
REGION_POR_CLAVE = {
    "antioquia": "Antioquia",
    "bogota dc": "Bogotá D.C.",
    "bogota": "Bogotá D.C.",
    "caldas": "Caldas",
    "risaralda": "Risaralda",
    "valle del cauca": "Valle del Cauca",
    "valle": "Valle del Cauca",
}

COLUMNAS_VENTAS = ("numero_documento", "tipo_documento", "fecha", "cliente_id", "subtotal")
COLUMNAS_CLIENTES = ("cliente_id", "region", "fecha_actualizacion")

# Hora opcional después de la fecha (00:00, 00:00:00); la fecha manda.
_HORA = r"(?:[ T][0-9]{1,2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?)?"
_FECHA_ISO = re.compile(r"([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})" + _HORA)
_FECHA_BARRAS = re.compile(r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})" + _HORA)


def leer_fecha(texto):
    """aaaa-mm-dd como ISO; toda fecha con barras como día/mes/año. Nada más se acepta."""
    limpio = (texto or "").strip()
    encontrado = _FECHA_ISO.fullmatch(limpio)
    if encontrado:
        anio, mes, dia = (int(g) for g in encontrado.groups())
    else:
        encontrado = _FECHA_BARRAS.fullmatch(limpio)
        if encontrado is None:
            raise ValueError(f"fecha ilegible {texto!r} (se esperaba aaaa-mm-dd o dd/mm/aaaa)")
        dia, mes, anio = (int(g) for g in encontrado.groups())
    try:
        return datetime.date(anio, mes, dia)
    except ValueError:
        raise ValueError(f"fecha inexistente {texto!r}") from None


def leer_numero(texto):
    """Número decimal exacto; vacío, texto o no finito detienen el análisis."""
    limpio = (texto or "").strip()
    try:
        valor = Decimal(limpio)
    except InvalidOperation:
        raise ValueError(f"número ilegible {texto!r}") from None
    if not valor.is_finite():
        raise ValueError(f"número no finito {texto!r}")
    return valor


def clave_region(texto):
    """Sin tildes, minúsculas, sin puntos y sin espacios sobrantes."""
    descompuesto = unicodedata.normalize("NFKD", texto or "")
    sin_tildes = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return " ".join(sin_tildes.lower().replace(".", "").split())


def codigo_cliente(texto):
    """cliente_id sin espacios al inicio y al final, en mayúsculas."""
    return (texto or "").strip().upper()


def _sin_espacios_mayusculas(texto):
    return "".join((texto or "").split()).upper()


def _decodificar(crudo):
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            return crudo.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return crudo.decode("latin-1")


def _nombre_columna(texto):
    # BOM de UTF-8 tal cual o leído como cp1252 ("ï»¿").
    return texto.replace("﻿", "").replace("ï»¿", "").strip().strip('"').strip().lower()


def _leer_tabla(ruta, requeridas, tabla):
    """Lee un CSV y devuelve sus filas como dicts con las columnas requeridas (y la línea)."""
    with open(ruta, "rb") as archivo:
        texto = _decodificar(archivo.read())

    primera = next((linea for linea in texto.splitlines() if linea.strip()), "")
    delimitador = ","
    for candidato in (",", ";", "\t", "|"):
        nombres = {_nombre_columna(c) for c in primera.split(candidato)}
        if all(r in nombres for r in requeridas):
            delimitador = candidato
            break

    lector = csv.reader(io.StringIO(texto, newline=""), delimiter=delimitador)
    indices = None
    filas = []
    for registro in lector:
        if not any(campo.strip() for campo in registro):
            continue  # líneas en blanco
        if indices is None:
            encabezado = [_nombre_columna(c) for c in registro]
            faltan = [r for r in requeridas if r not in encabezado]
            if faltan:
                raise ValueError(f"{tabla}: faltan las columnas {faltan} en {ruta}")
            indices = {r: encabezado.index(r) for r in requeridas}
            continue
        fila = {r: (registro[i] if i < len(registro) else "") for r, i in indices.items()}
        fila["_linea"] = lector.line_num
        filas.append(fila)
    if indices is None:
        raise ValueError(f"{tabla}: archivo vacío {ruta}")
    return filas


def _regiones_vigentes(clientes):
    """Código normalizado -> región oficial del registro más reciente del maestro."""
    vigente = {}
    for fila in clientes:
        codigo = codigo_cliente(fila["cliente_id"])
        if not codigo:
            continue  # una fila del maestro sin código no identifica a ningún cliente
        try:
            fecha = leer_fecha(fila["fecha_actualizacion"])
        except ValueError as error:
            raise ValueError(
                f"clientes, línea {fila['_linea']}, cliente {codigo}: fecha_actualizacion: {error}"
            ) from None
        actual = vigente.get(codigo)
        if actual is None or fecha >= actual[0]:  # empate: manda el último del archivo (S3)
            vigente[codigo] = (fecha, fila["region"])

    region_de = {}
    for codigo, (_, region_original) in vigente.items():
        etiqueta = REGION_POR_CLAVE.get(clave_region(region_original))
        if etiqueta is None:
            raise ValueError(
                f"La región vigente del cliente {codigo} es {region_original!r} y no encaja en "
                f"ninguna región oficial ({', '.join(REGIONES_OFICIALES)}); "
                "el análisis se detiene (supuesto S2)."
            )
        region_de[codigo] = etiqueta
    return region_de


def _como_numero(valor):
    return int(valor) if valor == valor.to_integral_value() else float(valor)


def analizar(datos):
    ventas = _leer_tabla(datos["ventas"], COLUMNAS_VENTAS, "ventas")
    clientes = _leer_tabla(datos["clientes"], COLUMNAS_CLIENTES, "clientes")
    region_de = _regiones_vigentes(clientes)

    totales = {etiqueta: Decimal(0) for etiqueta in REGIONES_OFICIALES + (SIN_REGION,)}
    vistos = set()
    for fila in ventas:
        documento = _sin_espacios_mayusculas(fila["numero_documento"])
        if documento in vistos:
            continue  # repetido: cuenta solo la primera aparición, antes de cualquier filtro
        vistos.add(documento)

        tipo = _sin_espacios_mayusculas(fila["tipo_documento"])
        if tipo == "FV":
            signo = 1
        elif tipo == "NC":
            signo = -1
        else:
            continue

        try:
            fecha = leer_fecha(fila["fecha"])
        except ValueError as error:
            raise ValueError(
                f"ventas, línea {fila['_linea']}, documento {documento}: {error}"
            ) from None
        if not (INICIO <= fecha <= FIN):
            continue

        try:
            subtotal = leer_numero(fila["subtotal"])
        except ValueError as error:
            raise ValueError(
                f"ventas, línea {fila['_linea']}, documento {documento}: subtotal: {error}"
            ) from None

        codigo = codigo_cliente(fila["cliente_id"])
        etiqueta = region_de.get(codigo, SIN_REGION) if codigo else SIN_REGION
        totales[etiqueta] += signo * subtotal

    # Orden estable: a igual valor, queda el orden de la lista oficial.
    oficiales = sorted(REGIONES_OFICIALES, key=lambda etiqueta: -totales[etiqueta])
    return [
        {"region": etiqueta, "ventas_netas": _como_numero(totales[etiqueta])}
        for etiqueta in oficiales + [SIN_REGION]
    ]

"""Generador A: valor contratado en 2025 por entidad con sede en Medellín (SECOP II).

Sigue spec.json de la corrida 2026-11-06-secop-medellin-2025:

1. Lee la tabla «contratos» con todas las columnas como texto (nada se convierte
   solo: el NIT conserva sus 9 o 10 dígitos y nunca queda como «890900286.0»).
2. Contrato único: id_contrato sin espacios al inicio y al final y en mayúsculas;
   si se repite, se conserva la primera aparición en el archivo. Se hace sobre el
   archivo completo, ANTES de filtrar y sumar.
3. Sede en Medellín: ciudad sin espacios al inicio y al final, sin tildes y sin
   distinguir mayúsculas igual a «medellin».
4. Contratado en 2025: el año de la parte de fecha de fecha_de_firma es 2025
   (del 1 de enero al 31 de diciembre, los dos días completos; la hora no cuenta).
5. Una fila por nit_entidad (texto sin espacios al inicio y al final), con la suma
   de valor_del_contrato (vacío = 0; nunca valor_facturado ni valor_pagado), el
   número de id_contrato distintos y, como nombre, el nombre_entidad con más
   contratos de 2025 dentro del NIT (empate: el primero por puntos de código).
   No se filtra por estado; los contratos de valor cero cuentan y suman 0.
6. Orden: valor_contratado de mayor a menor; en empate, nit_entidad ascendente.

Solo usa pandas: la implementación no lee nada fuera de las rutas que recibe.
"""

import pandas as pd

TABLA = "contratos"
ANIO = "2025"
CIUDAD = "medellin"

COL_NOMBRE = "nombre_entidad"
COL_NIT = "nit_entidad"
COL_CIUDAD = "ciudad"
COL_ID = "id_contrato"
COL_FECHA = "fecha_de_firma"
COL_VALOR = "valor_del_contrato"
COLUMNAS = (COL_NOMBRE, COL_NIT, COL_CIUDAD, COL_ID, COL_FECHA, COL_VALOR)

# Marcas diacríticas combinantes que deja la descomposición NFKD (la tilde de «í», etc.).
_MARCAS = r"[̀-ͯ᪰-᫿᷀-᷿⃐-⃿︠-︯]"
# Año al comienzo: aaaa-mm-dd…, aaaa/mm/dd…, aaaammdd… (formato real: aaaa-mm-ddThh:mm:ss.mmm).
_ANIO_PRIMERO = r"^(\d{4})(?:\d{4})?(?!\d)"
# Año al final de la fecha: dd/mm/aaaa o mm/dd/aaaa (en los dos casos el año es el mismo).
_ANIO_ULTIMO = r"^\d{1,2}[-/.]\d{1,2}[-/.](\d{4})(?!\d)"


def _ruta_de_contratos(datos):
    """Devuelve la ruta del CSV de contratos dentro de datos = {tabla: ruta_csv}."""
    if isinstance(datos, str):
        return datos
    if TABLA in datos:
        return datos[TABLA]
    if len(datos) == 1:
        return next(iter(datos.values()))
    raise KeyError(f"No está la tabla «{TABLA}» en datos (tablas: {sorted(datos)})")


def _separador(ruta, codificacion):
    """Separador de la cabecera: el que más se repite entre , ; tabulador y |."""
    with open(ruta, "r", encoding=codificacion, newline="") as archivo:
        cabecera = archivo.readline()
    candidatos = (",", ";", "\t", "|")
    mejor = max(candidatos, key=cabecera.count)
    return mejor if cabecera.count(mejor) > 0 else ","


def _leer_contratos(ruta):
    """Lee solo las columnas necesarias, todas como texto (vacío = "")."""
    error = None
    for codificacion in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            tabla = pd.read_csv(
                ruta,
                sep=_separador(ruta, codificacion),
                dtype=object,
                na_filter=False,
                keep_default_na=False,
                index_col=False,
                encoding=codificacion,
                usecols=lambda c: str(c).strip().lower() in COLUMNAS,
            )
            break
        except UnicodeDecodeError as e:
            error = e
    else:
        raise error
    tabla.columns = [str(c).strip().lower() for c in tabla.columns]
    faltan = [c for c in COLUMNAS if c not in tabla.columns]
    if faltan:
        raise ValueError(f"Faltan columnas en {ruta}: {faltan}")
    # Por si alguna fila viene corta: todo queda como texto, nunca NaN.
    return tabla[list(COLUMNAS)].fillna("").astype(object)


def _ciudad_normalizada(ciudad):
    """Sin espacios al inicio y al final, sin tildes y sin mayúsculas."""
    return (
        ciudad.str.strip()
        .str.normalize("NFKD")
        .str.replace(_MARCAS, "", regex=True)
        .str.casefold()
        .str.strip()
    )


def _anio_de_firma(fecha):
    """Año (texto de 4 dígitos) de la parte de fecha; NaN si no se reconoce."""
    fecha = fecha.str.strip()
    anio = fecha.str.extract(_ANIO_PRIMERO, expand=False)
    return anio.fillna(fecha.str.extract(_ANIO_ULTIMO, expand=False))


def _valor_numerico(valor):
    """Decimal con punto, sin separador de miles; vacío (o ilegible) = 0."""
    texto = valor.str.strip()
    numero = pd.to_numeric(texto.mask(texto == "", "0"), errors="coerce").astype(float)
    # NaN (texto ilegible) e infinitos no son un valor de contrato: cuentan como 0.
    return numero.where(numero.abs() < float("inf"), 0.0)


def analizar(datos):
    """Una fila por nit_entidad con contratos firmados en 2025 en Medellín.

    datos = {tabla: ruta_csv}; usa la tabla «contratos». Devuelve list[dict] con
    nit_entidad (texto), entidad (texto), valor_contratado (float) y
    numero_contratos (int), en el orden de la spec.
    """
    contratos = _leer_contratos(_ruta_de_contratos(datos))

    # Contrato único en todo el archivo, antes de filtrar y sumar.
    contratos = contratos.assign(_id=contratos[COL_ID].str.strip().str.upper())
    contratos = contratos.drop_duplicates(subset="_id", keep="first")

    # Solo Medellín y solo firmados en 2025 (la hora de la firma no importa).
    contratos = contratos[_ciudad_normalizada(contratos[COL_CIUDAD]) == CIUDAD]
    contratos = contratos[_anio_de_firma(contratos[COL_FECHA]) == ANIO]
    if contratos.empty:
        return []

    contratos = contratos.assign(
        _nit=contratos[COL_NIT].str.strip(),
        _nombre=contratos[COL_NOMBRE].str.strip(),
        _valor=_valor_numerico(contratos[COL_VALOR]),
    )

    por_nit = contratos.groupby("_nit", sort=False)
    resumen = pd.DataFrame(
        {
            "valor": por_nit["_valor"].sum(),
            "numero": por_nit["_id"].nunique(),
        }
    )

    # Nombre: el de más contratos dentro del NIT; empate por puntos de código.
    elegido = {}
    for (nit, nombre), cuantos in contratos.groupby(["_nit", "_nombre"], sort=False).size().items():
        actual = elegido.get(nit)
        if actual is None or cuantos > actual[1] or (cuantos == actual[1] and nombre < actual[0]):
            elegido[nit] = (nombre, cuantos)

    filas = [
        {
            "nit_entidad": str(fila.Index),
            "entidad": str(elegido[fila.Index][0]),
            "valor_contratado": float(fila.valor) + 0.0,
            "numero_contratos": int(fila.numero),
        }
        for fila in resumen.itertuples()
    ]
    filas.sort(key=lambda f: (-f["valor_contratado"], f["nit_entidad"]))
    return filas

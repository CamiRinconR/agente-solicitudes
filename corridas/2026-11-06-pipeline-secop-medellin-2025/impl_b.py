"""Generador B · etapa 2 (Procesamiento).

Valor contratado en 2025 por cada entidad con sede en Medellín, según SECOP II:
una fila por nit_entidad con nit_entidad, entidad, valor_contratado y
numero_contratos, tal como lo pide spec.json de la corrida.

Enfoque B: solo biblioteca estándar (csv, decimal, re, datetime, collections).
Función pura: lee los datos que recibe, no escribe ni borra archivos, no usa red
ni ejecuta comandos. Toda fila leída se usa o se excluye con su motivo; lo que
se limpia o se avisa en una fila usada se cuenta en «marcadas» (nada se borra
en silencio).

Decisiones de la spec que este código aplica:
- Contrato = id_contrato sin espacios al inicio y al final y en mayúsculas; vale la
  primera aparición en el orden del archivo y los repetidos se quitan ANTES de mirar
  la fecha (S6; nunca se depura por entidad, valor y fecha: L08).
- Fecha leída por formato: aaaa-mm-dd por sus 10 primeros caracteres, dd/mm/aaaa por
  su año (caracteres 7 a 10). Nada de lectores de formatos mezclados (L01) ni de
  comparar el texto con hora contra «2025-12-31» (L02).
- Valor: decimal con punto, sumado tal como figura y sin redondear; vacío = 0 y el
  contrato cuenta (S3).
- Entidad: nit_entidad como texto sin espacios al inicio y al final, nunca como
  número; una fila por NIT aunque tenga varios nombres o códigos (S1); se muestra el
  nombre con más contratos que cuentan dentro del NIT, empate por min() (S2, S4).
- No se filtra por ciudad, estado ni naturaleza de la entidad (S5, S7).
"""

import csv
import datetime
import decimal
import re
from collections import Counter

__all__ = ["analizar", "conciliar"]

TABLA = "contratos"

# Columnas que usa la spec (columnas_usadas); codigo_entidad no se usa (S1).
COL_ID = "id_contrato"
COL_NIT = "nit_entidad"
COL_NOMBRE = "nombre_entidad"
COL_FECHA = "fecha_de_firma"
COL_VALOR = "valor_del_contrato"
COLUMNAS = (COL_ID, COL_NIT, COL_NOMBRE, COL_FECHA, COL_VALOR)

# «Contratado en 2025»: del 2025-01-01 al 2025-12-31, los dos días completos.
ANIO = "2025"
DESDE = ANIO + "-01-01"
HASTA = ANIO + "-12-31"

# Formatos de fecha_de_firma (se mira solo cómo empieza el texto).
EMPIEZA_ISO = r"[0-9]{4}-[0-9]{2}-[0-9]{2}"  # aaaa-mm-dd, con o sin «T» y hora
EMPIEZA_DMA = r"[0-9]{2}/[0-9]{2}/[0-9]{4}"  # dd/mm/aaaa, día primero, con o sin hora
# Número con punto decimal y sin separador de miles.
NUMERO = r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
SOLO_DIGITOS = r"[0-9]+"

# Umbrales con que la spec reporta valores de valor_del_contrato: se avisan,
# nunca se excluyen ni se corrigen (se suman tal como figuran).
VALOR_SIMBOLICO = decimal.Decimal(10)  # mayores que 0 y menores que 10 pesos
VALOR_ALTO = decimal.Decimal(100_000_000_000)  # por encima de 100.000 millones

# Motivos de exclusión, en su orden de prioridad (cada fila va a uno solo).
EXCLUSIONES = ("repetido_id_contrato", "sin_fecha_de_firma", "fuera_de_2025")

# Motivos de marca: filas que se usan, pero con algo que avisar.
MARCAS = (
    "valor_cero",  # cuenta 1 contrato y suma 0 (glosario)
    "valor_mayor_que_0_y_menor_que_10",  # simbólico: se suma tal cual
    "valor_mayor_de_100_mil_millones",  # alto: se reporta, no se excluye (P3)
    "valor_negativo",  # se suma tal cual; R5 vigila el total de la fila
    "valor_vacio_tomado_como_0",  # S3
    "valor_no_numerico_tomado_como_0",  # S3 extendido: no es número con punto
    "nit_vacio_o_no_numerico",  # R5: nit_entidad son solo dígitos
    "nombre_entidad_vacio",  # R5: entidad no vacía
    "nombre_agrupado_bajo_otro_nombre_del_nit",  # S1/S2: el NIT sale con otro nombre
    "id_contrato_vacio",
    "id_contrato_con_espacios_o_minusculas",  # se comparó normalizado
    "nit_con_espacios_recortados",
    "nombre_con_espacios_recortados",
    "fecha_con_espacios_recortados",
    "valor_con_espacios_recortados",
    "fecha_dd_mm_aaaa_leida_por_su_anio",
    "fecha_que_no_existe_en_el_calendario",  # cuenta por su texto, pero se avisa
    "texto_leido_en_latin1",  # el archivo no era UTF-8
)

SEPARADORES = (",", ";", "\t", "|")
CODIFICACIONES = ("utf-8-sig", "latin-1")


# --------------------------------------------------------------------------
# Lectura
# --------------------------------------------------------------------------


def _texto(valor):
    """Una celda como texto, sin convertirla a número."""
    if valor is None:
        return ""
    if isinstance(valor, str):
        return valor
    if isinstance(valor, bool):
        return str(valor)
    if isinstance(valor, float):
        if valor != valor:  # NaN de un lector que ya convirtió los vacíos
            return ""
        if valor.is_integer():  # nunca «.0» en un NIT que llegó convertido
            return str(int(valor))
        return repr(valor)
    texto = str(valor)
    return "" if texto in ("nan", "NaN", "NaT", "None", "<NA>") else texto


def _nombre_columna(nombre):
    return _texto(nombre).replace("﻿", "").strip().strip("\"'").strip().lower()


def _separador(primera_linea):
    """El separador con el que el encabezado trae más columnas de la spec."""
    mejor, mejor_n = ",", -1
    for sep in SEPARADORES:
        nombres = {_nombre_columna(c) for c in primera_linea.rstrip("\r\n").split(sep)}
        n = sum(1 for c in COLUMNAS if c in nombres)
        if n > mejor_n:
            mejor, mejor_n = sep, n
    return mejor


def _exigir_columnas(presentes):
    faltan = [c for c in COLUMNAS if c not in presentes]
    if faltan:
        raise ValueError("faltan columnas en «%s»: %s" % (TABLA, ", ".join(faltan)))


def _leer_csv(ruta):
    """Filas del CSV como dicts (columna normalizada -> texto) y la codificación usada."""
    for codificacion in CODIFICACIONES:
        try:
            with open(ruta, "r", encoding=codificacion, newline="") as archivo:
                sep = _separador(archivo.readline())
                archivo.seek(0)
                lector = csv.reader(archivo, delimiter=sep)
                encabezado = next(lector, [])
                filas = [fila for fila in lector if fila]  # las líneas en blanco no son filas
            break
        except UnicodeDecodeError:
            continue
    columnas = [_nombre_columna(c) for c in encabezado]
    _exigir_columnas(set(columnas))
    return [dict(zip(columnas, fila)) for fila in filas], codificacion


def _filas_normalizadas(registros):
    filas = [{_nombre_columna(k): v for k, v in registro.items()} for registro in registros]
    if filas:
        presentes = set()
        for fila in filas:
            presentes.update(fila)
        _exigir_columnas(presentes)
    return filas


def _cargar(datos):
    """Acepta {tabla: ruta}, una ruta, una lista de filas o una tabla ya leída."""
    fuente = datos
    if isinstance(datos, dict):
        if TABLA in datos:
            fuente = datos[TABLA]
        elif len(datos) == 1:
            fuente = next(iter(datos.values()))
        else:
            raise KeyError("no llegó la tabla «%s»" % TABLA)
    if isinstance(fuente, (list, tuple)):
        return _filas_normalizadas(fuente), None
    if hasattr(fuente, "to_dict") and hasattr(fuente, "columns"):
        _exigir_columnas({_nombre_columna(c) for c in fuente.columns})
        return _filas_normalizadas(fuente.to_dict(orient="records")), None
    return _leer_csv(str(fuente))


# --------------------------------------------------------------------------
# Reglas de negocio por fila
# --------------------------------------------------------------------------


def _existe(anio, mes, dia):
    try:
        datetime.date(int(anio), int(mes), int(dia))
        return True
    except ValueError:
        return False


def _leer_fecha(texto):
    """(cae en 2025, se leyó día primero, existe en el calendario) o None sin formato."""
    if re.match(EMPIEZA_ISO, texto):
        dia = texto[:10]
        return DESDE <= dia <= HASTA, False, _existe(dia[0:4], dia[5:7], dia[8:10])
    if re.match(EMPIEZA_DMA, texto):
        anio = texto[6:10]
        return anio == ANIO, True, _existe(anio, texto[3:5], texto[0:2])
    return None


def _leer_valor(texto):
    """(valor decimal, marca o None): vacío y no numérico se toman como 0 y se marcan."""
    if texto == "":
        return decimal.Decimal(0), "valor_vacio_tomado_como_0"
    if re.fullmatch(NUMERO, texto):
        return decimal.Decimal(texto), None
    return decimal.Decimal(0), "valor_no_numerico_tomado_como_0"


def _marcas_de_valor(valor):
    if valor == 0:
        return ["valor_cero"]
    if valor < 0:
        return ["valor_negativo"]
    if valor < VALOR_SIMBOLICO:
        return ["valor_mayor_que_0_y_menor_que_10"]
    if valor > VALOR_ALTO:
        return ["valor_mayor_de_100_mil_millones"]
    return []


def _elegir_nombre(nombres):
    """El nombre con más contratos que cuentan; empate: min(). Un nombre vacío solo
    se elige si el NIT no trae ninguno con texto (R5 pide entidad no vacía)."""
    candidatos = {n: k for n, k in nombres.items() if n != ""} or dict(nombres)
    tope = max(candidatos.values())
    return min(n for n, k in candidatos.items() if k == tope)


# --------------------------------------------------------------------------
# Proceso
# --------------------------------------------------------------------------


def _procesar(datos):
    filas, codificacion = _cargar(datos)
    excluidas = dict.fromkeys(EXCLUSIONES, 0)
    marcadas = dict.fromkeys(MARCAS, 0)
    vistos = set()
    grupos = {}  # nit -> {"valor": Decimal, "n": int, "nombres": Counter}
    usadas = 0

    with decimal.localcontext() as contexto:
        contexto.prec = 60  # la suma no se redondea en la práctica
        for fila in filas:
            # 1. Repetidos por id_contrato, antes de mirar la fecha (S6).
            id_crudo = _texto(fila.get(COL_ID))
            id_contrato = id_crudo.strip().upper()
            if id_contrato in vistos:
                excluidas["repetido_id_contrato"] += 1
                continue
            vistos.add(id_contrato)

            # 2. Fecha de firma por formato; 3. año 2025, los dos días completos.
            fecha_cruda = _texto(fila.get(COL_FECHA))
            fecha = _leer_fecha(fecha_cruda.strip())
            if fecha is None:
                excluidas["sin_fecha_de_firma"] += 1
                continue
            en_anio, dia_primero, existe = fecha
            if not en_anio:
                excluidas["fuera_de_2025"] += 1
                continue

            # La fila se usa: valor, entidad y lo que haya que avisar.
            usadas += 1
            marcas = []
            valor_crudo = _texto(fila.get(COL_VALOR))
            valor, marca_valor = _leer_valor(valor_crudo.strip())
            if marca_valor:
                marcas.append(marca_valor)
            else:
                marcas.extend(_marcas_de_valor(valor))

            nit_crudo = _texto(fila.get(COL_NIT))
            nit = nit_crudo.strip()
            nombre_crudo = _texto(fila.get(COL_NOMBRE))
            nombre = nombre_crudo.strip()

            if not re.fullmatch(SOLO_DIGITOS, nit):
                marcas.append("nit_vacio_o_no_numerico")
            if nombre == "":
                marcas.append("nombre_entidad_vacio")
            if id_contrato == "":
                marcas.append("id_contrato_vacio")
            elif id_crudo != id_contrato:
                marcas.append("id_contrato_con_espacios_o_minusculas")
            for crudo, limpio, marca in (
                (nit_crudo, nit, "nit_con_espacios_recortados"),
                (nombre_crudo, nombre, "nombre_con_espacios_recortados"),
                (fecha_cruda, fecha_cruda.strip(), "fecha_con_espacios_recortados"),
                (valor_crudo, valor_crudo.strip(), "valor_con_espacios_recortados"),
            ):
                if crudo != limpio:
                    marcas.append(marca)
            if dia_primero:
                marcas.append("fecha_dd_mm_aaaa_leida_por_su_anio")
            if not existe:
                marcas.append("fecha_que_no_existe_en_el_calendario")
            if codificacion == "latin-1":
                marcas.append("texto_leido_en_latin1")
            for marca in marcas:
                marcadas[marca] += 1

            grupo = grupos.get(nit)
            if grupo is None:
                grupo = grupos[nit] = {"valor": decimal.Decimal(0), "n": 0, "nombres": Counter()}
            grupo["valor"] += valor
            grupo["n"] += 1
            grupo["nombres"][nombre] += 1

    resultado = []
    for nit, grupo in grupos.items():
        entidad = _elegir_nombre(grupo["nombres"])
        marcadas["nombre_agrupado_bajo_otro_nombre_del_nit"] += grupo["n"] - grupo["nombres"][entidad]
        resultado.append(
            {
                "nit_entidad": nit,
                "entidad": entidad,
                "valor_contratado": float(grupo["valor"]),
                "numero_contratos": int(grupo["n"]),
            }
        )
    # Orden: valor_contratado de mayor a menor; en empate, nit_entidad ascendente.
    resultado.sort(key=lambda f: (-f["valor_contratado"], f["nit_entidad"]))

    conciliacion = {
        "filas_leidas": len(filas),
        "usadas": usadas,
        "excluidas": excluidas,
        "marcadas": marcadas,
    }
    return resultado, conciliacion


def analizar(datos):
    """Una fila por nit_entidad con al menos un contrato firmado en 2025.

    Claves: nit_entidad (texto), entidad (texto), valor_contratado (float, sin
    redondear) y numero_contratos (int). Orden: valor_contratado de mayor a menor
    y, en empate, nit_entidad ascendente como texto.
    """
    return _procesar(datos)[0]


def conciliar(datos):
    """Cuentas de la corrida: filas_leidas = usadas + suma de excluidas.

    excluidas trae los tres motivos de la spec (repetido_id_contrato,
    sin_fecha_de_firma, fuera_de_2025), cada fila en uno solo y en ese orden de
    prioridad. marcadas cuenta filas usadas con algo que avisar; una fila puede
    tener varias marcas.
    """
    return _procesar(datos)[1]

"""Prueba de las hipótesis de la corrida (etapa 3 · Análisis), calculada directo desde el CSV crudo.

Cada función recibe datos = {"contratos": ruta del CSV crudo} (el mismo que reciben las reglas) y lee
solo esa ruta: no abre la capa limpia ni ninguna otra. Las marcas y la fecha que nombran las medidas
(calidad_atipico, calidad_valor_mayor_100mil_millones, calidad_valor_cero_o_simbolico y la fecha
aaaa-mm-dd) se reconstruyen aquí desde el crudo, con la definición declarada para la capa limpia:
  - texto: se borran los caracteres invisibles, forma NFC, espacios internos reducidos a uno y recorte;
  - nulos disfrazados («No Definido», «N/A», «-», etc.; en nit_entidad también «0») pasan a vacío;
  - valor_del_contrato: número con punto decimal; vacío o no numérico = 0, como dicen las medidas;
  - fecha_de_firma: se lee con los formatos declarados, en orden, y queda como aaaa-mm-dd;
  - atípico: rango intercuartílico sobre log10 de los valores positivos con k = 3; los cuartiles son
    las posiciones n // 4 y 3n // 4 de la lista ordenada; se marca el positivo que cae fuera.
FAILFAST: csv con strict=True y control del número de campos en cada fila. Si falta una columna, el
encabezado repite una, una fila trae más o menos campos o hay una comilla mal cerrada, la lectura se
detiene con el número de línea; nunca se lee en silencio.
"""
import csv
import math
import re
import unicodedata
from datetime import datetime

from reglas_base import hipotesis

COLUMNAS = ("nit_entidad", "codigo_entidad", "fecha_de_firma", "valor_del_contrato")

# Invisibles que borra la capa limpia: controles C0 y C1 (menos tabulador, salto y retorno), ancho cero,
# marcas de dirección, separadores de línea y de párrafo, unión de palabras y BOM. Escritos como escapes.
INVISIBLES = r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f\u200b-\u200f\u2028\u2029\u202a-\u202e\u2060\ufeff]"
NULOS = ("No Definido", "No Aplica", "N/A", "NA", "Null", "None", "Sin dato", "-", "--")
FORMATOS_FECHA = ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y")

K_ATIPICO = 3.0
MINIMO_POSITIVOS = 20               # con menos valores positivos la capa limpia no marca atípicos
SEPARA_ARRIBA = 1_000_000           # H1: entre los dos límites; deja solo los atípicos por arriba
TOPE_GRANDES = 100_000_000_000      # H2: contratos de más de 100.000 millones
NIT_DISTRITO = "890905211"          # H2: Distrito de Medellín
SIMBOLICO = 10                      # H5: valor cero o simbólico
MINIMO_FILAS_NIT = 100              # H5: entidades con 100 contratos o más


def _llave_nulo(s):
    """Cómo compara la capa limpia los nulos disfrazados: sin tildes ni mayúsculas, solo letras y dígitos."""
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^0-9a-z]", "", s.casefold())


DISFRACES = frozenset(_llave_nulo(x) for x in NULOS)
DISFRACES_NIT = DISFRACES | {_llave_nulo("0")}


def _texto(v):
    """Normalización de texto de la capa limpia: invisibles, NFC, espacios internos y recorte."""
    v = re.sub(INVISIBLES, "", v)
    v = unicodedata.normalize("NFC", v)
    v = re.sub(r"\s+", " ", v)
    return v.strip()


def _sin_disfraz(v, disfraces):
    return "" if v and _llave_nulo(v) in disfraces else v


def _numero(v):
    """(valor, se_pudo_leer). Vacío o no numérico = 0, como dicen las medidas."""
    if not v:
        return 0.0, False
    try:
        x = float(v)
    except ValueError:
        return 0.0, False
    if not math.isfinite(x):
        return 0.0, False
    return x, True


def _fecha(v):
    """aaaa-mm-dd con los formatos declarados, en orden; None si viene vacía o no se puede leer."""
    if not v:
        return None
    for formato in FORMATOS_FECHA:
        try:
            return datetime.strptime(v, formato).strftime("%Y-%m-%d")
        except ValueError:
            continue
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", v):
        try:
            return datetime.fromisoformat(v[:19]).strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None


def _leer(datos):
    """Filas normalizadas del CSV crudo de contratos. Solo abre datos["contratos"]."""
    ruta = datos["contratos"]
    filas = []
    with open(ruta, "r", newline="", encoding="utf-8-sig") as fh:
        lector = csv.reader(fh, strict=True)
        encabezado = next(lector, None)
        if not encabezado:
            raise ValueError("el CSV de contratos viene vacío: no tiene encabezado")
        repetidas = sorted({c for c in encabezado if encabezado.count(c) > 1})
        if repetidas:
            raise ValueError(f"el encabezado del CSV repite columnas: {repetidas}")
        faltan = [c for c in COLUMNAS if c not in encabezado]
        if faltan:
            raise ValueError(f"al CSV de contratos le faltan columnas: {faltan}")
        pos = {c: encabezado.index(c) for c in COLUMNAS}
        for campos in lector:
            if len(campos) != len(encabezado):
                raise ValueError(f"la línea {lector.line_num} del CSV trae {len(campos)} campos "
                                 f"y el encabezado {len(encabezado)}")
            valor, es_numero = _numero(_sin_disfraz(_texto(campos[pos["valor_del_contrato"]]), DISFRACES))
            filas.append({
                "nit": _sin_disfraz(_texto(campos[pos["nit_entidad"]]), DISFRACES_NIT),
                "codigo": _texto(campos[pos["codigo_entidad"]]),
                "fecha": _fecha(_sin_disfraz(_texto(campos[pos["fecha_de_firma"]]), DISFRACES)),
                "valor": valor,
                "es_numero": es_numero,
            })
    if not filas:
        raise ValueError("el CSV de contratos no trae filas")
    return filas


def _limites_atipico(filas):
    """(bajo, alto, n) en log10 sobre los n valores positivos; (None, None, n) si son menos de 20."""
    logs = sorted(math.log10(f["valor"]) for f in filas if f["es_numero"] and f["valor"] > 0)
    n = len(logs)
    if n < MINIMO_POSITIVOS:
        return None, None, n
    q1, q3 = logs[n // 4], logs[(3 * n) // 4]
    return q1 - K_ATIPICO * (q3 - q1), q3 + K_ATIPICO * (q3 - q1), n


def _es_atipico(f, bajo, alto):
    if bajo is None or not f["es_numero"] or f["valor"] <= 0:
        return False
    return not (bajo <= math.log10(f["valor"]) <= alto)


def _total(filas):
    total = math.fsum(f["valor"] for f in filas)
    if total <= 0:
        raise ValueError("la suma de valor_del_contrato no es positiva: la proporción no está definida")
    return total


def _sumas_por_nit(filas):
    valores = {}
    for f in filas:
        if f["nit"]:
            valores.setdefault(f["nit"], []).append(f["valor"])
    return {nit: math.fsum(vs) for nit, vs in valores.items()}


def _razon_distrito(sumas):
    """Suma del NIT del Distrito dividida por la mayor suma entre los otros NIT."""
    if NIT_DISTRITO not in sumas:
        raise ValueError(f"el NIT {NIT_DISTRITO} no aparece en los contratos")
    otras = [(s, nit) for nit, s in sumas.items() if nit != NIT_DISTRITO]
    if not otras:
        raise ValueError("no hay otro NIT con el que comparar")
    s_mayor, nit_mayor = max(otras)
    if s_mayor <= 0:
        raise ValueError("ningún otro NIT suma más de 0: la razón no está definida")
    return sumas[NIT_DISTRITO] / s_mayor, sumas[NIT_DISTRITO], nit_mayor, s_mayor


def _miles(x):
    """Entero con punto de miles."""
    return f"{x:,.0f}".replace(",", ".")


def _dec(x, cifras=4):
    """Decimal con coma."""
    return f"{x:.{cifras}f}".replace(".", ",")


@hipotesis("H1")
def h1(datos):
    filas = _leer(datos)
    n = len(filas)
    total = _total(filas)
    bajo, alto, n_pos = _limites_atipico(filas)
    atipicos = [f for f in filas if _es_atipico(f, bajo, alto)]
    arriba = [f["valor"] for f in atipicos if f["valor"] > SEPARA_ARRIBA]
    suma_arriba = math.fsum(arriba)
    valor = suma_arriba / total
    base = len(arriba) / n
    no_numericos = sum(1 for f in filas if not f["es_numero"])
    if bajo is None:
        limites = f"Con {n_pos} valores positivos (menos de {MINIMO_POSITIVOS}) no se marca ningún atípico"
    else:
        limites = (f"Límites de atípico (rango intercuartílico sobre log10 de los {_miles(n_pos)} valores positivos, "
                   f"k = 3): {_miles(10 ** bajo)} a {_miles(10 ** alto)} pesos")
    detalle = (f"{limites}. Atípicos: {_miles(len(atipicos))} filas; por arriba (atípico y valor > 1.000.000): "
               f"{_miles(len(arriba))} filas que suman {_miles(suma_arriba)} pesos, de {_miles(total)} pesos en las "
               f"{_miles(n)} filas → {_dec(valor)} ({_dec(100 * valor, 2)} %). "
               f"Línea base, reparto por número de contratos: {_miles(len(arriba))} de {_miles(n)} filas = {_dec(base)}. "
               f"Valores vacíos o no numéricos (cuentan 0): {no_numericos}.")
    return {"valor": valor, "linea_base": base, "detalle": detalle}


@hipotesis("H2")
def h2(datos):
    filas = _leer(datos)
    grandes = [f for f in filas if f["valor"] > TOPE_GRANDES]
    resto = [f for f in filas if not f["valor"] > TOPE_GRANDES]
    valor, s_dist, nit_otro, s_otro = _razon_distrito(_sumas_por_nit(resto))
    base, s_dist_todas, nit_otro_todas, s_otro_todas = _razon_distrito(_sumas_por_nit(filas))
    sin_nit = sum(1 for f in filas if not f["nit"])
    detalle = (f"Sin las {len(grandes)} filas de más de 100.000.000.000 pesos (suman "
               f"{_miles(math.fsum(f['valor'] for f in grandes))}), el NIT {NIT_DISTRITO} suma {_miles(s_dist)} pesos "
               f"y la mayor suma entre los otros NIT es la del NIT {nit_otro}, {_miles(s_otro)} pesos → razón {_dec(valor)}. "
               f"Línea base, con las {_miles(len(filas))} filas: {_miles(s_dist_todas)} contra {_miles(s_otro_todas)} "
               f"(NIT {nit_otro_todas}) → {_dec(base)}. Filas sin NIT: {sin_nit}.")
    return {"valor": valor, "linea_base": base, "detalle": detalle}


@hipotesis("H3")
def h3(datos):
    filas = _leer(datos)
    total = _total(filas)
    unidades = {}
    for f in filas:
        if f["nit"]:
            unidades.setdefault(f["nit"], {}).setdefault(f["codigo"], []).append(f["valor"])
    fuera, uniforme, nits, n_unidades = [], [], 0, 0
    for por_codigo in unidades.values():
        k = len(por_codigo)
        if k < 2:
            continue
        nits += 1
        n_unidades += k
        principal = max((math.fsum(vs), codigo) for codigo, vs in por_codigo.items())[1]
        fuera.extend(v for codigo, vs in por_codigo.items() if codigo != principal for v in vs)
        uniforme.append(math.fsum(v for vs in por_codigo.values() for v in vs) * (k - 1) / k)
    suma_fuera = math.fsum(fuera)
    suma_uniforme = math.fsum(uniforme)
    valor = suma_fuera / total
    base = suma_uniforme / total
    codigos_vacios = sum(1 for f in filas if not f["codigo"])
    detalle = (f"{nits} de {len(unidades)} NIT tienen 2 o más codigo_entidad ({n_unidades} unidades entre todos). "
               f"Valor fuera de la unidad principal (la de mayor suma en cada NIT): {_miles(suma_fuera)} pesos, "
               f"de {_miles(total)} pesos en las {_miles(len(filas))} filas → {_dec(valor)} ({_dec(100 * valor, 2)} %). "
               f"Línea base, reparto uniforme entre las unidades, valor × (k − 1) ÷ k: {_miles(suma_uniforme)} pesos "
               f"→ {_dec(base)}. codigo_entidad vacíos: {codigos_vacios}.")
    return {"valor": valor, "linea_base": base, "detalle": detalle}


@hipotesis("H4")
def h4(datos):
    filas = _leer(datos)
    n = len(filas)
    enero = sum(1 for f in filas if f["fecha"] is not None and "2025-01-01" <= f["fecha"] <= "2025-01-31")
    sin_fecha = sum(1 for f in filas if f["fecha"] is None)
    valor = enero / n
    base = 31 / 365
    detalle = (f"Filas con fecha_de_firma del 2025-01-01 al 2025-01-31, los dos días incluidos: {_miles(enero)} de "
               f"{_miles(n)} → {_dec(valor)} ({_dec(100 * valor, 2)} %). Fechas vacías o que no se pudieron leer: "
               f"{sin_fecha}. Línea base, reparto uniforme por días: 31 de 365 = {_dec(base)}.")
    return {"valor": valor, "linea_base": base, "detalle": detalle}


@hipotesis("H5")
def h5(datos):
    filas = _leer(datos)
    n = len(filas)
    conteo = {}
    for f in filas:
        if f["nit"]:
            c = conteo.setdefault(f["nit"], [0, 0])
            c[0] += 1
            c[1] += f["valor"] < SIMBOLICO
    elegibles = [(simb / filas_nit, nit, simb, filas_nit)
                 for nit, (filas_nit, simb) in conteo.items() if filas_nit >= MINIMO_FILAS_NIT]
    if not elegibles:
        raise ValueError(f"ningún NIT tiene {MINIMO_FILAS_NIT} filas o más")
    prop, nit_max, simb_max, filas_max = max(elegibles)
    simbolicas = sum(1 for f in filas if f["valor"] < SIMBOLICO)
    base = simbolicas / n
    no_numericos = sum(1 for f in filas if not f["es_numero"])
    detalle = (f"{len(elegibles)} de {len(conteo)} NIT tienen 100 filas o más. La mayor proporción de filas con "
               f"valor < 10 es la del NIT {nit_max}: {_miles(simb_max)} de {_miles(filas_max)} → {_dec(prop)} "
               f"({_dec(100 * prop, 2)} %). Línea base, todo el archivo: {_miles(simbolicas)} de {_miles(n)} filas "
               f"= {_dec(base)}. Valores vacíos o no numéricos (cuentan como 0): {no_numericos}.")
    return {"valor": prop, "linea_base": base, "detalle": detalle}

"""Generador B · etapa 2 (Procesamiento) · SECOP II, Medellín, 2025.

Petición: valor contratado en 2025 por cada entidad pública con sede en Medellín, según
SECOP II. Para cada entidad: nit_entidad, entidad (nombre), valor_contratado y
numero_contratos.

Enfoque B (distinto al de A): solo biblioteca estándar, sin pandas. El CSV se lee todo
como texto con el módulo csv y los valores se suman con Decimal (exacto); cada total se
pasa a float una sola vez, al final.

Capa limpia (spec.datos y spec.capa_limpia):
  * Cada fila va a un solo motivo de exclusión, el primero que aplique en este orden:
    sin_id_contrato, repetido, sin_fecha_de_firma, fuera_de_2025, sin_nit_entidad.
  * Las marcas calidad_* que excluyen van a su motivo; todas las demás solo avisan.
    calidad_ok no decide nada (calidad_ok = 1 no quiere decir que la fila cuente).
  * Un id_contrato, una fecha_de_firma o un nit_entidad vacío (tras recortar) no lleva
    marca: se reconoce por la celda vacía y excluye con su motivo.
  * Además de leer las marcas, el código repite las comprobaciones baratas (llave
    repetida, fecha real de 2025, número). En una capa limpia correcta dan lo mismo; si
    llega un archivo con alguna marca de menos, la fila no se cuela.
  * Si el archivo no trae ninguna columna calidad_* (dato crudo), antes de decidir se
    aplica la misma normalización de la capa limpia: U+0096 -> «–» en el nombre, sin
    invisibles ni controles, NFC, espacios internos reducidos, recorte y nulos
    disfrazados como vacíos.

analizar(datos)  -> list[dict]: una fila por nit_entidad con al menos un contrato que cuenta.
conciliar(datos) -> dict: filas_leidas = usadas + suma de excluidas; «marcadas» cuenta las
filas usadas que traen algo que avisar (limpiar es marcar: nada se descarta en silencio).

Funciones puras: solo leen el CSV que reciben; no escriben archivos, no usan la red y no
guardan estado entre llamadas (dos corridas dan lo mismo).
"""

import csv
import math
import re
import unicodedata
from collections import Counter
from datetime import date, datetime
from decimal import Context, Decimal, InvalidOperation

# ---------------------------------------------------------------------------
# Reglas de spec.json y del plan de limpieza (son reglas, no valores del archivo)
# ---------------------------------------------------------------------------

TABLA = "contratos"

COLUMNAS = (
    "id_contrato",
    "nit_entidad",
    "nombre_entidad",
    "fecha_de_firma",
    "valor_del_contrato",
)

# Orden de conciliar: cada fila va al primer motivo que aplique.
MOTIVOS_EXCLUSION = (
    "sin_id_contrato",
    "repetido",
    "sin_fecha_de_firma",
    "fuera_de_2025",
    "sin_nit_entidad",
)

# spec.capa_limpia: marcas que excluyen y su motivo. Cualquier otra marca solo avisa.
MARCAS_QUE_EXCLUYEN = {
    "nulo_disfrazado_id_contrato": "sin_id_contrato",
    "repetido": "repetido",
    "nulo_disfrazado_fecha_de_firma": "sin_fecha_de_firma",
    "fecha_invalida": "sin_fecha_de_firma",
    "fuera_de_2025": "fuera_de_2025",
    "nulo_disfrazado_nit_entidad": "sin_nit_entidad",
}

PREFIJO_MARCA = "calidad_"
COLUMNA_SIN_MARCAS = "calidad_ok"
VALORES_MARCA_ACTIVA = frozenset({"1", "1.0", "true", "True"})

# «Contratado en 2025»: la parte de fecha, los dos días completos, sin importar la hora.
INICIO_2025 = date(2025, 1, 1)
FIN_2025 = date(2025, 12, 31)

# spec.capa_limpia.fecha_invalida: formatos probados uno por uno (dd/mm/aaaa es día primero).
FORMATOS_FECHA = (
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%d/%m/%Y",
)
# Si nada de eso sirve: aaaa-mm-ddThh:mm... con zona u otros decimales, por sus 19 primeros
# caracteres.
PATRON_FECHA_LARGA = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}"
FORMATO_FECHA_LARGA = "%Y-%m-%dT%H:%M:%S"

# Plan de limpieza: nulos disfrazados (solo se usan si el archivo llega sin capa limpia).
NULOS_DISFRAZADOS = frozenset(
    {"No Definido", "No Aplica", "N/A", "NA", "Null", "None", "Sin dato", "-", "--"}
)
COLUMNAS_DONDE_CERO_ES_NULO = frozenset({"id_contrato", "nit_entidad"})

# Nombre: la raya de Windows-1252 mal codificada (U+0096) se cambia por «–» (U+2013).
RAYA_MAL_CODIFICADA = "\u0096"
RAYA = "–"
SIN_NOMBRE = "SIN NOMBRE"  # S9

# Avisos de valor y de NIT (spec.capa_limpia); nunca excluyen.
VALOR_SIMBOLICO = Decimal(10)
VALOR_MAYOR_100MIL_MILLONES = Decimal(100_000_000_000)
NIT_MINIMO = 100_000_000
NIT_MAXIMO = 9_999_999_999

PRECISION_SUMA = 60  # dígitos significativos: la suma con Decimal no redondea en la práctica


# ---------------------------------------------------------------------------
# Interfaz
# ---------------------------------------------------------------------------


def analizar(datos):
    """Una fila por nit_entidad con al menos un contrato que cuenta.

    Claves: nit_entidad (str), entidad (str), valor_contratado (float),
    numero_contratos (int). Orden: valor_contratado de mayor a menor; en empate,
    nit_entidad ascendente como texto.
    """
    resultado, _ = _procesar(datos)
    return resultado


def conciliar(datos):
    """{"filas_leidas", "usadas", "excluidas": {motivo: n}, "marcadas": {motivo: n}}.

    filas_leidas = usadas + suma de excluidas: cada fila leída va a un solo lugar.
    «marcadas» cuenta filas usadas con algo que avisar (una fila puede tener varios avisos).
    """
    _, conciliacion = _procesar(datos)
    return conciliacion


# ---------------------------------------------------------------------------
# Proceso (una sola pasada por el archivo)
# ---------------------------------------------------------------------------


def _procesar(datos):
    ruta = _ruta_de(datos)
    contexto = Context(prec=PRECISION_SUMA)

    leidas = 0
    usadas = 0
    excluidas = dict.fromkeys(MOTIVOS_EXCLUSION, 0)
    marcadas = Counter()
    vistos = set()  # llaves id_contrato ya vistas, sobre todas las filas
    fechas_leidas = {}  # caché de esta llamada: texto -> fecha o None
    grupos = {}  # nit_entidad -> [total Decimal, contratos, Counter de nombres]

    with open(ruta, "r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.reader(archivo)
        encabezado = next(lector, None)
        if encabezado is None:  # archivo vacío: nada leído
            return [], _armar_conciliacion(leidas, usadas, excluidas, marcadas)

        columnas = [c.strip() for c in encabezado]
        posicion = {}
        for i, columna in enumerate(columnas):
            posicion.setdefault(columna, i)
        faltan = [c for c in COLUMNAS if c not in posicion]
        if faltan:
            raise ValueError(
                "La tabla «%s» no trae las columnas: %s" % (TABLA, ", ".join(faltan))
            )
        columnas_marca = [
            (columna[len(PREFIJO_MARCA):], i)
            for columna, i in posicion.items()
            if columna.startswith(PREFIJO_MARCA) and columna != COLUMNA_SIN_MARCAS
        ]
        es_capa_limpia = any(c.startswith(PREFIJO_MARCA) for c in columnas)

        for fila in lector:
            if not fila:  # línea en blanco: no es una fila
                continue
            leidas += 1

            marcas = {
                marca
                for marca, i in columnas_marca
                if i < len(fila) and fila[i].strip() in VALORES_MARCA_ACTIVA
            }
            crudo = {c: (fila[posicion[c]] if posicion[c] < len(fila) else "") for c in COLUMNAS}
            valores = {}
            for columna in COLUMNAS:
                texto = crudo[columna]
                if es_capa_limpia or columna == "id_contrato":
                    texto = texto.strip()
                else:
                    texto = _normalizar_texto(texto, columna)
                if not es_capa_limpia and _es_nulo_disfrazado(texto, columna):
                    marcas.add("nulo_disfrazado_" + columna)
                if "nulo_disfrazado_" + columna in marcas:
                    texto = ""  # un nulo disfrazado cuenta como vacío
                valores[columna] = texto

            # --- Motivos de exclusión: marcas de la capa limpia + comprobaciones propias
            motivos = {MARCAS_QUE_EXCLUYEN[m] for m in marcas if m in MARCAS_QUE_EXCLUYEN}

            id_contrato = valores["id_contrato"]
            if id_contrato == "" or "sin_id_contrato" in motivos:
                motivos.add("sin_id_contrato")
            else:
                # Llave recortada y sin distinguir mayúsculas; vale la primera aparición,
                # mirada sobre todas las filas y antes de mirar la fecha (S3).
                llave = id_contrato.lower()
                if llave in vistos:
                    motivos.add("repetido")
                vistos.add(llave)

            texto_fecha = valores["fecha_de_firma"]
            if texto_fecha == "":
                motivos.add("sin_fecha_de_firma")
            else:
                if texto_fecha not in fechas_leidas:
                    fechas_leidas[texto_fecha] = _leer_fecha(texto_fecha)
                fecha = fechas_leidas[texto_fecha]
                if fecha is None:
                    motivos.add("sin_fecha_de_firma")  # S5: no es una fecha real
                elif not (INICIO_2025 <= fecha <= FIN_2025):
                    motivos.add("fuera_de_2025")

            nit = valores["nit_entidad"]
            if nit == "":
                motivos.add("sin_nit_entidad")  # S6

            motivo = next((m for m in MOTIVOS_EXCLUSION if m in motivos), None)
            if motivo is not None:
                excluidas[motivo] += 1
                continue

            # --- La fila cuenta: se suma y se anotan sus avisos
            usadas += 1
            avisos = {m for m in marcas if m not in MARCAS_QUE_EXCLUYEN}

            texto_valor = valores["valor_del_contrato"]
            valor = None
            if not ({"numero_invalido", "nulo_disfrazado_valor_del_contrato"} & marcas):
                valor = _leer_valor(texto_valor)
                if valor is None:
                    avisos.add("valor_vacio" if texto_valor == "" else "numero_invalido")
            if valor is not None:
                if valor < 0:
                    avisos.add("valor_negativo")  # no se corrige
                if valor < VALOR_SIMBOLICO:
                    avisos.add("valor_cero_o_simbolico")
                if valor > VALOR_MAYOR_100MIL_MILLONES:
                    avisos.add("valor_mayor_100mil_millones")

            if re.fullmatch(r"[0-9]+", nit) is None:
                avisos.add("nit_no_numerico")  # el NIT se usa tal como viene
            elif not _nit_en_rango(nit):
                avisos.add("nit_longitud_atipica")

            nombre = valores["nombre_entidad"]
            if nombre == "" and "nulo_disfrazado_nombre_entidad" not in marcas:
                avisos.add("nombre_entidad_vacio")  # S9: no participa en la elección
            if crudo["id_contrato"] != id_contrato:
                avisos.add("id_contrato_recortado")
            if crudo["nit_entidad"] != nit or (
                crudo["nombre_entidad"] != nombre
                and "nulo_disfrazado_nombre_entidad" not in marcas
            ):
                avisos.add("texto_normalizado")
            if len(fila) != len(columnas):
                avisos.add("fila_mal_formada")
            marcadas.update(avisos)

            grupo = grupos.get(nit)
            if grupo is None:
                grupo = grupos[nit] = [Decimal(0), 0, Counter()]
            if valor is not None:  # S4: vacío o no numérico suma 0, pero cuenta
                grupo[0] = contexto.add(grupo[0], valor)
            grupo[1] += 1
            if nombre != "":
                grupo[2][nombre] += 1

    resultado = [
        {
            "nit_entidad": nit,
            "entidad": _elegir_nombre(nombres),
            "valor_contratado": float(total),
            "numero_contratos": int(contratos),
        }
        for nit, (total, contratos, nombres) in grupos.items()
    ]
    resultado.sort(key=lambda f: (-f["valor_contratado"], f["nit_entidad"]))
    return resultado, _armar_conciliacion(leidas, usadas, excluidas, marcadas)


# ---------------------------------------------------------------------------
# Ayudas
# ---------------------------------------------------------------------------


def _ruta_de(datos):
    if isinstance(datos, dict):
        if TABLA not in datos:
            raise KeyError("datos debe traer la tabla «%s» (ruta del CSV)" % TABLA)
        return str(datos[TABLA])
    return str(datos)


def _armar_conciliacion(leidas, usadas, excluidas, marcadas):
    return {
        "filas_leidas": leidas,
        "usadas": usadas,
        "excluidas": dict(excluidas),
        "marcadas": {m: marcadas[m] for m in sorted(marcadas)},
    }


def _normalizar_texto(texto, columna):
    """Normalización de capa_limpia para un archivo crudo (op reemplazar + op texto)."""
    if columna == "nombre_entidad":
        texto = texto.replace(RAYA_MAL_CODIFICADA, RAYA)
    texto = "".join(
        c for c in texto if c.isspace() or unicodedata.category(c) not in ("Cc", "Cf")
    )
    texto = unicodedata.normalize("NFC", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _es_nulo_disfrazado(texto, columna):
    if texto in NULOS_DISFRAZADOS:
        return True
    return texto == "0" and columna in COLUMNAS_DONDE_CERO_ES_NULO


def _leer_fecha(texto):
    """Fecha real (date) o None. Cada formato por separado; nunca se adivina el orden."""
    for formato in FORMATOS_FECHA:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    if re.match(PATRON_FECHA_LARGA, texto):
        try:
            return datetime.strptime(texto[:19], FORMATO_FECHA_LARGA).date()
        except ValueError:
            return None
    return None


def _leer_valor(texto):
    """Decimal exacto, o None si está vacío o no es un número finito."""
    if texto == "":
        return None
    try:
        valor = Decimal(texto)
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not valor.is_finite() or not math.isfinite(float(valor)):
        return None
    return valor


def _nit_en_rango(nit):
    """9 o 10 dígitos: entre 100.000.000 y 9.999.999.999 (nit ya es solo dígitos)."""
    digitos = nit.lstrip("0") or "0"
    if len(digitos) > len(str(NIT_MAXIMO)):
        return False
    return NIT_MINIMO <= int(digitos) <= NIT_MAXIMO


def _elegir_nombre(nombres):
    """El nombre con más contratos que cuentan; en empate, el menor como texto (S2, S9)."""
    if not nombres:
        return SIN_NOMBRE
    mayor = max(nombres.values())
    return min(nombre for nombre, veces in nombres.items() if veces == mayor)

"""Generador A · etapa 2 (Procesamiento) · SECOP II, entidades con sede en Medellín, 2025.

Petición: valor contratado en 2025 por cada entidad pública con sede en Medellín, según
SECOP II; por entidad: nit_entidad, entidad (nombre), valor_contratado y numero_contratos.

- analizar(datos) -> list[dict]: una fila por nit_entidad con al menos un contrato que
  cuenta, con exactamente las claves nit_entidad (str), entidad (str), valor_contratado
  (float, sin redondear) y numero_contratos (int); ordenada por valor_contratado de mayor
  a menor y, en empate exacto, por nit_entidad ascendente como texto.
- conciliar(datos) -> dict: {"filas_leidas", "usadas", "excluidas", "marcadas"}. Cada fila
  leída queda usada o excluida por un solo motivo, el primero que aplique en el orden de
  MOTIVOS (filas_leidas = usadas + suma de excluidas). «marcadas» cuenta las filas usadas
  que traen algo que avisar: limpiar es marcar, nada se borra en silencio.

datos = {"contratos": ruta_csv} con la capa limpia (spec.datos). Se usan sus marcas
calidad_* como dice spec.capa_limpia: las de exclusión sacan la fila con su motivo y las
de aviso solo se cuentan. Además se vuelve a comprobar, con la definición de la spec, lo
que decide si un contrato cuenta (celda vacía tras recortar, nulo disfrazado, fecha real
dentro del año, id repetido): en la capa limpia da lo mismo que las marcas, y si falta
una marca la fila no se cuela.

Solo biblioteca estándar y pandas. Función pura: lee el CSV y no escribe nada.
"""

import math
import re
import unicodedata
from collections.abc import Mapping
from datetime import date, datetime

import pandas as pd

# ---------------------------------------------------------------------------
# Parámetros de la spec (salen de la petición y de spec.json; no son datos)
# ---------------------------------------------------------------------------

TABLA = "contratos"

# «Contratado en 2025»: del 1 de enero al 31 de diciembre, los dos días completos,
# sin importar la hora (solo cuenta la parte de fecha).
ANIO = 2025
INICIO = date(ANIO, 1, 1)
FIN = date(ANIO, 12, 31)

SIN_NOMBRE = "SIN NOMBRE"  # S9: ningún contrato que cuenta del NIT trae nombre

COLUMNAS = ("id_contrato", "nit_entidad", "nombre_entidad", "fecha_de_firma", "valor_del_contrato")

# Motivos de exclusión, en el orden de conciliar: manda el primero que aplique.
MOTIVOS = ("sin_id_contrato", "repetido", "sin_fecha_de_firma", "fuera_de_2025", "sin_nit_entidad")

# Marcas de la capa limpia que excluyen y el motivo al que llevan (spec.capa_limpia).
MARCAS_QUE_EXCLUYEN = {
    "nulo_disfrazado_id_contrato": "sin_id_contrato",
    "repetido": "repetido",
    "nulo_disfrazado_fecha_de_firma": "sin_fecha_de_firma",
    "fecha_invalida": "sin_fecha_de_firma",
    "fuera_de_2025": "fuera_de_2025",
    "nulo_disfrazado_nit_entidad": "sin_nit_entidad",
}

# Marcas que solo avisan (spec.capa_limpia). Cualquier otra calidad_* que aparezca,
# salvo calidad_ok, también se trata como aviso: las marcas de aviso nunca excluyen.
MARCAS_DE_AVISO = (
    "nit_no_numerico",
    "nit_longitud_atipica",
    "nulo_disfrazado_nombre_entidad",
    "nulo_disfrazado_valor_del_contrato",
    "numero_invalido",
    "valor_negativo",
    "valor_cero_o_simbolico",
    "valor_mayor_100mil_millones",
    "atipico",
)

# Avisos propios, para lo que afecta la cuenta y no trae marca:
#   valor_negativo     además de la marca, todo valor leído < 0: se suma sin corregir (R7)
#   valor_vacio        valor vacío o nulo disfrazado sin marca: cuenta y suma 0 (S4)
#   valor_no_numerico  valor que no es número y sin marca numero_invalido: suma 0 (S4)
#   nombre_vacio       nombre vacío sin marca: no participa en la elección del nombre (S9)
#   nit_no_digitos     NIT que no es solo dígitos y sin marca nit_no_numerico (R5)

# Nulos disfrazados del plan de limpieza; se comparan exactos tras normalizar, así que en
# la capa limpia (donde ya quedaron vacíos) no cambian nada.
_NULOS = ("No Definido", "No Aplica", "N/A", "NA", "Null", "None", "Sin dato", "-", "--")
NULOS_DISFRAZADOS = {
    "id_contrato": sorted(_NULOS + ("0",)),
    "nit_entidad": sorted(_NULOS + ("0",)),
    "nombre_entidad": sorted(_NULOS),
    "fecha_de_firma": sorted(_NULOS),
    "valor_del_contrato": sorted(_NULOS),
}

# Formatos aceptados para fecha_de_firma, probados uno por uno (L01: nunca format='mixed'
# ni dayfirst); dd/mm/aaaa es día primero. Si ninguno sirve, un aaaa-mm-ddThh:mm… con zona
# u otros decimales se lee por sus 19 primeros caracteres.
FORMATOS_FECHA = (
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%d/%m/%Y",
)
_ISO_CON_HORA = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}"
_FORMATO_19 = "%Y-%m-%dT%H:%M:%S"

# Número con punto decimal (decimal "." en el plan); sin separador de miles.
_NUMERO = r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"

_RAYA_MAL_CODIFICADA = "\u0096"  # control C1: la raya de Windows-1252 mal codificada
_RAYA = "–"                 # «–»

_MARCA_SI = ("true", "verdadero", "si", "sí")

_USADA = ""  # motivo de una fila que se usa


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------

def _leer(datos):
    """Tabla de contratos, todo como texto y sin convertir vacíos en NaN."""
    fuente = datos
    if isinstance(datos, Mapping):
        if TABLA in datos:
            fuente = datos[TABLA]
        elif len(datos) == 1:
            fuente = next(iter(datos.values()))
        else:
            raise KeyError("datos no trae la tabla «" + TABLA + "»")
    if isinstance(fuente, pd.DataFrame):
        tabla = fuente.astype(object).where(fuente.notna(), "").astype(str)
    else:
        tabla = pd.read_csv(
            fuente,
            dtype=str,
            keep_default_na=False,
            na_filter=False,
            encoding="utf-8-sig",
        )
    tabla.columns = [str(columna).strip() for columna in tabla.columns]
    faltan = [columna for columna in COLUMNAS if columna not in tabla.columns]
    if faltan:
        raise ValueError("a la tabla «" + TABLA + "» le faltan columnas: " + ", ".join(faltan))
    return tabla.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Normalización y lectura de valores (la de spec.capa_limpia, idempotente)
# ---------------------------------------------------------------------------

def _quitar_invisibles(texto):
    """Quita controles e invisibles (categorías Cc y Cf); los espacios se tratan aparte."""
    return "".join(c for c in texto if c.isspace() or unicodedata.category(c) not in ("Cc", "Cf"))


def _normalizar(texto):
    """Sin invisibles ni controles, NFC, espacios internos reducidos a uno y recortado."""
    texto = unicodedata.normalize("NFC", _quitar_invisibles(texto))
    return " ".join(texto.split())


def _normalizar_nombre(texto):
    """Como _normalizar, pero antes U+0096 → «–» (si no, el control se borraría)."""
    return _normalizar(texto.replace(_RAYA_MAL_CODIFICADA, _RAYA))


def _recortar(texto):
    return texto.strip()


def _minusculas(texto):
    return texto.lower()


def _probar_formato(texto, formato):
    try:
        return datetime.strptime(texto, formato).date()
    except ValueError:
        return None


def _fecha(texto):
    """Fecha real del calendario (solo la parte de fecha) o None."""
    for formato in FORMATOS_FECHA:
        leida = _probar_formato(texto, formato)
        if leida is not None:
            return leida
    if re.match(_ISO_CON_HORA, texto):
        return _probar_formato(texto[:19], _FORMATO_19)
    return None


def _numero(texto):
    """Número finito o None si el texto está vacío o no es un número."""
    if not re.fullmatch(_NUMERO, texto):
        return None
    numero = float(texto)
    return numero if math.isfinite(numero) else None


def _por_valor(serie, funcion):
    """Aplica funcion una sola vez por valor distinto y devuelve la lista fila a fila."""
    hechos = {valor: funcion(valor) for valor in dict.fromkeys(serie)}
    return [hechos[valor] for valor in serie]


def _marca(tabla, nombre):
    """calidad_<nombre> como booleano; si la columna no existe, vale 0 en todas las filas."""
    columna = "calidad_" + nombre
    if columna not in tabla.columns:
        return pd.Series(False, index=tabla.index, dtype=bool)
    texto = tabla[columna].astype(str).str.strip().str.lower()
    numero = pd.to_numeric(texto, errors="coerce").fillna(0)
    return ((numero != 0) | texto.isin(_MARCA_SI)).astype(bool)


def _otras_marcas(tabla):
    """Columnas calidad_* que no están en la spec (salvo calidad_ok): se cuentan como aviso."""
    conocidas = set(MARCAS_QUE_EXCLUYEN) | set(MARCAS_DE_AVISO) | {"ok"}
    otras = []
    for columna in tabla.columns:
        if columna.startswith("calidad_"):
            nombre = columna[len("calidad_"):]
            if nombre and nombre not in conocidas:
                otras.append(nombre)
    return sorted(otras)


# ---------------------------------------------------------------------------
# Clasificación fila a fila: cada fila usada o excluida por un solo motivo
# ---------------------------------------------------------------------------

def _clasificar(datos):
    tabla = _leer(datos)
    indice = tabla.index

    def texto(valores):
        return pd.Series(valores, index=indice, dtype=object)

    def booleano(valores):
        return pd.Series(valores, index=indice, dtype=bool)

    excluye = {nombre: _marca(tabla, nombre) for nombre in MARCAS_QUE_EXCLUYEN}

    # 1. sin_id_contrato: id_contrato no se reescribe en la capa limpia; se recorta al usarlo.
    ids = texto(_por_valor(tabla["id_contrato"], _recortar))
    sin_id = (
        (ids == "")
        | ids.isin(NULOS_DISFRAZADOS["id_contrato"])
        | excluye["nulo_disfrazado_id_contrato"]
    )

    # 2. repetido: id recortado y sin distinguir mayúsculas que ya apareció antes en el orden
    #    del archivo, sobre todas las filas y antes de mirar la fecha (vale la primera, S3).
    claves = texto(_por_valor(ids, _minusculas))
    repetido_propio = (
        claves[~sin_id].duplicated(keep="first").reindex(indice, fill_value=False).astype(bool)
    )
    repetido = ~sin_id & (excluye["repetido"] | repetido_propio)

    # 3. sin_fecha_de_firma (vacía, nulo disfrazado o no es fecha real) y 4. fuera_de_2025.
    fechas_texto = texto(_por_valor(tabla["fecha_de_firma"], _normalizar))
    fechas = _por_valor(fechas_texto, _fecha)
    leida = booleano([fecha is not None for fecha in fechas])
    en_el_anio = booleano([fecha is not None and INICIO <= fecha <= FIN for fecha in fechas])
    marca_fuera = excluye["fuera_de_2025"]
    sin_fecha = (
        (fechas_texto == "")
        | fechas_texto.isin(NULOS_DISFRAZADOS["fecha_de_firma"])
        | excluye["nulo_disfrazado_fecha_de_firma"]
        | excluye["fecha_invalida"]
        | (~leida & ~marca_fuera)
    )
    fuera = marca_fuera | (leida & ~en_el_anio)

    # 5. sin_nit_entidad: NIT como texto, recortado, sin convertir a número.
    nits = texto(_por_valor(tabla["nit_entidad"], _normalizar))
    sin_nit = (
        (nits == "")
        | nits.isin(NULOS_DISFRAZADOS["nit_entidad"])
        | excluye["nulo_disfrazado_nit_entidad"]
    )

    motivo = texto([_USADA] * len(indice))
    pendiente = booleano([True] * len(indice))
    for nombre, aplica in zip(MOTIVOS, (sin_id, repetido, sin_fecha, fuera, sin_nit)):
        nuevo = pendiente & aplica
        motivo = motivo.mask(nuevo, nombre)
        pendiente = pendiente & ~nuevo

    # Nombre: normalizado; vacío o nulo disfrazado no participa en la elección (S9).
    nombres = texto(_por_valor(tabla["nombre_entidad"], _normalizar_nombre))
    marca_nombre = _marca(tabla, "nulo_disfrazado_nombre_entidad")
    nombre_vacio = (nombres == "") | nombres.isin(NULOS_DISFRAZADOS["nombre_entidad"]) | marca_nombre
    nombres = nombres.mask(nombre_vacio, "")

    # Valor tal como viene, con decimales; vacío, nulo disfrazado o no numérico suma 0 (S4).
    valores_texto = texto(_por_valor(tabla["valor_del_contrato"], _normalizar))
    marca_nulo_valor = _marca(tabla, "nulo_disfrazado_valor_del_contrato")
    marca_invalido = _marca(tabla, "numero_invalido")
    valor_vacio = (
        (valores_texto == "")
        | valores_texto.isin(NULOS_DISFRAZADOS["valor_del_contrato"])
        | marca_nulo_valor
    )
    numeros = _por_valor(valores_texto, _numero)
    legible = booleano([numero is not None for numero in numeros])
    suma_cero = valor_vacio | marca_invalido | ~legible
    valores = pd.Series(
        [0.0 if cero else numero for numero, cero in zip(numeros, suma_cero)],
        index=indice,
        dtype=float,
    )

    # Avisos (no excluyen): marcas de la capa limpia y lo que la cuenta trató sin marca.
    # Si un aviso propio coincide con una marca del mismo nombre, se suman (nunca se pisa).
    avisos = {nombre: _marca(tabla, nombre) for nombre in MARCAS_DE_AVISO + tuple(_otras_marcas(tabla))}
    solo_digitos = booleano([nit.isascii() and nit.isdigit() for nit in nits])
    propios = {
        "valor_negativo": valores < 0,
        "valor_vacio": valor_vacio & ~marca_nulo_valor & ~marca_invalido,
        "valor_no_numerico": ~valor_vacio & ~legible & ~marca_invalido,
        "nombre_vacio": nombre_vacio & ~marca_nombre,
        "nit_no_digitos": ~solo_digitos & ~avisos["nit_no_numerico"],
    }
    for nombre, marca in propios.items():
        avisos[nombre] = (avisos[nombre] | marca) if nombre in avisos else marca

    filas = pd.DataFrame(
        {"motivo": motivo, "clave": claves, "nit": nits, "nombre": nombres, "valor": valores},
        index=indice,
    )
    return filas, avisos


# ---------------------------------------------------------------------------
# Funciones públicas
# ---------------------------------------------------------------------------

def analizar(datos):
    """Una fila por nit_entidad con al menos un contrato que cuenta (ver docstring del módulo)."""
    filas, _ = _clasificar(datos)
    usadas = filas[filas["motivo"] == _USADA]
    if usadas.empty:
        return []

    grupos = usadas.groupby("nit", sort=True)
    numero_contratos = grupos["clave"].nunique()      # id distintos (recortados, sin mayúsculas)
    valor_contratado = grupos["valor"].agg(math.fsum)  # suma exacta, sin redondear

    # Nombre más frecuente entre los contratos que cuentan del NIT; empate al menor texto.
    con_nombre = usadas.loc[usadas["nombre"] != "", ["nit", "nombre"]]
    elegido = {}
    for (nit, nombre), veces in con_nombre.value_counts(sort=False).items():
        previo = elegido.get(nit)
        if previo is None or veces > previo[0] or (veces == previo[0] and nombre < previo[1]):
            elegido[nit] = (int(veces), nombre)

    resultado = [
        {
            "nit_entidad": str(nit),
            "entidad": elegido[nit][1] if nit in elegido else SIN_NOMBRE,
            "valor_contratado": float(valor_contratado[nit]) + 0.0,  # + 0.0 evita un -0.0
            "numero_contratos": int(numero_contratos[nit]),
        }
        for nit in numero_contratos.index
    ]
    resultado.sort(key=lambda fila: (-fila["valor_contratado"], fila["nit_entidad"]))
    return resultado


def conciliar(datos):
    """filas_leidas = usadas + suma de excluidas; marcadas = avisos de las filas usadas."""
    filas, avisos = _clasificar(datos)
    usada = filas["motivo"] == _USADA
    excluidas = {motivo: int((filas["motivo"] == motivo).sum()) for motivo in MOTIVOS}
    marcadas = {}
    for nombre, marca in avisos.items():
        veces = int((marca & usada).sum())
        if veces:
            marcadas[nombre] = veces
    resumen = {
        "filas_leidas": int(len(filas)),
        "usadas": int(usada.sum()),
        "excluidas": excluidas,
        "marcadas": marcadas,
    }
    if resumen["filas_leidas"] != resumen["usadas"] + sum(excluidas.values()):
        raise RuntimeError("la conciliación no cuadra: hay filas sin motivo")
    return resumen

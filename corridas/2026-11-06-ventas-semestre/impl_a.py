"""Generador A: ventas netas sin IVA por región, primer semestre de 2026.

analizar(datos) recibe {"ventas": ruta_csv, "clientes": ruta_csv} y devuelve una
lista de seis diccionarios {"region": str, "ventas_netas": número}: las cinco
regiones oficiales de mayor a menor ventas_netas y «Sin región» de última.

Sigue spec.json de la corrida y el glosario del negocio:
- Cada documento cuenta una vez: se quitan los repetidos por numero_documento
  (sin espacios al inicio y al final, en mayúsculas) con la primera aparición,
  antes de filtrar y sumar.
- Fechas: aaaa-mm-dd se lee como ISO y toda fecha con barras como dd/mm/aaaa
  (también las ambiguas). La librería nunca adivina el formato. Semestre:
  2026-01-01 a 2026-06-30, ambos días incluidos.
- Ventas netas = suma del subtotal de las FV menos suma del subtotal de las NC.
  Cualquier otro tipo no cuenta. Las columnas iva y total nunca se usan.
- Región de un documento = la del registro de clientes con la
  fecha_actualizacion más reciente (en empate, el último del archivo: S3), con
  los códigos sin espacios al inicio y al final y en mayúsculas en las dos
  tablas. Sin cliente_id, o con un código que no está en el maestro, va a
  «Sin región». Si la región vigente de un cliente no encaja en las oficiales,
  el análisis se detiene con un error que nombra el cliente y la región (S2).
- La salida tiene siempre las seis filas, con 0 donde no haya ventas (S1).
"""

from __future__ import annotations

import datetime as _dt
import re
import unicodedata
import warnings

import numpy as np
import pandas as pd

INICIO = _dt.date(2026, 1, 1)
FIN = _dt.date(2026, 6, 30)

REGIONES_OFICIALES = (
    "Antioquia",
    "Bogotá D.C.",
    "Caldas",
    "Risaralda",
    "Valle del Cauca",
)
SIN_REGION = "Sin región"

# Escritura normalizada (sin espacios sobrantes, minúsculas, sin tildes, sin
# puntos) -> etiqueta oficial, tal como la fija tratamiento_de_datos.
MAPA_REGIONES = {
    "antioquia": "Antioquia",
    "bogota dc": "Bogotá D.C.",
    "bogota": "Bogotá D.C.",
    "caldas": "Caldas",
    "risaralda": "Risaralda",
    "valle del cauca": "Valle del Cauca",
    "valle": "Valle del Cauca",
}

SIGNO_POR_TIPO = {"FV": 1, "NC": -1}

_RE_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_RE_BARRAS = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")

_MAX_EJEMPLOS = 5


def _leer_csv(ruta: str) -> pd.DataFrame:
    """Lee todo como texto, sin convertir vacíos en NaN, para normalizar a mano."""
    df = pd.read_csv(
        ruta,
        dtype=str,
        keep_default_na=False,
        na_filter=False,
        encoding="utf-8-sig",
    )
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _texto(serie: pd.Series) -> pd.Series:
    return serie.astype(str).fillna("")


def _normalizar_codigo(serie: pd.Series) -> pd.Series:
    """Quita espacios al inicio y al final y pasa a mayúsculas."""
    return _texto(serie).str.strip().str.upper()


def _parsear_fecha(valor) -> _dt.date | None:
    """aaaa-mm-dd como ISO; dd/mm/aaaa (día primero) para toda fecha con barras.

    Devuelve None si el texto no tiene ninguna de las dos formas o no es una
    fecha del calendario.
    """
    texto = str(valor).strip()
    m = _RE_ISO.match(texto)
    if m:
        anio, mes, dia = (int(g) for g in m.groups())
    else:
        m = _RE_BARRAS.match(texto)
        if not m:
            return None
        dia, mes, anio = (int(g) for g in m.groups())
    try:
        return _dt.date(anio, mes, dia)
    except ValueError:
        return None


def _normalizar_region(valor) -> str:
    """Sin espacios sobrantes, minúsculas, sin tildes y sin puntos."""
    texto = " ".join(str(valor).split()).lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = texto.replace(".", "")
    return " ".join(texto.split())


def _ejemplos(valores) -> str:
    lista = [repr(v) for v in list(valores)[:_MAX_EJEMPLOS]]
    return ", ".join(lista)


def _maestro_clientes(ruta: str) -> dict[str, str]:
    """Código normalizado -> región oficial vigente (registro más reciente)."""
    cli = _leer_csv(ruta)
    cli = cli.assign(
        _codigo=_normalizar_codigo(cli["cliente_id"]),
        _orden=np.arange(len(cli)),
    )
    cli = cli[cli["_codigo"] != ""].copy()

    fechas = cli["fecha_actualizacion"].map(_parsear_fecha)
    sin_fecha = fechas.isna()
    if sin_fecha.any():
        warnings.warn(
            "clientes: fecha_actualizacion ilegible en "
            f"{int(sin_fecha.sum())} registro(s) (p. ej. "
            f"{_ejemplos(cli.loc[sin_fecha, 'cliente_id'])}); "
            "se toman como los más antiguos de su cliente.",
            stacklevel=3,
        )
    cli["_fecha_ord"] = [d.toordinal() if d is not None else -1 for d in fechas]

    # Más reciente por cliente; en empate, el último del archivo (S3).
    cli = cli.sort_values(["_fecha_ord", "_orden"], kind="mergesort")
    vigentes = cli.drop_duplicates(subset="_codigo", keep="last")

    maestro: dict[str, str] = {}
    for codigo, region in zip(vigentes["_codigo"], vigentes["region"]):
        etiqueta = MAPA_REGIONES.get(_normalizar_region(region))
        if etiqueta is None:
            raise ValueError(
                f"La región vigente del cliente {codigo} es {str(region)!r}, "
                "que no encaja en ninguna región oficial (Antioquia, Bogotá D.C., "
                "Caldas, Risaralda, Valle del Cauca). El análisis se detiene (S2)."
            )
        maestro[codigo] = etiqueta
    return maestro


def _a_numero(valor):
    """Escalar de numpy/pandas -> int o float de Python (serializable en JSON)."""
    if isinstance(valor, (int, np.integer)):
        return int(valor)
    numero = float(valor)
    if numero.is_integer():
        return int(numero)
    return numero


def analizar(datos: dict) -> list[dict]:
    ventas = _leer_csv(datos["ventas"])
    maestro = _maestro_clientes(datos["clientes"])

    # 1. Cada documento una vez: primera aparición, antes de filtrar y sumar.
    ventas = ventas.assign(_documento=_normalizar_codigo(ventas["numero_documento"]))
    if (ventas["_documento"] == "").any():
        warnings.warn(
            "ventas: hay filas sin numero_documento; cuentan como un mismo "
            "documento vacío (se queda la primera).",
            stacklevel=2,
        )
    ventas = ventas.drop_duplicates(subset="_documento", keep="first")

    # 2. Fechas leídas a mano (ISO o dd/mm/aaaa) y solo el semestre, bordes incluidos.
    fechas = ventas["fecha"].map(_parsear_fecha)
    sin_fecha = fechas.isna()
    if sin_fecha.any():
        warnings.warn(
            f"ventas: {int(sin_fecha.sum())} documento(s) con fecha ilegible "
            f"(p. ej. {_ejemplos(ventas.loc[sin_fecha, 'numero_documento'])}); "
            "no se puede mostrar que caigan en el semestre y quedan fuera.",
            stacklevel=2,
        )
    en_semestre = np.array(
        [d is not None and INICIO <= d <= FIN for d in fechas], dtype=bool
    )
    ventas = ventas[en_semestre]

    # 3. FV suma el subtotal, NC lo resta; cualquier otro tipo no cuenta.
    #    Las columnas iva y total no se usan.
    signo = _normalizar_codigo(ventas["tipo_documento"]).map(SIGNO_POR_TIPO)
    cuenta = signo.notna()
    ventas = ventas[cuenta]
    signo = signo[cuenta].astype(int)

    subtotal = pd.to_numeric(_texto(ventas["subtotal"]).str.strip(), errors="coerce")
    sin_subtotal = subtotal.isna()
    if sin_subtotal.any():
        warnings.warn(
            f"ventas: {int(sin_subtotal.sum())} documento(s) del semestre con "
            f"subtotal no numérico (p. ej. "
            f"{_ejemplos(ventas.loc[sin_subtotal, 'numero_documento'])}); "
            "suman 0.",
            stacklevel=2,
        )
    neto = subtotal.fillna(0) * signo

    # 4. Región vigente del cliente; sin cliente o fuera del maestro -> «Sin región».
    region = _normalizar_codigo(ventas["cliente_id"]).map(maestro)
    region = region.astype(object).where(region.notna(), SIN_REGION)

    totales = neto.groupby(region).sum() if len(neto) else pd.Series(dtype=float)

    oficiales = [(r, _a_numero(totales.get(r, 0))) for r in REGIONES_OFICIALES]
    # De mayor a menor; los empates conservan el orden de la lista oficial.
    oficiales.sort(key=lambda par: par[1], reverse=True)

    filas = [{"region": r, "ventas_netas": v} for r, v in oficiales]
    filas.append(
        {"region": SIN_REGION, "ventas_netas": _a_numero(totales.get(SIN_REGION, 0))}
    )
    return filas

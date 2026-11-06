"""Ventas netas por región del primer semestre de 2026.

Reglas del glosario del negocio (negocio.md):
  * Ventas = suma del subtotal de las FV menos suma del subtotal de las NC.
    El IVA nunca cuenta.
  * Cada documento cuenta en su fecha; el semestre va del 2026-01-01 al
    2026-06-30, ambos incluidos.
  * numero_documento identifica un documento y cuenta una sola vez.
  * La región de una venta es la del registro más reciente del cliente en el
    maestro (fecha_actualizacion), aunque la venta sea anterior al cambio.
  * Regiones oficiales: Antioquia, Bogotá D.C., Caldas, Risaralda y Valle del
    Cauca. Sin código, o con un código fuera del maestro: «Sin región».

Limpieza que exigen los datos:
  * Las fechas vienen como AAAA-MM-DD o DD/MM/AAAA. El orden día/mes está
    confirmado en el archivo: hay fechas con barra cuyo primer número pasa de
    12 y ninguna cuyo segundo número pase de 12.
  * Los códigos de cliente traen espacios o minúsculas («c055», « C012»).
  * El maestro escribe la misma región de varias formas («CALDAS »,
    «BOGOTA DC», «Valle»).
  * Hay documentos repetidos como copias idénticas.
Lo que no tiene una lectura segura (fecha ilegible, región desconocida,
copias que no coinciden, montos negativos) detiene el cálculo con un error en
lugar de adivinar.

Uso: python analisis.py ventas.csv clientes.csv
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
import warnings

import pandas as pd

INICIO = pd.Timestamp("2026-01-01")
FIN = pd.Timestamp("2026-06-30")
REGIONES_OFICIALES = ["Antioquia", "Bogotá D.C.", "Caldas", "Risaralda", "Valle del Cauca"]
SIN_REGION = "Sin región"

# Escritura de la región reducida a letras y números, sin tildes ni mayúsculas.
_ALIAS_REGION = {
    "antioquia": "Antioquia",
    "bogotadc": "Bogotá D.C.",
    "bogota": "Bogotá D.C.",
    "caldas": "Caldas",
    "risaralda": "Risaralda",
    "valledelcauca": "Valle del Cauca",
    "valle": "Valle del Cauca",  # «el Valle» es el Valle del Cauca
}
_SIGNO = {"FV": 1, "NC": -1}  # las notas crédito (devoluciones) restan


def _clave(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", sin_tildes.lower())


def _leer(ruta: str, columnas: set[str]) -> pd.DataFrame:
    df = pd.read_csv(ruta, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    faltan = columnas - set(df.columns)
    if faltan:
        raise ValueError(f"{ruta}: faltan las columnas {sorted(faltan)}")
    return df


def _fechas(serie: pd.Series) -> pd.Series:
    texto = serie.str.strip()
    fecha = pd.to_datetime(texto, format="%Y-%m-%d", errors="coerce")
    fecha = fecha.fillna(pd.to_datetime(texto, format="%d/%m/%Y", errors="coerce"))
    ilegibles = sorted(set(texto[fecha.isna()]))
    if ilegibles:
        raise ValueError(f"Fechas que no se pueden leer: {ilegibles[:10]}")
    return fecha


def _codigo(serie: pd.Series) -> pd.Series:
    return serie.str.strip().str.upper()


def _region_vigente(ruta: str) -> pd.Series:
    """cliente_id -> región oficial de su registro más reciente en el maestro."""
    maestro = _leer(ruta, {"cliente_id", "region", "fecha_actualizacion"})
    oficial = maestro["region"].map(lambda r: _ALIAS_REGION.get(_clave(r)))
    desconocidas = sorted(set(maestro.loc[oficial.isna(), "region"]))
    if desconocidas:
        raise ValueError(f"Regiones del maestro sin equivalente oficial: {desconocidas}")
    maestro = maestro.assign(
        cliente_id=_codigo(maestro["cliente_id"]),
        region=oficial,
        fecha=_fechas(maestro["fecha_actualizacion"]),
    )
    vigente = maestro[maestro["fecha"] == maestro.groupby("cliente_id")["fecha"].transform("max")]
    regiones = vigente.groupby("cliente_id")["region"].nunique()
    if (regiones > 1).any():
        raise ValueError(
            f"Clientes con dos regiones en la misma fecha: {sorted(regiones[regiones > 1].index)}"
        )
    return vigente.drop_duplicates("cliente_id").set_index("cliente_id")["region"]


def _documentos_del_semestre(datos: dict) -> pd.DataFrame:
    ventas = _leer(
        datos["ventas"], {"numero_documento", "tipo_documento", "fecha", "cliente_id", "subtotal"}
    )
    ventas = ventas.assign(
        numero_documento=_codigo(ventas["numero_documento"]),
        tipo_documento=_codigo(ventas["tipo_documento"]),
        fecha=_fechas(ventas["fecha"]),
        cliente_id=_codigo(ventas["cliente_id"]),
        subtotal=pd.to_numeric(ventas["subtotal"].str.strip(), errors="coerce"),
    )
    if ventas["subtotal"].isna().any() or (ventas["subtotal"] < 0).any():
        malos = ventas.loc[ventas["subtotal"].isna() | (ventas["subtotal"] < 0), "numero_documento"]
        raise ValueError(f"Subtotales vacíos, ilegibles o negativos en: {sorted(malos)[:10]}")

    # Cada documento cuenta una vez; sus filas repetidas deben ser copias idénticas.
    campos = ["numero_documento", "tipo_documento", "fecha", "cliente_id", "subtotal"]
    copias_distintas = ventas.drop_duplicates(campos)["numero_documento"]
    if copias_distintas.duplicated().any():
        raise ValueError(
            "Documentos repetidos con datos distintos: "
            f"{sorted(set(copias_distintas[copias_distintas.duplicated()]))[:10]}"
        )
    documentos = ventas.drop_duplicates("numero_documento")

    otros = documentos.loc[~documentos["tipo_documento"].isin(_SIGNO), "tipo_documento"]
    if not otros.empty:
        warnings.warn(f"No son FV ni NC y no cuentan como venta: {otros.value_counts().to_dict()}")

    semestre = documentos[
        documentos["tipo_documento"].isin(_SIGNO) & documentos["fecha"].between(INICIO, FIN)
    ]
    region = _region_vigente(datos["clientes"])
    return semestre.assign(
        region=semestre["cliente_id"].map(region).fillna(SIN_REGION),
        ventas=semestre["subtotal"] * semestre["tipo_documento"].map(_SIGNO),
    )


def _numero(valor) -> int | float:
    return int(valor) if float(valor).is_integer() else round(float(valor), 2)


def analizar(datos: dict) -> list[dict]:
    """Una fila por región: {"region": ..., "ventas": ...} en pesos, netas y sin IVA.

    datos = {"ventas": ruta_csv, "clientes": ruta_csv}. Las cinco regiones
    oficiales siempre aparecen; «Sin región» aparece cuando hay documentos sin
    cliente identificado.
    """
    semestre = _documentos_del_semestre(datos)
    por_region = semestre.groupby("region")["ventas"].sum()
    filas = [{"region": r, "ventas": _numero(por_region.get(r, 0))} for r in REGIONES_OFICIALES]
    if SIN_REGION in por_region.index:
        filas.append({"region": SIN_REGION, "ventas": _numero(por_region[SIN_REGION])})
    return filas


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Uso: python analisis.py ventas.csv clientes.csv")
    resultado = analizar({"ventas": sys.argv[1], "clientes": sys.argv[2]})
    print(json.dumps(resultado, ensure_ascii=False, indent=2))

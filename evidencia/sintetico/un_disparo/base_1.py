"""Ventas netas por región del primer semestre de 2026.

Reglas del glosario del negocio (negocio.md), aplicadas tal cual:

- Ventas: netas y sin IVA. Suma del ``subtotal`` de las facturas de venta (FV)
  menos la suma del ``subtotal`` de las notas crédito (NC). El IVA nunca cuenta.
- Fecha: cada documento cuenta en su ``fecha``. Primer semestre: del 1 de enero
  al 30 de junio, ambos incluidos.
- Documento: ``numero_documento`` lo identifica; cada documento cuenta una vez.
- Cliente: código ``C`` seguido de tres dígitos.
- Región de una venta: la del registro más reciente del cliente en el maestro
  (``fecha_actualizacion``), aunque la venta sea anterior al cambio.
- Regiones oficiales: Antioquia, Bogotá D.C., Caldas, Risaralda, Valle del Cauca.
- Ventas sin cliente identificado (sin código, o con un código que no está en
  el maestro) no se descartan: se reportan como «Sin región».

Limpieza que piden los datos (ninguna cambia la definición de venta):

- Filas repetidas con el mismo ``numero_documento`` se cuentan una vez. Si dos
  filas del mismo documento no coinciden, el cálculo se detiene con error,
  porque el glosario no dice cuál de las dos vale.
- Fechas en dos formatos: ``AAAA-MM-DD`` y ``DD/MM/AAAA`` (día primero).
- Espacios y minúsculas en los códigos de cliente (``" c023"`` -> ``"C023"``).
- Regiones escritas de varias formas (``"CALDAS "``, ``"BOGOTA DC"``,
  ``"Valle"``...) llevadas a su nombre oficial. Un valor que no se pueda llevar
  a una región oficial detiene el cálculo en vez de adivinarlo.

Uso: ``python analisis.py [ventas.csv clientes.csv]`` (por defecto, ../datos).
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
import warnings
from pathlib import Path

import pandas as pd

INICIO = pd.Timestamp("2026-01-01")
FIN = pd.Timestamp("2026-06-30")  # incluido: las fechas no traen hora
REGIONES_OFICIALES = ["Antioquia", "Bogotá D.C.", "Caldas", "Risaralda", "Valle del Cauca"]
SIN_REGION = "Sin región"
SIGNO = {"FV": 1, "NC": -1}


def _clave(texto: str) -> str:
    """Forma comparable de un nombre: sin tildes, en minúsculas y solo letras."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", sin_tildes.lower())


ALIAS_REGION = {_clave(r): r for r in REGIONES_OFICIALES}
# Formas cortas que no se confunden con ninguna otra región oficial.
ALIAS_REGION.update({"bogota": "Bogotá D.C.", "valle": "Valle del Cauca"})


def _leer(ruta) -> pd.DataFrame:
    """Lee todo como texto (sin convertir vacíos en NaN) y quita espacios."""
    df = pd.read_csv(ruta, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    return df.apply(lambda col: col.str.strip())


def _fechas(serie: pd.Series) -> pd.Series:
    """Convierte AAAA-MM-DD y DD/MM/AAAA; cualquier otra cosa es un error."""
    iso = pd.to_datetime(serie.where(serie.str.fullmatch(r"\d{4}-\d{2}-\d{2}")),
                         format="%Y-%m-%d", errors="coerce")
    dma = pd.to_datetime(serie.where(serie.str.fullmatch(r"\d{2}/\d{2}/\d{4}")),
                         format="%d/%m/%Y", errors="coerce")
    fechas = iso.fillna(dma)
    if fechas.isna().any():
        malas = sorted(serie[fechas.isna()].unique())
        raise ValueError(f"Fechas que no se pueden leer como AAAA-MM-DD ni DD/MM/AAAA: {malas[:10]}")
    return fechas


def _region_vigente(clientes: pd.DataFrame) -> dict[str, str]:
    """Código de cliente -> región oficial de su registro más reciente."""
    maestro = clientes.assign(
        cliente_id=clientes["cliente_id"].str.upper(),
        fecha_actualizacion=_fechas(clientes["fecha_actualizacion"]),
    )
    ultima = maestro.groupby("cliente_id")["fecha_actualizacion"].transform("max")
    vigentes = maestro[maestro["fecha_actualizacion"] == ultima].copy()
    vigentes["region_oficial"] = vigentes["region"].map(lambda r: ALIAS_REGION.get(_clave(r)))

    sin_oficial = sorted(vigentes.loc[vigentes["region_oficial"].isna(), "region"].unique())
    if sin_oficial:
        raise ValueError(f"Regiones del maestro que no son una región oficial: {sin_oficial}")
    empates = vigentes.groupby("cliente_id")["region_oficial"].nunique()
    if (empates > 1).any():
        raise ValueError("Clientes con dos regiones distintas en su fecha más reciente: "
                         f"{sorted(empates[empates > 1].index)}")
    return vigentes.drop_duplicates("cliente_id").set_index("cliente_id")["region_oficial"].to_dict()


def _numero(valor) -> int | float:
    valor = float(valor)
    return int(valor) if valor.is_integer() else round(valor, 2)


def analizar(datos: dict) -> list[dict]:
    """Una fila por región ({"region", "ventas"}): ventas netas sin IVA del 1-ene al 30-jun-2026."""
    region_de = _region_vigente(_leer(datos["clientes"]))
    crudas = _leer(datos["ventas"])

    docs = pd.DataFrame({
        "numero_documento": crudas["numero_documento"],
        "tipo_documento": crudas["tipo_documento"].str.upper(),
        "fecha": _fechas(crudas["fecha"]),
        "cliente_id": crudas["cliente_id"].str.upper(),
        "subtotal": pd.to_numeric(crudas["subtotal"], errors="raise"),
    })
    if (docs["subtotal"] < 0).any():
        raise ValueError("Hay subtotales negativos; el glosario no dice cómo tratarlos.")

    # Cada documento cuenta una vez; las copias deben ser idénticas.
    docs = docs.drop_duplicates()
    repetidos = docs.loc[docs["numero_documento"].duplicated(), "numero_documento"]
    if len(repetidos):
        raise ValueError(f"Documentos repetidos con datos distintos: {sorted(repetidos.unique())[:10]}")

    otros = docs.loc[~docs["tipo_documento"].isin(SIGNO), "tipo_documento"]
    if len(otros):
        warnings.warn(f"Quedan fuera documentos que no son FV ni NC: {otros.value_counts().to_dict()}")

    docs = docs[docs["tipo_documento"].isin(SIGNO) & docs["fecha"].between(INICIO, FIN)]
    docs = docs.assign(
        region=docs["cliente_id"].map(region_de).fillna(SIN_REGION),  # vacío o fuera del maestro
        neto=docs["subtotal"] * docs["tipo_documento"].map(SIGNO),
    )

    totales = docs.groupby("region")["neto"].sum()
    filas = [{"region": r, "ventas": _numero(totales.get(r, 0))} for r in REGIONES_OFICIALES]
    if SIN_REGION in totales.index:
        filas.append({"region": SIN_REGION, "ventas": _numero(totales[SIN_REGION])})
    return filas


if __name__ == "__main__":
    carpeta = Path(__file__).resolve().parent.parent / "datos"
    rutas = {
        "ventas": sys.argv[1] if len(sys.argv) > 1 else carpeta / "ventas.csv",
        "clientes": sys.argv[2] if len(sys.argv) > 2 else carpeta / "clientes.csv",
    }
    print(json.dumps(analizar(rutas), ensure_ascii=False, indent=2))

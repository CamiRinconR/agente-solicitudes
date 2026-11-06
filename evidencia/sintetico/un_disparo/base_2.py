"""Ventas totales por región del primer semestre de 2026.

Aplica las reglas de negocio.md (glosario de ventas):
  * Ventas = suma del subtotal de las FV menos la suma del subtotal de las NC.
    El IVA nunca cuenta como venta.
  * Cada documento cuenta en su fecha. Primer semestre: del 1 de enero al 30 de
    junio de 2026, ambos incluidos.
  * numero_documento identifica un documento y cada documento cuenta una vez.
  * La región de una venta es la vigente del cliente: la de su registro más
    reciente en el maestro (fecha_actualizacion), aunque la venta sea anterior.
  * Las ventas sin cliente identificado (sin código, o con un código que no está
    en el maestro) se reportan como «Sin región».

Limpieza que exigen los datos (cada caso queda contado en diagnosticar()):
  * Fechas en dos formatos: AAAA-MM-DD y DD/MM/AAAA.
  * Códigos de cliente con espacios o en minúscula («c055», « C017 »).
  * Regiones escritas de varias formas («CALDAS », «BOGOTA DC», «Valle»...).
  * Documentos repetidos con el mismo numero_documento.

Ante lo que no se puede decidir sin el negocio (una región o una fecha que no
reconoce, un documento repetido con datos distintos, un subtotal negativo, dos
registros vigentes del mismo cliente con regiones distintas), se detiene con
ValueError en lugar de adivinar.

Uso:
    analizar({"ventas": "ventas.csv", "clientes": "clientes.csv"})
    python analisis.py [ventas.csv clientes.csv]
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

INICIO = pd.Timestamp("2026-01-01")
FIN = pd.Timestamp("2026-06-30")

REGIONES_OFICIALES = ("Antioquia", "Bogotá D.C.", "Caldas", "Risaralda", "Valle del Cauca")
SIN_REGION = "Sin región"

# Signo con el que entra cada tipo de documento en las ventas netas.
SIGNO = {"FV": 1, "NC": -1}

# Forma canónica (sin tildes, minúsculas, sin puntuación, espacios simples) -> región oficial.
ALIAS_REGION = {
    "antioquia": "Antioquia",
    "bogota dc": "Bogotá D.C.",
    "bogota": "Bogotá D.C.",  # «Bogotá» a secas
    "caldas": "Caldas",
    "risaralda": "Risaralda",
    "valle del cauca": "Valle del Cauca",
    "valle": "Valle del Cauca",  # «Valle» a secas: inferido, el glosario no lo dice
}

PATRON_CLIENTE = re.compile(r"C\d{3}")


def _canon(texto: str) -> str:
    sin_tildes = "".join(
        ch for ch in unicodedata.normalize("NFKD", str(texto)) if not unicodedata.combining(ch)
    )
    sin_puntuacion = re.sub(r"[^\w\s]", "", sin_tildes.lower())
    return re.sub(r"\s+", " ", sin_puntuacion).strip()


def _region_oficial(texto: str) -> str:
    clave = _canon(texto)
    if clave not in ALIAS_REGION:
        raise ValueError(f"Región no reconocida en el maestro de clientes: {texto!r}")
    return ALIAS_REGION[clave]


def _fecha(texto: str) -> pd.Timestamp:
    s = str(texto).strip()
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", s):
        return pd.to_datetime(s, format="%Y-%m-%d")
    if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", s):
        # Día/mes/año. Si un archivo trajera mes/día, un «mes» mayor que 12 rompe aquí.
        try:
            return pd.to_datetime(s, format="%d/%m/%Y")
        except ValueError:
            raise ValueError(f"Fecha que no es día/mes/año válido: {texto!r}") from None
    raise ValueError(f"Fecha con formato no reconocido: {texto!r}")


def _leer(ruta: str, columnas: list[str]) -> pd.DataFrame:
    tabla = pd.read_csv(ruta, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    tabla.columns = tabla.columns.str.strip()
    faltan = set(columnas) - set(tabla.columns)
    if faltan:
        raise ValueError(f"{ruta}: faltan las columnas {sorted(faltan)}")
    return tabla


def _maestro(ruta: str, diag: dict) -> pd.DataFrame:
    """Maestro limpio, ordenado por cliente y fecha de actualización (el último es el vigente)."""
    m = _leer(ruta, ["cliente_id", "region", "fecha_actualizacion"])
    m["cliente"] = m["cliente_id"].str.strip().str.upper()
    m["region_oficial"] = m["region"].map(_region_oficial)
    m["fecha_act"] = m["fecha_actualizacion"].map(_fecha)
    m = m.sort_values(["cliente", "fecha_act"], kind="stable").reset_index(drop=True)

    ultima = m.groupby("cliente")["fecha_act"].transform("max")
    candidatos = m[m["fecha_act"] == ultima]
    regiones_por_cliente = candidatos.groupby("cliente")["region_oficial"].nunique()
    dudosos = regiones_por_cliente[regiones_por_cliente > 1]
    if len(dudosos):
        raise ValueError(
            f"Clientes con dos registros vigentes (misma fecha) y regiones distintas: {list(dudosos.index)}"
        )

    diag["maestro"] = {
        "registros": len(m),
        "clientes": int(m["cliente"].nunique()),
        "clientes_con_varios_registros": sorted(m.loc[m["cliente"].duplicated(), "cliente"].unique()),
        "textos_de_region_unificados": {
            txt: _region_oficial(txt)
            for txt in sorted(set(m["region"]))
            if txt != _region_oficial(txt)
        },
    }
    return m


def _documentos(ruta: str, diag: dict) -> pd.DataFrame:
    """Documentos limpios, uno por numero_documento, solo FV y NC."""
    v = _leer(ruta, ["numero_documento", "tipo_documento", "fecha", "cliente_id", "subtotal"])
    v["documento"] = v["numero_documento"].str.strip().str.upper()
    v["tipo"] = v["tipo_documento"].str.strip().str.upper()
    v["fecha_doc"] = v["fecha"].map(_fecha)
    v["cliente"] = v["cliente_id"].str.strip().str.upper()
    v["valor"] = pd.to_numeric(v["subtotal"].str.strip(), errors="raise")
    if (v["documento"] == "").any():
        raise ValueError("Hay filas sin numero_documento: no se puede saber si repiten otro documento.")
    if (v["valor"] < 0).any():
        raise ValueError("Hay subtotales negativos: no se sabe si las NC ya traen el signo.")

    campos = ["tipo", "fecha_doc", "cliente", "valor"]
    repetidos = v[v["documento"].duplicated(keep=False)]
    con_diferencias = repetidos.groupby("documento")[campos].nunique().gt(1).any(axis=1)
    if con_diferencias.any():
        raise ValueError(
            f"Documentos repetidos con datos distintos: {list(con_diferencias[con_diferencias].index)}"
        )
    copias = v[v["documento"].duplicated(keep="first")]
    v = v.drop_duplicates("documento", keep="first")

    otros_tipos = v[~v["tipo"].isin(SIGNO)]
    v = v[v["tipo"].isin(SIGNO)].copy()
    v["neto"] = v["valor"] * v["tipo"].map(SIGNO)

    barra = v["fecha"].str.contains("/")
    dia_barra = v.loc[barra, "fecha"].str.strip().str.split("/").str[0].astype(int)
    crudo = v["cliente_id"]
    en_s1_copias = copias[(copias["fecha_doc"] >= INICIO) & (copias["fecha_doc"] <= FIN)]
    diag["ventas"] = {
        "filas": int(len(v) + len(copias) + len(otros_tipos)),
        "copias_descartadas": int(len(copias)),
        "copias_descartadas_en_s1": int(len(en_s1_copias)),
        "monto_que_inflarian_en_s1": int((en_s1_copias["valor"] * en_s1_copias["tipo"].map(SIGNO).fillna(0)).sum()),
        "tipos_excluidos": otros_tipos["tipo"].value_counts().to_dict(),
        "fechas_dd_mm_aaaa": int(barra.sum()),
        "fechas_dd_mm_aaaa_con_dia_mayor_a_12": int((dia_barra > 12).sum()),
        "codigos_cliente_corregidos": int(((crudo != "") & (crudo != v["cliente"])).sum()),
        "codigos_cliente_fuera_de_formato": sorted(
            set(c for c in v["cliente"] if c and not PATRON_CLIENTE.fullmatch(c))
        ),
        "rango_de_fechas": [str(v["fecha_doc"].min().date()), str(v["fecha_doc"].max().date())],
    }
    return v


def _calcular(datos: dict) -> tuple[list[dict], dict]:
    diag: dict = {}
    maestro = _maestro(datos["clientes"], diag)
    docs = _documentos(datos["ventas"], diag)

    vigente = maestro.drop_duplicates("cliente", keep="last").set_index("cliente")["region_oficial"]
    s1 = docs[(docs["fecha_doc"] >= INICIO) & (docs["fecha_doc"] <= FIN)].copy()
    s1["region"] = s1["cliente"].map(vigente).fillna(SIN_REGION)

    por_region = s1.groupby("region")["neto"].sum()
    oficiales = sorted(
        ({"region": r, "ventas": int(por_region.get(r, 0))} for r in REGIONES_OFICIALES),
        key=lambda fila: (-fila["ventas"], fila["region"]),
    )
    filas = oficiales + [{"region": SIN_REGION, "ventas": int(por_region.get(SIN_REGION, 0))}]

    # Diagnóstico del semestre.
    sin_region = s1[s1["region"] == SIN_REGION]
    sin_codigo = sin_region[sin_region["cliente"] == ""]
    fuera = sin_region[sin_region["cliente"] != ""]

    # Ventas que el glosario lleva a la región vigente aunque en su fecha el cliente estaba en otra.
    historial = maestro[["cliente", "fecha_act", "region_oficial"]].sort_values("fecha_act")
    con_cambio = maestro.groupby("cliente")["region_oficial"].nunique()
    con_cambio = list(con_cambio[con_cambio > 1].index)
    candidatas = s1[s1["cliente"].isin(con_cambio)].sort_values("fecha_doc")
    en_su_fecha = pd.merge_asof(
        candidatas, historial.rename(columns={"region_oficial": "region_en_su_fecha"}),
        left_on="fecha_doc", right_on="fecha_act", by="cliente", direction="backward",
    )
    movidas = en_su_fecha[
        en_su_fecha["region_en_su_fecha"].notna() & (en_su_fecha["region_en_su_fecha"] != en_su_fecha["region"])
    ]

    iva_s1 = None
    if "iva" in s1.columns:
        iva_s1 = int((pd.to_numeric(s1["iva"].str.strip(), errors="coerce").fillna(0) * s1["tipo"].map(SIGNO)).sum())

    diag["semestre"] = {
        "periodo": [str(INICIO.date()), str(FIN.date())],
        "facturas": int((s1["tipo"] == "FV").sum()),
        "notas_credito": int((s1["tipo"] == "NC").sum()),
        "subtotal_facturas": int(s1.loc[s1["tipo"] == "FV", "valor"].sum()),
        "subtotal_notas_credito": int(s1.loc[s1["tipo"] == "NC", "valor"].sum()),
        "ventas_netas_total": int(s1["neto"].sum()),
        "iva_neto_excluido": iva_s1,
        "sin_region": {
            "sin_codigo": {"documentos": int(len(sin_codigo)), "ventas": int(sin_codigo["neto"].sum())},
            "codigo_fuera_del_maestro": {
                "codigos": sorted(fuera["cliente"].unique()),
                "documentos": int(len(fuera)),
                "ventas": int(fuera["neto"].sum()),
            },
        },
        "reasignadas_por_cambio_de_region": [
            {
                "cliente": cliente,
                "de": de,
                "a": a,
                "documentos": int(len(grupo)),
                "ventas": int(grupo["neto"].sum()),
            }
            for (cliente, de, a), grupo in movidas.groupby(["cliente", "region_en_su_fecha", "region"])
        ],
        "historial_de_clientes_con_cambio": {
            cliente: [
                (str(f.date()), r)
                for f, r in maestro.loc[maestro["cliente"] == cliente, ["fecha_act", "region_oficial"]].itertuples(index=False)
            ]
            for cliente in con_cambio
        },
    }
    if sum(f["ventas"] for f in filas) != diag["semestre"]["ventas_netas_total"]:
        raise AssertionError("Las filas por región no suman el total del semestre.")
    return filas, diag


def analizar(datos: dict) -> list[dict]:
    """Una fila por región ({"region", "ventas"}): ventas netas sin IVA del primer semestre de 2026."""
    filas, _ = _calcular(datos)
    return filas


def diagnosticar(datos: dict) -> dict:
    """Lo que la limpieza encontró y corrigió, con cifras, para contárselo a quien pidió el dato."""
    _, diag = _calcular(datos)
    return diag


if __name__ == "__main__":
    carpeta = Path(__file__).resolve().parent.parent / "datos"
    datos = {
        "ventas": sys.argv[1] if len(sys.argv) > 1 else str(carpeta / "ventas.csv"),
        "clientes": sys.argv[2] if len(sys.argv) > 2 else str(carpeta / "clientes.csv"),
    }
    filas, diag = _calcular(datos)
    print(json.dumps({"resultado": filas, "diagnostico": diag}, ensure_ascii=False, indent=2, default=str))

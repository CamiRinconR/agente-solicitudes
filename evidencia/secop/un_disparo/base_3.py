"""Valor contratado en 2025 por cada entidad pública con sede en Medellín (SECOP II).

Reglas del glosario del negocio (negocio.md):
- Un contrato cuenta en el año de su `fecha_de_firma`, del 1 de enero al 31 de
  diciembre con los dos días completos: se filtra con [2025-01-01, 2026-01-01),
  nunca comparando texto contra '2025-12-31' (eso deja fuera las firmas del 31 con hora).
- Valor contratado = `valor_del_contrato` tal como figura hoy (con adiciones);
  no se usan `valor_facturado` ni `valor_pagado`.
- Todo contrato firmado cuenta, sin importar su estado.
- Un contrato se identifica por `id_contrato` y cuenta una sola vez.
- Los contratos de valor cero cuentan en el número y suman cero al valor.

Decisiones propias (explicadas en `diagnostico`):
- La entidad se identifica por `nit_entidad`, tal como figura en SECOP II. Varias
  unidades de SECOP II (`codigo_entidad`) con el mismo NIT forman una sola fila.
- El nombre se limpia de marcas de la plataforma («//», «*», «COMPRADOR») y, si el
  NIT tiene varios nombres, se toma el más completo de la unidad principal (o el
  prefijo común de las unidades, p. ej. «SENA REGIONAL ANTIOQUIA»).
- La sede es la columna `ciudad` = Medellín (el archivo ya viene recortado así).

Los valores se suman con Decimal para no perder centavos en totales de billones.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from decimal import Decimal, InvalidOperation

import pandas as pd

ANIO = 2025
CIUDAD = "medellin"
ESTADOS_FIRMADOS = {
    "en ejecucion", "modificado", "terminado", "cerrado",
    "aprobado", "suspendido", "cedido",
}
# Palabras que no cierran un nombre cuando se recorta al prefijo común.
PALABRAS_COLGANTES = {"grupo", "de", "del", "la", "las", "los", "el", "y", "e", "-"}


# --------------------------------------------------------------------------- utilidades

def _clave(texto: str) -> str:
    """Texto sin tildes, sin espacios repetidos y en minúsculas, para comparar."""
    texto = " ".join(str(texto).split())
    texto = "".join(c for c in unicodedata.normalize("NFKD", texto)
                     if not unicodedata.combining(c))
    return texto.casefold()


def _reparar_c1(texto: str) -> str:
    """Caracteres de control C1 (U+0080–U+009F) son bytes Windows-1252 mal leídos
    (p. ej. U+0096 = «–» en «Rama Judicial – Dirección Seccional...»)."""
    return re.sub(r"[\x80-\x9f]",
                  lambda m: m.group().encode("latin-1").decode("cp1252", errors="ignore"),
                  texto)


def _limpiar_nombre(nombre: str) -> str:
    """Quita marcas de la plataforma al final del nombre («//», «*», «COMPRADOR»)."""
    n = " ".join(_reparar_c1(str(nombre)).split())
    n = re.sub(r"[/*\s]+$", "", n)
    n = re.sub(r"(?:\s*-\s*|\s+)COMPRADOR$", "", n, flags=re.IGNORECASE)
    return re.sub(r"[/*\s]+$", "", n)


def _normalizar_nit(nit: str) -> str:
    """NIT tal como figura en SECOP II, sin espacios ni puntos ni un «-DV» explícito."""
    nit = re.sub(r"[\s.]", "", str(nit))
    return nit.split("-")[0]


def _decimal(texto: str) -> Decimal | None:
    try:
        valor = Decimal(str(texto).strip())
    except (InvalidOperation, ValueError):
        return None
    return valor if valor.is_finite() else None


def _numero(valor: Decimal) -> float | int:
    valor = valor.quantize(Decimal("0.01"))
    return int(valor) if valor == valor.to_integral_value() else float(valor)


def _mas_completo(nombres: pd.Series) -> str:
    """Variante más larga (las abreviaturas son más cortas); empate: la más frecuente."""
    conteo = nombres.value_counts()
    return max(conteo.index, key=lambda n: (len(n), conteo[n]))


def _prefijo_comun(nombres: list[str]) -> str | None:
    palabras = [n.split() for n in nombres]
    comun = 0
    for grupo in zip(*palabras):
        if len({_clave(p) for p in grupo}) != 1:
            break
        comun += 1
    while comun and _clave(palabras[0][comun - 1]) in PALABRAS_COLGANTES:
        comun -= 1
    return " ".join(palabras[0][:comun]) if comun >= 2 else None


# --------------------------------------------------------------------------- preparación

def _cargar(datos: dict) -> pd.DataFrame:
    df = pd.read_csv(datos["contratos"], dtype=str, keep_default_na=False, encoding="utf-8")
    df["_id"] = df["id_contrato"].str.strip().str.upper()
    df["_nit"] = df["nit_entidad"].map(_normalizar_nit)
    df["_codigo"] = df["codigo_entidad"].str.strip()
    df["_nombre"] = df["nombre_entidad"].map(_limpiar_nombre)
    df["_fecha"] = pd.to_datetime(df["fecha_de_firma"].str.strip(), format="ISO8601",
                                  errors="coerce")
    df["_valor"] = df["valor_del_contrato"].map(_decimal)
    df["_estado"] = df["estado_contrato"].map(_clave)
    df["_ciudad"] = df["ciudad"].map(_clave)
    return df


def _contratos_del_anio(df: pd.DataFrame) -> pd.DataFrame:
    # Un contrato cuenta una sola vez: si un id se repite, queda su versión más reciente.
    df = (df.sort_values("ultima_actualizacion", kind="stable")
            .drop_duplicates("_id", keep="last"))
    inicio, fin = pd.Timestamp(ANIO, 1, 1), pd.Timestamp(ANIO + 1, 1, 1)
    en_anio = (df["_fecha"] >= inicio) & (df["_fecha"] < fin)
    return df[en_anio & (df["_ciudad"] == CIUDAD)].copy()


def _nombre_de_entidad(filas: pd.DataFrame) -> str:
    por_codigo = (filas.groupby("_codigo")
                  .agg(n=("_id", "size"), v=("_valor_float", "sum"))
                  .sort_values(["n", "v"], ascending=False))
    nombres = {c: _mas_completo(filas.loc[filas["_codigo"] == c, "_nombre"])
               for c in por_codigo.index}
    if len(nombres) > 1:
        prefijo = _prefijo_comun(list(nombres.values()))
        if prefijo:
            return prefijo
    return nombres[por_codigo.index[0]]


# --------------------------------------------------------------------------- análisis

def analizar(datos: dict) -> list[dict]:
    """Una fila por entidad (NIT) con el valor y el número de contratos firmados en 2025."""
    anio = _contratos_del_anio(_cargar(datos))
    # Un valor ilegible cuenta como contrato y suma cero (diagnostico() lo reporta).
    anio["_valor"] = anio["_valor"].map(lambda v: v if isinstance(v, Decimal) else Decimal(0))
    anio["_valor_float"] = anio["_valor"].map(float)

    filas = []
    for nit, grupo in anio.groupby("_nit", sort=False):
        filas.append({
            "nit_entidad": nit,
            "entidad": _nombre_de_entidad(grupo),
            "valor_contratado": _numero(sum(grupo["_valor"], Decimal(0))),
            "numero_contratos": int(grupo["_id"].nunique()),
        })
    filas.sort(key=lambda f: (-f["valor_contratado"], f["nit_entidad"]))
    return filas


def diagnostico(datos: dict) -> dict:
    """Cifras de control para las advertencias a quien pidió el análisis."""
    df = _cargar(datos)
    anio = _contratos_del_anio(df)
    anio["_valor_float"] = anio["_valor"].map(lambda v: float(v) if isinstance(v, Decimal) else 0.0)
    millones = lambda s: round(float(s) / 1e6, 2)

    fecha_txt = df["fecha_de_firma"].str.strip()
    dia = df["_fecha"].dt.strftime("%Y-%m-%d")
    hora = df["_fecha"].dt.hour

    compartidos = {}
    for nit, g in anio.groupby("_nit"):
        if g["_codigo"].nunique() > 1:
            compartidos[nit] = (g.groupby(["_codigo", "_nombre"])
                                .agg(contratos=("_id", "size"), millones=("_valor_float", "sum"))
                                .assign(millones=lambda t: t["millones"].map(millones))
                                .reset_index().to_dict("records"))
    variantes = {cod: sorted(g["nombre_entidad"].unique())
                 for cod, g in anio.groupby("_codigo") if g["nombre_entidad"].nunique() > 1}

    clave_dup = ["_codigo", "referencia_del_contrato", "valor_del_contrato"]
    dup = anio[anio.duplicated(clave_dup, keep=False)]
    dup_extra = anio[anio.duplicated(clave_dup, keep="first")]

    credito = anio[anio["tipo_de_contrato"].map(_clave) == "operaciones de credito publico"]
    upb = anio[anio["_nombre"].map(_clave).str.contains("pontificia bolivariana")]
    nits_anio = set(anio["_nit"])
    sin_contratos = (df[~df["_nit"].isin(nits_anio)]
                     .groupby(["_nit", "_nombre"]).size().reset_index().values.tolist())

    return {
        "filas_archivo": len(df),
        "ids_repetidos_archivo": int(df["_id"].duplicated().sum()),
        "fechas_invalidas": int(df["_fecha"].isna().sum()),
        "valores_no_numericos": int(df["_valor"].isna().sum()),
        "estados_fuera_del_glosario": sorted(set(df["_estado"]) - ESTADOS_FIRMADOS),
        "ciudades": sorted(set(df["_ciudad"])),
        "contratos_2025": len(anio),
        "valor_2025_millones": millones(anio["_valor_float"].sum()),
        "entidades_2025": anio["_nit"].nunique(),
        "unidades_secop_2025": anio["_codigo"].nunique(),
        "contratos_valor_cero_2025": int((anio["_valor_float"] == 0).sum()),
        "firmados_31_dic_2025_con_hora": int((dia == f"{ANIO}-12-31").sum()),
        "perdidos_con_filtro_de_texto": len(anio) - int(((fecha_txt >= f"{ANIO}-01-01")
                                                         & (fecha_txt <= f"{ANIO}-12-31")).sum()),
        "firmas_1_ene_antes_de_5am": {
            str(a): int(((dia == f"{a}-01-01") & (hora < 5)).sum()) for a in (ANIO, ANIO + 1)},
        "nit_con_varias_unidades": compartidos,
        "unidades_con_varios_nombres": variantes,
        "nit_de_10_digitos": sorted(n for n in nits_anio if len(n) == 10),
        "posibles_registros_dobles": {
            "filas_en_grupos": len(dup), "filas_extra": len(dup_extra),
            "millones_filas_extra": millones(dup_extra["_valor_float"].sum())},
        "operaciones_credito_publico": {
            "contratos": len(credito), "millones": millones(credito["_valor_float"].sum()),
            "por_entidad": credito.groupby("_nombre")["_valor_float"].sum()
                                  .map(millones).to_dict()},
        "upb": {"contratos": len(upb), "millones": millones(upb["_valor_float"].sum()),
                "modalidades": upb["modalidad_de_contratacion"].value_counts().to_dict()},
        "entidades_sin_contratos_2025": sin_contratos,
    }


if __name__ == "__main__":
    ruta = sys.argv[1] if len(sys.argv) > 1 else "contratos.csv"
    datos = {"contratos": ruta}
    print(json.dumps({"resultado": analizar(datos), "diagnostico": diagnostico(datos)},
                     ensure_ascii=False, indent=1, default=str))

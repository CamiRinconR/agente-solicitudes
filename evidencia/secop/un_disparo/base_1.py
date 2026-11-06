"""Valor contratado en 2025 por cada entidad pública con sede en Medellín (SECOP II).

Reglas del glosario (negocio.md):
- Un contrato cuenta en el año de su `fecha_de_firma`, del 1 de enero al 31 de
  diciembre, con los dos días completos. La fecha se toma tal como viene en
  SECOP II (hora local), sin convertir zonas horarias.
- Valor contratado = `valor_del_contrato` (con adiciones). No se usan el valor
  facturado ni el pagado.
- Todo contrato firmado cuenta, sea cual sea su estado.
- Un contrato se identifica por `id_contrato` y cuenta una sola vez.
- Los contratos de valor cero cuentan en el número y suman cero al valor.

Decisiones propias (el glosario no las define):
- Entidad = `nit_entidad`. Varias cuentas de SECOP II pueden compartir un NIT
  (p. ej. Distrito de Medellín, Personería y Concejo); se suman en una fila.
- El nombre de cada NIT es el `nombre_entidad` más frecuente entre sus
  contratos del año (desempate: el del contrato firmado más tarde y luego el
  orden alfabético). Se deja tal como figura en SECOP II.
- Se excluyen las entidades privadas que publican en SECOP II (NO_PUBLICAS).
- Sede en Medellín = campo `ciudad` de SECOP II.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

import pandas as pd

ANIO = 2025
CIUDAD = "medellin"

# Entidades privadas presentes en el archivo, por NIT sin dígito de verificación.
NO_PUBLICAS = {
    "890902922": "Universidad Pontificia Bolivariana (universidad privada)",
}

_FECHA = re.compile(r"^\s*(\d{4})-(\d{2})-(\d{2})")


def _sin_tildes(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in texto if not unicodedata.combining(c)).strip().lower()


def _nit9(nit: str) -> str:
    """NIT sin dígito de verificación, solo para comparar con NO_PUBLICAS."""
    digitos = re.sub(r"\D", "", str(nit))
    return digitos[:9] if len(digitos) == 10 else digitos


def _valor(texto: str) -> Decimal:
    texto = str(texto).strip().replace(",", "")
    if texto == "":
        return Decimal(0)
    try:
        return Decimal(texto)
    except InvalidOperation as exc:
        raise ValueError(f"valor_del_contrato no numérico: {texto!r}") from exc


def _leer(datos) -> pd.DataFrame:
    origen = datos["contratos"] if isinstance(datos, dict) else datos
    if isinstance(origen, pd.DataFrame):
        df = origen.fillna("").astype(str).copy()
    else:
        df = pd.read_csv(origen, dtype=str, keep_default_na=False)
    for col in df.columns:
        df[col] = df[col].fillna("").astype(str).str.strip()
    return df


def preparar(datos) -> tuple[pd.DataFrame, dict]:
    """Contratos del año que cuentan, con el detalle de lo que se descartó."""
    df = _leer(datos)
    info = {"filas_archivo": len(df)}

    # Un contrato cuenta una sola vez: si hubiera repetidos, se queda la versión
    # actualizada más recientemente (la que figura hoy en SECOP II).
    df = df.sort_values("ultima_actualizacion", kind="stable")
    antes = len(df)
    df = df.drop_duplicates("id_contrato", keep="last")
    info["repetidos_descartados"] = antes - len(df)

    # Sede en Medellín según el campo ciudad.
    en_medellin = df["ciudad"].map(_sin_tildes) == CIUDAD
    info["fuera_de_medellin"] = int((~en_medellin).sum())
    df = df[en_medellin]

    # Año de firma, sin convertir zona horaria.
    partes = df["fecha_de_firma"].str.extract(_FECHA)
    info["sin_fecha_de_firma"] = int(partes[0].isna().sum())
    df = df[partes[0].notna()].copy()
    df["_anio"] = partes.loc[df.index, 0].astype(int)
    df = df[df["_anio"] == ANIO].copy()

    # Solo entidades públicas.
    privada = df["nit_entidad"].map(_nit9).isin(NO_PUBLICAS)
    info["privadas"] = df[privada].copy()
    df = df[~privada].copy()

    df["_valor"] = df["valor_del_contrato"].map(_valor)
    return df, info


def _nombre(grupo: pd.DataFrame) -> str:
    resumen = (
        grupo.groupby("nombre_entidad")
        .agg(n=("id_contrato", "size"), ultima=("fecha_de_firma", "max"))
        .reset_index()
        .sort_values(["n", "ultima", "nombre_entidad"], ascending=[False, False, True])
    )
    return resumen["nombre_entidad"].iloc[0]


def analizar(datos) -> list[dict]:
    df, _ = preparar(datos)
    filas = []
    for nit, grupo in df.groupby("nit_entidad", sort=True):
        total = sum(grupo["_valor"], Decimal(0))
        filas.append(
            {
                "nit_entidad": nit,
                "entidad": _nombre(grupo),
                "valor_contratado": float(round(total, 2)),
                "numero_contratos": int(grupo["id_contrato"].nunique()),
            }
        )
    filas.sort(key=lambda f: (-f["valor_contratado"], f["nit_entidad"]))
    return filas


if __name__ == "__main__":
    import json
    import sys

    resultado = analizar({"contratos": sys.argv[1]})
    print(json.dumps(resultado, ensure_ascii=False, indent=1))

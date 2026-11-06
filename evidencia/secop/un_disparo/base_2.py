"""Valor contratado en 2025 por cada entidad pública con sede en Medellín (SECOP II).

Reglas del glosario (negocio.md):
- Un contrato cuenta en el año de su `fecha_de_firma`, del 1 de enero al 31 de
  diciembre, con los dos días completos (se compara el año, no una cadena).
- Valor contratado = `valor_del_contrato` (con adiciones). No se usan el valor
  facturado ni el pagado.
- Cuenta todo contrato firmado: en ejecución, modificado, terminado, cerrado,
  aprobado, suspendido o cedido.
- Un contrato se identifica por `id_contrato` y cuenta una sola vez.
- Los contratos de valor cero cuentan en el número y suman cero al valor.

Decisiones propias (el glosario no las fija):
- Entidad = NIT (`nit_entidad`). Si varias unidades compradoras de SECOP II
  comparten un NIT (p. ej., el Distrito, el Concejo y la Personería de Medellín),
  se suman en una sola fila.
- Un NIT de 10 dígitos que es el de 9 más su dígito de verificación válido se une
  al de 9 cuando ambos aparecen. Si no, el NIT se deja como figura en SECOP II.
- Nombre = el `nombre_entidad` más frecuente del NIT entre sus contratos del año
  (si hay empate, el del contrato firmado más tarde).
- Sede = campo `ciudad` igual a Medellín (sin distinguir tildes ni mayúsculas).
- Si un `id_contrato` se repitiera, se conserva la fila con la
  `ultima_actualizacion` más reciente, que es la que figura hoy en SECOP II.
- Los valores se suman con Decimal para no perder centavos.
"""

from __future__ import annotations

import json
import sys
import unicodedata
from decimal import Decimal, InvalidOperation

import pandas as pd

ANIO = 2025
CIUDAD = "medellin"
ESTADOS_QUE_CUENTAN = {
    "en ejecucion",
    "modificado",
    "terminado",
    "cerrado",
    "aprobado",
    "suspendido",
    "cedido",
}
PESOS_DV = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71)
COLUMNAS = [
    "id_contrato",
    "nit_entidad",
    "nombre_entidad",
    "ciudad",
    "estado_contrato",
    "fecha_de_firma",
    "valor_del_contrato",
    "ultima_actualizacion",
]
# Solo para el diagnóstico; el análisis no las necesita.
OPCIONALES = ["codigo_entidad", "referencia_del_contrato", "proceso_de_compra", "tipo_de_contrato"]


def _clave(texto: str) -> str:
    """Texto sin tildes, en minúsculas y con espacios simples, para comparar."""
    sin_tildes = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.lower().split())


def _dv(nit9: str) -> int:
    """Dígito de verificación de la DIAN para un NIT."""
    suma = sum(int(d) * w for d, w in zip(reversed(nit9), PESOS_DV))
    resto = suma % 11
    return resto if resto < 2 else 11 - resto


def _solo_digitos(nits: pd.Series) -> pd.Series:
    return nits.astype(str).str.replace(r"\D", "", regex=True)


def _normalizar_nits(nits: pd.Series) -> pd.Series:
    limpios = _solo_digitos(nits)
    de_nueve = set(limpios[limpios.str.len() == 9])

    def unir(nit: str) -> str:
        if len(nit) == 10 and nit[:9] in de_nueve and _dv(nit[:9]) == int(nit[9]):
            return nit[:9]
        return nit

    return limpios.map(unir)


def _decimal(texto: str, id_contrato: str) -> Decimal:
    limpio = str(texto).strip().replace("$", "").replace(" ", "")
    if limpio == "":
        return Decimal(0)
    try:
        return Decimal(limpio)
    except InvalidOperation as error:
        raise ValueError(f"valor_del_contrato no numérico en {id_contrato}: {texto!r}") from error


def _fechas(serie: pd.Series) -> pd.Series:
    fechas = pd.to_datetime(serie.replace("", None), format="ISO8601", errors="coerce")
    if getattr(fechas.dt, "tz", None) is not None:
        fechas = fechas.dt.tz_convert("America/Bogota").dt.tz_localize(None)
    return fechas


def _suma(valores) -> Decimal:
    return sum(valores, Decimal(0))


def _numero(valor: Decimal) -> int | float:
    valor = valor.quantize(Decimal("0.01"))
    return int(valor) if valor == valor.to_integral_value() else float(valor)


def _preparar(ruta: str) -> tuple[pd.DataFrame, dict]:
    """Lee el CSV, deja los contratos que cuentan en el año y anota lo descartado."""
    df = pd.read_csv(ruta, dtype=str, keep_default_na=False, encoding="utf-8")
    faltan = [c for c in COLUMNAS if c not in df.columns]
    if faltan:
        raise ValueError(f"Faltan columnas en {ruta}: {faltan}")

    notas: dict = {"filas_leidas": int(len(df))}
    df = df[COLUMNAS + [c for c in OPCIONALES if c in df.columns]].copy()
    for col in ("id_contrato", "nit_entidad", "nombre_entidad"):
        df[col] = df[col].str.strip()

    # Un contrato por id_contrato: la versión con la última actualización.
    df["_actualizado"] = _fechas(df["ultima_actualizacion"])
    df["_orden"] = range(len(df))
    df = df.sort_values(["_actualizado", "_orden"], na_position="first")
    notas["filas_id_repetido"] = int(df.duplicated("id_contrato", keep="last").sum())
    df = df.drop_duplicates("id_contrato", keep="last")

    sede = df["ciudad"].map(_clave) == CIUDAD
    notas["fuera_de_medellin"] = int((~sede).sum())
    df = df[sede]

    df["_firma"] = _fechas(df["fecha_de_firma"])
    notas["sin_fecha_de_firma"] = int(df["_firma"].isna().sum())
    df = df[df["_firma"].notna()]

    estado = df["estado_contrato"].map(_clave)
    notas["estados_excluidos"] = df.loc[~estado.isin(ESTADOS_QUE_CUENTAN), "estado_contrato"].value_counts().to_dict()
    df = df[estado.isin(ESTADOS_QUE_CUENTAN)].copy()

    df["_nit"] = _normalizar_nits(df["nit_entidad"])
    notas["nits_unidos_por_dv"] = sorted(set(df.loc[df["_nit"] != _solo_digitos(df["nit_entidad"]), "nit_entidad"]))

    del_anio = df[df["_firma"].dt.year == ANIO].copy()
    notas["contratos_del_anio"] = int(len(del_anio))
    del_anio["_valor"] = [_decimal(v, i) for v, i in zip(del_anio["valor_del_contrato"], del_anio["id_contrato"])]
    return del_anio, notas


def _nombre(grupo: pd.DataFrame) -> str:
    resumen = grupo.groupby("nombre_entidad").agg(n=("id_contrato", "size"), ultima=("_firma", "max"))
    return resumen.sort_values(["n", "ultima"], ascending=False).index[0]


def analizar(datos: dict) -> list[dict]:
    """Una fila por entidad (NIT) con el valor y el número de contratos firmados en 2025."""
    contratos, _ = _preparar(datos["contratos"])
    filas = [
        {
            "nit_entidad": nit,
            "entidad": _nombre(grupo),
            "valor_contratado": _numero(_suma(grupo["_valor"])),
            "numero_contratos": int(grupo["id_contrato"].nunique()),
        }
        for nit, grupo in contratos.groupby("_nit", sort=False)
    ]
    filas.sort(key=lambda f: (-f["valor_contratado"], f["nit_entidad"]))
    return filas


def diagnostico(datos: dict) -> dict:
    """Comprobaciones que sustentan las advertencias del resultado."""
    contratos, notas = _preparar(datos["contratos"])
    unidades = (
        contratos.groupby(["_nit", "nombre_entidad"])
        .agg(contratos=("id_contrato", "size"), valor=("_valor", lambda s: _numero(_suma(s))))
        .reset_index()
    )
    salida = {
        **notas,
        "valor_total": _numero(_suma(contratos["_valor"])),
        "entidades": int(contratos["_nit"].nunique()),
        "nits_con_varios_nombres": unidades[unidades.duplicated("_nit", keep=False)].to_dict("records"),
        "valor_cero": int((contratos["_valor"] == 0).sum()),
        "valor_un_peso": int((contratos["_valor"] == 1).sum()),
    }
    claves = ["_nit", "referencia_del_contrato", "proceso_de_compra", "valor_del_contrato"]
    if all(c in contratos.columns for c in claves):
        copias = contratos[contratos.duplicated(claves, keep="first")]
        salida["posibles_registros_dobles"] = {"contratos": int(len(copias)), "valor": _numero(_suma(copias["_valor"]))}
    if "tipo_de_contrato" in contratos.columns:
        credito = contratos[contratos["tipo_de_contrato"].map(_clave) == "operaciones de credito publico"]
        salida["operaciones_de_credito_publico"] = (
            credito.groupby("_nit")
            .agg(contratos=("id_contrato", "size"), valor=("_valor", lambda s: _numero(_suma(s))))
            .reset_index()
            .to_dict("records")
        )
    return salida


if __name__ == "__main__":
    entrada = {"contratos": sys.argv[1] if len(sys.argv) > 1 else "contratos.csv"}
    print(json.dumps(analizar(entrada), ensure_ascii=False, indent=1))
    print(json.dumps(diagnostico(entrada), ensure_ascii=False, indent=1, default=str), file=sys.stderr)

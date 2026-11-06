"""Generador A · etapa 2 (Procesamiento) · corrida 2026-11-06-pipeline-secop-medellin-2025.

Petición: valor contratado en 2025 por cada entidad pública con sede en Medellín,
según SECOP II. Para cada entidad: nit_entidad, entidad, valor_contratado y
numero_contratos.

Sigue spec.json al pie de la letra:
- Una fila por nit_entidad, leído como texto, sin espacios al inicio y al final y
  sin convertirlo a número (S1). Nunca se agrupa por codigo_entidad ni por nombre.
- Cada id_contrato (sin espacios al inicio y al final, en mayúsculas) cuenta una
  sola vez: vale la primera aparición en el orden del archivo y los repetidos se
  quitan ANTES de mirar la fecha (S6). Nunca se depura por (entidad, valor, fecha) (L08).
- «Contratado en 2025»: fecha_de_firma del 2025-01-01 al 2025-12-31, los dos días
  completos, leída por formato: si empieza por aaaa-mm-dd se usan sus 10 primeros
  caracteres; si empieza por dd/mm/aaaa, el año son los caracteres 7 a 10. Ni
  format='mixed' con dayfirst (L01) ni el texto con hora contra '2025-12-31' (L02).
- valor_del_contrato a número decimal con punto, sumado tal como figura (sin topes,
  sin corrección y sin redondeo); vacío = 0 y el contrato cuenta (S3); los ceros
  cuentan en numero_contratos y suman 0.
- entidad: el nombre_entidad con más contratos que cuentan dentro del NIT; en
  empate, min() de los empatados (S2). Se muestra tal como viene, solo sin espacios
  al inicio y al final (S4).
- No se filtra por ciudad, estado ni naturaleza de la entidad (S5, S7).

Limpiar es marcar: lo que se normaliza o se toma como 0 se cuenta en «marcadas» de
conciliar(); nada se borra en silencio.

Función pura: solo lee la tabla que recibe; no escribe, no usa red, no ejecuta nada.
"""

import math

import pandas as pd

TABLA = "contratos"
COL_ID = "id_contrato"
COL_NIT = "nit_entidad"
COL_NOMBRE = "nombre_entidad"
COL_FECHA = "fecha_de_firma"
COL_VALOR = "valor_del_contrato"
COLUMNAS = (COL_ID, COL_NIT, COL_NOMBRE, COL_FECHA, COL_VALOR)

# Año de la petición (es la pregunta, no un dato).
ANIO = "2025"
DESDE = ANIO + "-01-01"
HASTA = ANIO + "-12-31"

# Formatos de fecha de la spec: «empieza por» (str.match se ancla al inicio).
FORMATO_ISO = r"[0-9]{4}-[0-9]{2}-[0-9]{2}"  # aaaa-mm-dd, con o sin «T» y hora
FORMATO_DMA = r"[0-9]{2}/[0-9]{2}/[0-9]{4}"  # dd/mm/aaaa, día primero, con o sin hora
SOLO_DIGITOS = r"[0-9]+"
CONTROL = r"[\x00-\x1f\x7f-\x9f]"  # caracteres de control C0 y C1 (p. ej. U+0096)

# Umbrales de los hallazgos de la spec: solo marcan; nunca excluyen ni corrigen.
SIMBOLICO = 10.0  # 0 < valor < 10 pesos
ALTO = 100_000_000_000.0  # valor > 100.000 millones (ver P3)

USADA = "usada"
EXCLUSIONES = ("repetido_id_contrato", "sin_fecha_de_firma", "fuera_de_2025")
MARCAS = (
    "id_contrato_con_espacios_o_minusculas",
    "id_contrato_vacio",
    "nit_con_espacios",
    "nit_vacio",
    "nit_con_caracteres_que_no_son_digitos",
    "nombre_con_espacios",
    "nombre_vacio",
    "nombre_con_caracteres_de_control",
    "nombre_distinto_al_mostrado",
    "fecha_con_espacios",
    "fecha_dd_mm_aaaa",
    "valor_vacio_tomado_como_cero",
    "valor_no_numerico_tomado_como_cero",
    "valor_negativo",
    "valor_cero",
    "valor_mayor_que_0_y_menor_que_10",
    "valor_mayor_que_100_mil_millones",
)


def _leer(fuente) -> pd.DataFrame:
    """La tabla como DataFrame nuevo: nunca se modifica lo que llega."""
    if isinstance(fuente, pd.DataFrame):
        return fuente.copy()
    # Ruta o archivo: todo como texto, sin volver nulos los vacíos ni «NA».
    return pd.read_csv(fuente, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def _tabla(datos) -> pd.DataFrame:
    """Saca la tabla de contratos de `datos`.

    Acepta {"contratos": ruta o DataFrame} (la forma de spec.json), un dict con una
    sola tabla, un DataFrame o una ruta.
    """
    if isinstance(datos, dict) and TABLA not in datos and "datos" in datos and isinstance(datos["datos"], dict):
        datos = datos["datos"]
    if isinstance(datos, dict):
        if TABLA in datos:
            fuente = datos[TABLA]
        elif len(datos) == 1:
            fuente = next(iter(datos.values()))
        else:
            raise KeyError(f"datos no trae la tabla «{TABLA}»; trae {sorted(str(k) for k in datos)}")
    else:
        fuente = datos
    if isinstance(fuente, dict) and "ruta" in fuente:
        fuente = fuente["ruta"]
    df = _leer(fuente)
    df.columns = [str(c).replace("﻿", "").strip() for c in df.columns]
    faltan = [c for c in COLUMNAS if c not in df.columns]
    if faltan:
        raise KeyError(f"a la tabla «{TABLA}» le faltan columnas: {faltan}")
    return df.reset_index(drop=True)


def _un_texto(valor) -> str:
    """Un valor como texto tal como viene; nulo -> ''; 890900286.0 -> '890900286'."""
    if isinstance(valor, str):
        return valor
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        return str(valor)
    if isinstance(valor, pd.Timestamp):
        return valor.strftime("%Y-%m-%dT%H:%M:%S")
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor)


def _texto(serie: pd.Series) -> pd.Series:
    """Columna como texto sin recortar (sirve también si la tabla llega ya tipada)."""
    if isinstance(serie.dtype, pd.CategoricalDtype):
        serie = serie.astype(object)
    if pd.api.types.is_datetime64_any_dtype(serie):
        serie = serie.dt.strftime("%Y-%m-%dT%H:%M:%S")
    return serie.map(_un_texto).astype(str)


def _nombre_por_nit(usadas: pd.DataFrame) -> dict:
    """Para cada NIT, el nombre con más contratos que cuentan; empate: min() (S2).

    Un nombre vacío solo se muestra si el NIT no tiene ningún nombre con texto.
    """
    conteo = usadas.groupby(["nit", "nombre"], sort=False).size()
    candidatos: dict = {}
    for (nit, nombre), n in conteo.items():
        candidatos.setdefault(nit, []).append((nombre, int(n)))
    elegido = {}
    for nit, pares in candidatos.items():
        pares = [p for p in pares if p[0] != ""] or pares
        mas = max(n for _, n in pares)
        elegido[nit] = min(nombre for nombre, n in pares if n == mas)
    return elegido


def _preparar(datos):
    """Una fila por fila leída, con su lectura normalizada, su destino y sus marcas."""
    df = _tabla(datos)

    id_crudo = _texto(df[COL_ID])
    nit_crudo = _texto(df[COL_NIT])
    nombre_crudo = _texto(df[COL_NOMBRE])
    fecha_cruda = _texto(df[COL_FECHA])
    valor_crudo = _texto(df[COL_VALOR])

    id_norm = id_crudo.str.strip().str.upper()
    nit = nit_crudo.str.strip()
    nombre = nombre_crudo.str.strip()
    fecha = fecha_cruda.str.strip()
    valor_txt = valor_crudo.str.strip()

    # 1) Contrato: primera aparición del id normalizado, en el orden del archivo (S6).
    repetido = id_norm.duplicated(keep="first")

    # 2) Fecha por formato, cada uno por separado (L01, L02).
    es_iso = fecha.str.match(FORMATO_ISO)
    es_dma = fecha.str.match(FORMATO_DMA) & ~es_iso
    con_fecha = es_iso | es_dma
    dia_iso = fecha.str.slice(0, 10)
    anio_dma = fecha.str.slice(6, 10)
    en_anio = (es_iso & dia_iso.ge(DESDE) & dia_iso.le(HASTA)) | (es_dma & anio_dma.eq(ANIO))

    # 3) Valor: decimal con punto; vacío o ilegible suman 0 y se marcan.
    vacio = valor_txt.eq("")
    numero = pd.to_numeric(valor_txt.where(~vacio), errors="coerce").astype(float)
    finito = numero.notna() & numero.abs().ne(math.inf)
    valor = numero.where(finito, 0.0)

    # Destino: un solo motivo por fila, con la prioridad de la spec.
    destino = pd.Series(USADA, index=df.index, dtype=object)
    destino.loc[~repetido & con_fecha & ~en_anio] = "fuera_de_2025"
    destino.loc[~repetido & ~con_fecha] = "sin_fecha_de_firma"
    destino.loc[repetido] = "repetido_id_contrato"

    filas = pd.DataFrame(
        {
            "nit": nit,
            "nombre": nombre,
            "valor": valor,
            "destino": destino,
            "id_contrato_con_espacios_o_minusculas": id_crudo.ne(id_norm),
            "id_contrato_vacio": id_norm.eq(""),
            "nit_con_espacios": nit_crudo.ne(nit),
            "nit_vacio": nit.eq(""),
            "nit_con_caracteres_que_no_son_digitos": nit.ne("") & ~nit.str.fullmatch(SOLO_DIGITOS),
            "nombre_con_espacios": nombre_crudo.ne(nombre),
            "nombre_vacio": nombre.eq(""),
            "nombre_con_caracteres_de_control": nombre.str.contains(CONTROL, regex=True),
            "fecha_con_espacios": fecha_cruda.ne(fecha),
            "fecha_dd_mm_aaaa": es_dma,
            "valor_vacio_tomado_como_cero": vacio,
            "valor_no_numerico_tomado_como_cero": ~vacio & ~finito,
            "valor_negativo": valor.lt(0),
            "valor_cero": ~vacio & finito & valor.eq(0),
            "valor_mayor_que_0_y_menor_que_10": valor.gt(0) & valor.lt(SIMBOLICO),
            "valor_mayor_que_100_mil_millones": valor.gt(ALTO),
        }
    )
    usada = filas["destino"].eq(USADA)
    nombres = _nombre_por_nit(filas.loc[usada, ["nit", "nombre"]])
    mostrado = filas["nit"].map(nombres)
    filas["nombre_distinto_al_mostrado"] = usada & filas["nombre"].ne(mostrado)
    return filas, nombres


def _orden(fila: dict):
    """valor_contratado de mayor a menor; en empate, nit_entidad ascendente como texto."""
    return (-fila["valor_contratado"], fila["nit_entidad"])


def analizar(datos) -> list[dict]:
    """Una fila por nit_entidad con al menos un contrato que cuenta.

    Claves: nit_entidad (str), entidad (str), valor_contratado (float, sin
    redondear) y numero_contratos (int), ordenadas según la spec.
    """
    filas, nombres = _preparar(datos)
    usadas = filas[filas["destino"].eq(USADA)]
    grupos = usadas.groupby("nit", sort=False)["valor"]
    valor = grupos.agg(math.fsum)
    cuantos = grupos.size()
    resultado = [
        {
            "nit_entidad": str(nit),
            "entidad": str(nombres[nit]),
            "valor_contratado": float(valor[nit]),
            "numero_contratos": int(cuantos[nit]),
        }
        for nit in valor.index
    ]
    resultado.sort(key=_orden)
    return resultado


def conciliar(datos) -> dict:
    """Cuenta el destino de cada fila leída.

    filas_leidas = usadas + suma de excluidas; cada fila excluida va a un solo
    motivo (repetido_id_contrato, sin_fecha_de_firma, fuera_de_2025, en ese orden de
    prioridad). «marcadas» cuenta filas usadas con algo que avisar; una fila puede
    tener varias marcas, así que las marcas no suman a «usadas».
    """
    filas, _ = _preparar(datos)
    usada = filas["destino"].eq(USADA)
    leidas = int(len(filas))
    n_usadas = int(usada.sum())
    excluidas = {m: int(filas["destino"].eq(m).sum()) for m in EXCLUSIONES}
    marcadas = {m: int((filas[m] & usada).sum()) for m in MARCAS}
    if leidas != n_usadas + sum(excluidas.values()):
        raise ValueError(
            f"conciliación rota: {leidas} leídas != {n_usadas} usadas + {sum(excluidas.values())} excluidas"
        )
    return {"filas_leidas": leidas, "usadas": n_usadas, "excluidas": excluidas, "marcadas": marcadas}

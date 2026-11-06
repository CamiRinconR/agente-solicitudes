from reglas_base import regla, leer_csv, aprox, suma

import datetime
import math

INICIO = datetime.date(2026, 1, 1)
FIN = datetime.date(2026, 6, 30)
OFICIALES = ["Antioquia", "Bogotá D.C.", "Caldas", "Risaralda", "Valle del Cauca"]
SIN_REGION = "Sin región"
ETIQUETAS = OFICIALES + [SIN_REGION]


# ---- tratamientos puntuales (no unen tablas ni agrupan por región) ----
def _fecha(texto):
    """aaaa-mm-dd o dd/mm/aaaa (día primero, demostrado por el perfil)."""
    s = (texto or "").strip()
    try:
        if "/" in s:
            d, m, a = s.split("/")
            return datetime.date(int(a), int(m), int(d))
        return datetime.date.fromisoformat(s)
    except ValueError:
        return None


def _codigo(texto):
    return (texto or "").strip().upper()


def _documentos_del_periodo(ruta_ventas):
    """Documentos FV/NC del semestre, cada numero_documento una sola vez (el primero)."""
    vistos, docs = set(), []
    for f in leer_csv(ruta_ventas):
        num = (f.get("numero_documento") or "").strip().upper()
        if num in vistos:
            continue
        vistos.add(num)
        tipo = (f.get("tipo_documento") or "").strip().upper()
        if tipo not in ("FV", "NC"):
            continue
        fecha = _fecha(f.get("fecha"))
        if fecha is None or not (INICIO <= fecha <= FIN):
            continue
        valor = float(f.get("subtotal") or 0)
        docs.append({"cliente": _codigo(f.get("cliente_id")), "neto": valor if tipo == "FV" else -valor,
                     "tipo": tipo})
    return docs


def _valor(resultado, etiqueta):
    filas = [f for f in resultado if str(f.get("region", "")).strip() == etiqueta]
    if len(filas) != 1:
        return None
    try:
        return float(filas[0].get("ventas_netas"))
    except (TypeError, ValueError):
        return None


@regla("R1", "conservacion",
       "La suma de ventas_netas de todas las filas es igual a las ventas netas del semestre calculadas "
       "directo de ventas (FV menos NC sobre subtotal, cada documento una vez, fechas dd/mm/aaaa o aaaa-mm-dd), "
       "sin unir con clientes")
def r1(datos, resultado):
    docs = _documentos_del_periodo(datos["ventas"])
    fuente = sum(d["neto"] for d in docs)
    total = suma(resultado, "ventas_netas")
    return aprox(total, fuente), (f"resultado {total:,.0f} · fuente {fuente:,.0f} "
                                  f"({len(docs)} documentos del semestre)")


@regla("R2", "cobertura",
       "La fila «Sin región» vale exactamente las ventas netas del semestre de los documentos sin cliente_id "
       "o con un cliente_id que, tras quitar espacios y pasar a mayúsculas, no está en el maestro de clientes")
def r2(datos, resultado):
    maestro = {_codigo(f.get("cliente_id")) for f in leer_csv(datos["clientes"])}
    maestro.discard("")
    docs = [d for d in _documentos_del_periodo(datos["ventas"]) if d["cliente"] == "" or d["cliente"] not in maestro]
    fuente = sum(d["neto"] for d in docs)
    obtenido = _valor(resultado, SIN_REGION)
    if obtenido is None:
        return False, f"no hay exactamente una fila «{SIN_REGION}» con valor numérico; fuente {fuente:,.0f}"
    return aprox(obtenido, fuente), (f"«{SIN_REGION}» en el resultado {obtenido:,.0f} · fuente {fuente:,.0f} "
                                     f"({len(docs)} documentos sin cliente identificado)")


@regla("R3", "unicidad", "Cada región aparece una sola vez en el resultado (ninguna fila repetida)")
def r3(datos, resultado):
    etiquetas = [str(f.get("region", "")).strip() for f in resultado]
    repetidas = sorted({e for e in etiquetas if etiquetas.count(e) > 1})
    return not repetidas, f"{len(etiquetas)} filas, {len(set(etiquetas))} regiones distintas; repetidas: {repetidas or 'ninguna'}"


@regla("R4", "dominio",
       "El resultado tiene exactamente seis filas, una por cada etiqueta de la lista cerrada (Antioquia, "
       "Bogotá D.C., Caldas, Risaralda, Valle del Cauca, Sin región), escritas tal cual, aunque valgan 0; "
       "ninguna región queda partida por variantes de escritura")
def r4(datos, resultado):
    etiquetas = {str(f.get("region", "")).strip() for f in resultado}
    sobran = sorted(etiquetas - set(ETIQUETAS))
    faltan = [e for e in ETIQUETAS if e not in etiquetas]
    ok = not sobran and not faltan and len(resultado) == len(ETIQUETAS)
    return ok, f"{len(resultado)} filas de 6; faltan: {faltan or 'ninguna'}; fuera de la lista: {sobran or 'ninguna'}"


@regla("R5", "completitud",
       "Las cinco regiones oficiales juntas valen las ventas netas del semestre de los documentos cuyo cliente "
       "está en el maestro (lo identificado no se pierde ni se va a «Sin región»)")
def r5(datos, resultado):
    maestro = {_codigo(f.get("cliente_id")) for f in leer_csv(datos["clientes"])}
    maestro.discard("")
    docs = [d for d in _documentos_del_periodo(datos["ventas"]) if d["cliente"] != "" and d["cliente"] in maestro]
    fuente = sum(d["neto"] for d in docs)
    valores = [_valor(resultado, e) for e in OFICIALES]
    if any(v is None for v in valores):
        return False, f"falta alguna región oficial con valor numérico; fuente {fuente:,.0f}"
    obtenido = sum(valores)
    return aprox(obtenido, fuente), (f"regiones oficiales en el resultado {obtenido:,.0f} · fuente {fuente:,.0f} "
                                     f"({len(docs)} documentos con cliente identificado)")


@regla("R6", "rango",
       "Cada ventas_netas es un número finito y ninguna fila supera en valor absoluto la suma del subtotal de "
       "todas las FV del semestre (cota bruta); el IVA no entra")
def r6(datos, resultado):
    docs = _documentos_del_periodo(datos["ventas"])
    cota = sum(d["neto"] for d in docs if d["tipo"] == "FV")
    malos = []
    for f in resultado:
        try:
            v = float(f.get("ventas_netas"))
        except (TypeError, ValueError):
            malos.append(f"{f.get('region')}: {f.get('ventas_netas')!r}")
            continue
        if not math.isfinite(v) or abs(v) > cota + 0.5:
            malos.append(f"{f.get('region')}: {v:,.0f}")
    return not malos, f"cota bruta FV del semestre {cota:,.0f}; filas fuera de rango: {malos or 'ninguna'}"


@regla("R7", "orden",
       "Las filas salen en el orden de la spec: las cinco regiones oficiales de mayor a menor ventas_netas "
       "(los empates, en cualquier orden) y «Sin región» de última")
def r7(datos, resultado):
    etiquetas = [str(f.get("region", "")).strip() for f in resultado]
    if not etiquetas or etiquetas[-1] != SIN_REGION:
        return False, f"la última fila es {etiquetas[-1] if etiquetas else 'ninguna'!r}, no «{SIN_REGION}»"
    valores = []
    for f in resultado[:-1]:
        try:
            valores.append(float(f.get("ventas_netas")))
        except (TypeError, ValueError):
            return False, f"{f.get('region')}: ventas_netas no numérico"
    desordenadas = [f"{etiquetas[i]} < {etiquetas[i + 1]}" for i in range(len(valores) - 1)
                    if valores[i] < valores[i + 1] - 0.5]
    return not desordenadas, (f"orden: {etiquetas}; pares fuera de orden: {desordenadas or 'ninguno'}")

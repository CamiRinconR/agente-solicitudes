from reglas_base import regla, leer_csv, aprox, suma

import unicodedata
from collections import Counter, defaultdict


def _sin_tildes(t):
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def _es_medellin(ciudad):
    return _sin_tildes((ciudad or "").strip().casefold()) == "medellin"


def _en_2025(fecha):
    d = (fecha or "").strip()[:10]
    return "2025-01-01" <= d <= "2025-12-31"


def _valor(t):
    t = (t or "").strip()
    return float(t) if t else 0.0


def _contratos_2025(datos):
    """Contratos únicos por id_contrato (primera aparición), firmados en 2025, ciudad Medellín."""
    vistos, filas = set(), []
    for f in leer_csv(datos["contratos"]):
        k = (f.get("id_contrato") or "").strip().upper()
        if k in vistos:
            continue
        vistos.add(k)
        if _en_2025(f.get("fecha_de_firma")) and _es_medellin(f.get("ciudad")):
            filas.append(f)
    return filas


def _nit(v):
    return str(v if v is not None else "").strip()


@regla("R1", "conservacion",
       "La suma de valor_contratado del resultado es igual a la suma de valor_del_contrato de los contratos "
       "únicos firmados en 2025 en Medellín, calculada directo de la fuente")
def r1(datos, resultado):
    fuente = sum(_valor(f.get("valor_del_contrato")) for f in _contratos_2025(datos))
    res = suma(resultado, "valor_contratado")
    return aprox(res, fuente), f"resultado {res:,.2f} · fuente {fuente:,.2f}"


@regla("R2", "conservacion",
       "La suma de numero_contratos del resultado es igual al número de id_contrato distintos firmados en "
       "2025 en Medellín (los de valor cero incluidos)")
def r2(datos, resultado):
    fuente = len(_contratos_2025(datos))
    res = suma(resultado, "numero_contratos")
    return aprox(res, fuente), f"resultado {res:,.0f} · fuente {fuente:,} contratos"


@regla("R3", "unicidad", "Cada nit_entidad aparece una sola vez en el resultado")
def r3(datos, resultado):
    c = Counter(_nit(f.get("nit_entidad")) for f in resultado)
    rep = sorted(k for k, n in c.items() if n > 1)
    return not rep, f"{len(resultado)} filas · {len(c)} NIT distintos · repetidos: {rep[:5]}"


@regla("R4", "completitud",
       "Los NIT del resultado son exactamente los que tienen al menos un contrato firmado en 2025 en Medellín: "
       "no falta ninguno ni sobra ninguno (ni entidades sin contratos en 2025)")
def r4(datos, resultado):
    fuente = {_nit(f.get("nit_entidad")) for f in _contratos_2025(datos)}
    res = {_nit(f.get("nit_entidad")) for f in resultado}
    faltan, sobran = sorted(fuente - res), sorted(res - fuente)
    return not faltan and not sobran, (f"fuente {len(fuente)} NIT · resultado {len(res)} NIT · "
                                       f"faltan {faltan[:5]} · sobran {sobran[:5]}")


@regla("R5", "dominio",
       "numero_contratos es un entero mayor o igual a 1, valor_contratado es mayor o igual a 0 y no supera "
       "el total de la fuente, y nit_entidad son solo dígitos")
def r5(datos, resultado):
    total = sum(_valor(f.get("valor_del_contrato")) for f in _contratos_2025(datos))
    malas = []
    for f in resultado:
        n, v, nit = f.get("numero_contratos"), f.get("valor_contratado"), _nit(f.get("nit_entidad"))
        try:
            n_ok = float(n).is_integer() and float(n) >= 1
            v_ok = float(v) >= -0.5 and float(v) <= total + 0.5
        except (TypeError, ValueError):
            n_ok = v_ok = False
        if not (n_ok and v_ok and nit.isdigit()):
            malas.append((nit, n, v))
    return not malas, f"{len(resultado)} filas · fuera de dominio {len(malas)}: {malas[:5]} · total fuente {total:,.2f}"


@regla("R6", "otra",
       "entidad es el nombre_entidad (sin espacios al inicio ni al final) que más contratos únicos de 2025 "
       "tiene dentro de su NIT; si hay empate, el primero en orden alfabético")
def r6(datos, resultado):
    nombres = defaultdict(Counter)
    for f in _contratos_2025(datos):
        nombres[_nit(f.get("nit_entidad"))][(f.get("nombre_entidad") or "").strip()] += 1
    malos = []
    for f in resultado:
        nit = _nit(f.get("nit_entidad"))
        c = nombres.get(nit)
        if not c:
            malos.append((nit, f.get("entidad"), None))
            continue
        tope = max(c.values())
        esperado = sorted(n for n, k in c.items() if k == tope)[0]
        if str(f.get("entidad") or "").strip() != esperado:
            malos.append((nit, f.get("entidad"), esperado))
    con_varios = sum(1 for c in nombres.values() if len(c) > 1)
    return not malos, (f"{len(resultado)} filas · {con_varios} NIT con más de un nombre · "
                       f"nombre distinto al esperado {len(malos)}: {malos[:5]}")


@regla("R7", "otra",
       "El resultado viene ordenado por valor_contratado de mayor a menor y, en empate, por nit_entidad ascendente")
def r7(datos, resultado):
    llaves = [(-float(f["valor_contratado"]), _nit(f.get("nit_entidad"))) for f in resultado]
    malos = [i for i in range(1, len(llaves)) if llaves[i] < llaves[i - 1]]
    return not malos, f"{len(resultado)} filas · filas fuera de orden: {malos[:5]}"


@regla("R8", "conservacion",
       "Para cada nit_entidad del resultado, valor_contratado y numero_contratos son iguales a la suma de "
       "valor_del_contrato y al número de id_contrato distintos de ese NIT firmados en 2025 en Medellín, "
       "calculados directo de la fuente")
def r8(datos, resultado):
    val, num = defaultdict(float), Counter()
    for f in _contratos_2025(datos):
        nit = _nit(f.get("nit_entidad"))
        val[nit] += _valor(f.get("valor_del_contrato"))
        num[nit] += 1
    malos = []
    for f in resultado:
        nit = _nit(f.get("nit_entidad"))
        try:
            v, n = float(f.get("valor_contratado")), float(f.get("numero_contratos"))
        except (TypeError, ValueError):
            malos.append((nit, f.get("valor_contratado"), f.get("numero_contratos")))
            continue
        if not (aprox(v, val.get(nit, 0.0)) and aprox(n, num.get(nit, 0))):
            malos.append((nit, (v, val.get(nit, 0.0)), (n, num.get(nit, 0))))
    return not malos, (f"{len(resultado)} filas · NIT con valor o número distinto al de la fuente "
                       f"{len(malos)}: {malos[:5]}")

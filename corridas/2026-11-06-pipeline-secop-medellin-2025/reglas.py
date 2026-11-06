from reglas_base import regla, leer_csv, aprox, suma

import re
from collections import Counter, defaultdict

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}")
_BARRAS = re.compile(r"^\d{2}/\d{2}/\d{4}")


def _en_2025(fecha):
    """True/False según el año de firma; None si la fecha está vacía o no tiene formato conocido."""
    t = (fecha or "").strip()
    if _ISO.match(t):
        return "2025-01-01" <= t[:10] <= "2025-12-31"
    if _BARRAS.match(t):
        return t[6:10] == "2025"
    return None


def _valor(t):
    t = (t or "").strip()
    return float(t) if t else 0.0


def _nit(v):
    return str(v if v is not None else "").strip()


def _contratos_2025(datos):
    """Contratos únicos por id_contrato (sin espacios, en mayúsculas; primera aparición), firmados en 2025."""
    vistos, filas = set(), []
    for f in leer_csv(datos["contratos"]):
        k = (f.get("id_contrato") or "").strip().upper()
        if k in vistos:
            continue
        vistos.add(k)
        if _en_2025(f.get("fecha_de_firma")) is True:
            filas.append(f)
    return filas


@regla("R1", "conservacion",
       "La suma de valor_contratado del resultado es igual a la suma de valor_del_contrato de los contratos "
       "únicos firmados en 2025, calculada directo de la fuente")
def r1(datos, resultado):
    fuente = sum(_valor(f.get("valor_del_contrato")) for f in _contratos_2025(datos))
    res = suma(resultado, "valor_contratado")
    return aprox(res, fuente), f"resultado {res:,.2f} · fuente {fuente:,.2f}"


@regla("R2", "conservacion",
       "La suma de numero_contratos del resultado es igual al número de id_contrato distintos firmados en "
       "2025 (los de valor cero incluidos)")
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
       "Los NIT del resultado son exactamente los que tienen al menos un contrato firmado en 2025: "
       "no falta ninguno ni sobra ninguno")
def r4(datos, resultado):
    fuente = {_nit(f.get("nit_entidad")) for f in _contratos_2025(datos)}
    res = {_nit(f.get("nit_entidad")) for f in resultado}
    faltan, sobran = sorted(fuente - res), sorted(res - fuente)
    return not faltan and not sobran, (f"fuente {len(fuente)} NIT · resultado {len(res)} NIT · "
                                       f"faltan {faltan[:5]} · sobran {sobran[:5]}")


@regla("R5", "dominio",
       "numero_contratos es un entero >= 1, valor_contratado es >= 0 y no supera el total de la fuente, "
       "nit_entidad son solo dígitos sin espacios y entidad no está vacía")
def r5(datos, resultado):
    total = sum(_valor(f.get("valor_del_contrato")) for f in _contratos_2025(datos))
    malas = []
    for f in resultado:
        n, v = f.get("numero_contratos"), f.get("valor_contratado")
        nit, ent = str(f.get("nit_entidad") if f.get("nit_entidad") is not None else ""), f.get("entidad")
        try:
            n_ok = float(n).is_integer() and float(n) >= 1
            v_ok = -0.5 <= float(v) <= total + 0.5
        except (TypeError, ValueError):
            n_ok = v_ok = False
        nit_ok = nit.isdigit() and nit == nit.strip()
        ent_ok = isinstance(ent, str) and ent.strip() != ""
        if not (n_ok and v_ok and nit_ok and ent_ok):
            malas.append((nit, n, v, ent_ok))
    return not malas, (f"{len(resultado)} filas · fuera de dominio {len(malas)}: {malas[:5]} · "
                       f"total fuente {total:,.2f}")


@regla("R6", "otra",
       "entidad es el nombre_entidad (sin espacios al inicio ni al final) con más contratos únicos de 2025 "
       "dentro de su NIT; en empate, el menor en orden de texto")
def r6(datos, resultado):
    nombres = defaultdict(Counter)
    for f in _contratos_2025(datos):
        nombres[_nit(f.get("nit_entidad"))][(f.get("nombre_entidad") or "").strip()] += 1
    malos = []
    for f in resultado:
        nit = _nit(f.get("nit_entidad"))
        c = nombres.get(nit)
        if not c:
            malos.append((nit, None))
            continue
        tope = max(c.values())
        esperado = min(n for n, k in c.items() if k == tope)
        if str(f.get("entidad") or "").strip() != esperado:
            malos.append((nit, "nombre distinto"))
    con_varios = sum(1 for c in nombres.values() if len(c) > 1)
    return not malos, (f"{len(resultado)} filas · {con_varios} NIT con más de un nombre · "
                       f"nombre distinto al esperado {len(malos)}: {malos[:5]}")


@regla("R7", "otra",
       "El resultado viene ordenado por valor_contratado de mayor a menor y, en empate, por nit_entidad "
       "ascendente como texto")
def r7(datos, resultado):
    llaves = [(-float(f["valor_contratado"]), _nit(f.get("nit_entidad"))) for f in resultado]
    malos = [i for i in range(1, len(llaves)) if llaves[i] < llaves[i - 1]]
    return not malos, f"{len(resultado)} filas · posiciones fuera de orden: {malos[:5]}"


@regla("R8", "conservacion",
       "Para cada nit_entidad del resultado, valor_contratado y numero_contratos son iguales a la suma de "
       "valor_del_contrato y al número de id_contrato distintos de ese NIT firmados en 2025, calculados "
       "directo de la fuente")
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


_CLAVES = {"nit_entidad", "entidad", "valor_contratado", "numero_contratos"}


def _tipos_ok(f):
    v, n = f.get("valor_contratado"), f.get("numero_contratos")
    return (isinstance(f.get("nit_entidad"), str) and isinstance(f.get("entidad"), str)
            and isinstance(v, (int, float)) and not isinstance(v, bool)
            and isinstance(n, int) and not isinstance(n, bool))


@regla("R9", "dominio",
       "Cada fila del resultado tiene exactamente las claves nit_entidad, entidad, valor_contratado y "
       "numero_contratos, con sus tipos (nit_entidad y entidad texto, valor_contratado número, "
       "numero_contratos entero), y el resultado no viene vacío")
def r9(datos, resultado):
    malas = [(i, sorted(set(f) ^ _CLAVES)) for i, f in enumerate(resultado) if set(f) != _CLAVES]
    tipos = [(i, {k: type(f.get(k)).__name__ for k in sorted(_CLAVES)})
             for i, f in enumerate(resultado) if set(f) == _CLAVES and not _tipos_ok(f)]
    return bool(resultado) and not malas and not tipos, (
        f"{len(resultado)} filas · con claves de más o de menos {len(malas)}: {malas[:5]} · "
        f"con tipo distinto {len(tipos)}: {tipos[:3]}")

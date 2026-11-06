"""Reglas de «valor contratado en 2025 por entidad con sede en Medellín (SECOP II)».

Leen el CSV CRUDO por su cuenta (solo biblioteca estándar) y no unen tablas. Sirven igual para los
datos reales y para el caso con respuesta conocida.

Aplican sobre el crudo la MISMA definición que spec.capa_limpia, escrita aquí por separado, para que
una implementación correcta sobre la capa limpia y estas reglas sobre el crudo digan lo mismo:
  - texto: U+0096 (raya «–» mal codificada de Windows-1252) se cambia por «–»; se quitan invisibles y
    controles, NFC, espacios repetidos a uno y recorte (nit_entidad, nombre_entidad, fecha, valor);
  - nulos disfrazados («No Definido», «N/A», «-», «0» en id y NIT…) cuentan como vacíos;
  - id_contrato recortado y sin distinguir mayúsculas; vale la primera aparición del archivo;
  - fecha en los formatos aceptados, leídos uno por uno (L01); la hora no importa (L02).
"""
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation

from reglas_base import regla, leer_csv, aprox, suma

TOL = 0.5
SIN_NOMBRE = "SIN NOMBRE"
_INVISIBLES = re.compile("[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f"
                         "\u200b-\u200f  \u202a-\u202e\u2060\ufeff]")
_FORMATOS = ["%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"]
_ISO_T = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")
_NULOS = ["No Definido", "No Aplica", "N/A", "NA", "Null", "None", "Sin dato", "-", "--"]


def _clave(s):
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^0-9a-z]", "", s.casefold())


_DISFRAZ = {_clave(x) for x in _NULOS}
_DISFRAZ_CON_CERO = _DISFRAZ | {_clave("0")}


def _texto(v):
    v = (v or "").replace("\u0096", "–")
    v = unicodedata.normalize("NFC", _INVISIBLES.sub("", v))
    return re.sub(r"\s+", " ", v).strip()


def _sin_disfraz(v, con_cero=False):
    """Vacío si el texto es un nulo disfrazado."""
    return "" if v and _clave(v) in (_DISFRAZ_CON_CERO if con_cero else _DISFRAZ) else v


def _anio(texto):
    """Año de la fecha de firma, o None si está vacía o no es una fecha real en un formato aceptado."""
    t = _sin_disfraz(_texto(texto))
    if not t:
        return None
    for f in _FORMATOS:
        try:
            return datetime.strptime(t, f).year
        except ValueError:
            continue
    if _ISO_T.match(t):
        try:
            return datetime.fromisoformat(t[:19]).year
        except ValueError:
            return None
    return None


def _valor(texto):
    t = _sin_disfraz(_texto(texto))
    if not t:
        return Decimal(0)
    try:
        v = Decimal(t)
    except InvalidOperation:
        return Decimal(0)
    return v if v.is_finite() else Decimal(0)


def _nombre(texto):
    return _sin_disfraz(_texto(texto))


def _que_cuentan(datos):
    """Contratos que cuentan: [(id, nit, nombre, valor)] en el orden del archivo."""
    vistos, out = set(), []
    for f in leer_csv(datos["contratos"]):
        idc = _sin_disfraz((f.get("id_contrato") or "").strip(), con_cero=True)
        if not idc:
            continue
        llave = idc.upper()
        if llave in vistos:
            continue
        vistos.add(llave)
        if _anio(f.get("fecha_de_firma")) != 2025:
            continue
        nit = _sin_disfraz(_texto(f.get("nit_entidad")), con_cero=True)
        if not nit:
            continue
        out.append((idc, nit, _nombre(f.get("nombre_entidad")), _valor(f.get("valor_del_contrato"))))
    return out


def _por_nit(datos):
    tot, n, nombres = defaultdict(Decimal), Counter(), defaultdict(Counter)
    for _, nit, nom, v in _que_cuentan(datos):
        tot[nit] += v
        n[nit] += 1
        if nom:
            nombres[nit][nom] += 1
    return tot, n, nombres


def _num(v):
    if isinstance(v, bool) or v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@regla("R1", "conservacion", "El total de valor_contratado es igual al total directo de la fuente cruda")
def r1(datos, resultado):
    fuente = float(sum(v for *_, v in _que_cuentan(datos)))
    res = suma(resultado, "valor_contratado")
    return aprox(res, fuente, TOL), f"resultado {res:,.2f} · fuente {fuente:,.2f}"


@regla("R2", "conservacion", "La suma de numero_contratos es igual a los id_contrato distintos que cuentan")
def r2(datos, resultado):
    fuente = len(_que_cuentan(datos))
    res = suma(resultado, "numero_contratos")
    return aprox(res, fuente, 0), f"resultado {res:,.0f} · fuente {fuente:,}"


@regla("R3", "cobertura", "Los NIT del resultado son exactamente los NIT con algún contrato que cuenta")
def r3(datos, resultado):
    fuente = {nit for _, nit, _, _ in _que_cuentan(datos)}
    res = {str(f.get("nit_entidad", "")).strip() for f in resultado}
    faltan, sobran = sorted(fuente - res), sorted(res - fuente)
    return not faltan and not sobran, (f"resultado {len(res)} NIT · fuente {len(fuente)} NIT · "
                                       f"faltan {len(faltan)} {faltan[:3]} · sobran {len(sobran)} {sobran[:3]}")


@regla("R4", "unicidad", "Cada nit_entidad aparece una sola vez y ninguno está vacío")
def r4(datos, resultado):
    nits = [str(f.get("nit_entidad", "") or "").strip() for f in resultado]
    rep = sorted(k for k, c in Counter(nits).items() if c > 1)
    vacios = sum(1 for n in nits if not n)
    return not rep and not vacios, f"filas {len(nits)} · NIT distintos {len(set(nits))} · repetidos {rep[:3]} · vacíos {vacios}"


@regla("R5", "dominio", "Tipos y dominios de las cuatro columnas de la salida")
def r5(datos, resultado):
    esperadas = {"nit_entidad", "entidad", "valor_contratado", "numero_contratos"}
    malas = Counter()
    for f in resultado:
        if set(f) != esperadas:
            malas["claves distintas de las cuatro"] += 1
        nit = f.get("nit_entidad")
        if not isinstance(nit, str) or not nit.strip().isdigit():
            malas["nit_entidad no es texto de dígitos"] += 1
        ent = f.get("entidad")
        if not isinstance(ent, str) or not ent.strip():
            malas["entidad vacía o no es texto"] += 1
        v = _num(f.get("valor_contratado"))
        if v is None or isinstance(f.get("valor_contratado"), str) or v < 0:
            malas["valor_contratado no es número >= 0"] += 1
        n = f.get("numero_contratos")
        if not isinstance(n, int) or isinstance(n, bool) or n < 1:
            malas["numero_contratos no es int >= 1"] += 1
    return not malas, f"filas {len(resultado)} · problemas {dict(malas) or 'ninguno'}"


@regla("R6", "cuadre_por_entidad", "valor_contratado y numero_contratos de cada NIT cuadran con la fuente cruda")
def r6(datos, resultado):
    tot, n, _ = _por_nit(datos)
    difs = []
    for f in resultado:
        nit = str(f.get("nit_entidad", "")).strip()
        v, c = _num(f.get("valor_contratado")), _num(f.get("numero_contratos"))
        if nit not in n:
            continue  # lo atrapa R3
        if v is None or abs(v - float(tot[nit])) > TOL or c is None or c != n[nit]:
            difs.append(f"{nit}: resultado {v} y {c} · fuente {float(tot[nit]):,.2f} y {n[nit]}")
    return not difs, f"NIT revisados {len(resultado)} · descuadrados {len(difs)} {difs[:3]}"


@regla("R7", "nombre_elegido", "entidad es el nombre más frecuente del NIT entre sus contratos que cuentan; empate al menor")
def r7(datos, resultado):
    _, n, nombres = _por_nit(datos)
    malos = []
    for f in resultado:
        nit = str(f.get("nit_entidad", "")).strip()
        if nit not in n:
            continue  # lo atrapa R3
        if nombres[nit]:
            maximo = max(nombres[nit].values())
            elegido = min(k for k, c in nombres[nit].items() if c == maximo)
        else:
            elegido = SIN_NOMBRE
        if f.get("entidad") != elegido:  # exacto: el nombre publicado ya va normalizado
            malos.append(nit)
    return not malos, f"NIT revisados {len(resultado)} · con otro nombre {len(malos)} {malos[:3]}"


@regla("R8", "orden", "Orden: valor_contratado descendente; en empate, nit_entidad ascendente como texto")
def r8(datos, resultado):
    for i in range(1, len(resultado)):
        a, b = resultado[i - 1], resultado[i]
        va, vb = _num(a.get("valor_contratado")) or 0.0, _num(b.get("valor_contratado")) or 0.0
        na, nb = str(a.get("nit_entidad", "")), str(b.get("nit_entidad", ""))
        if va < vb or (va == vb and na > nb):
            return False, f"fila {i - 1} ({na}, {va:,.2f}) va antes que fila {i} ({nb}, {vb:,.2f})"
    return True, f"{len(resultado)} filas en orden"

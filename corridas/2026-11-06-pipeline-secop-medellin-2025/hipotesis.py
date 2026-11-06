"""Pruebas de las hipótesis H1 a H5 (etapa 3 · Análisis, lado del probador).

Petición: valor contratado en 2025 por cada entidad pública con sede en Medellín, según SECOP II.
Todo se calcula directo desde datos["contratos"] (contratos.csv), sin usar el resultado aprobado,
impl_a/impl_b ni las bitácoras, y siguiendo al pie de la letra la «medida» sellada de cada hipótesis:

- Contratos que cuentan: se recorre el archivo en su orden; cada id_contrato (sin espacios al borde y
  en mayúsculas) cuenta una sola vez y vale su primera aparición; los repetidos se quitan ANTES de
  mirar la fecha; después quedan los firmados del 2025-01-01 al 2025-12-31, los dos días completos.
- fecha_de_firma se lee por formato, nunca con un lector «mixto» (lección L01): si empieza por
  aaaa-mm-dd, sus 10 primeros caracteres; si empieza por dd/mm/aaaa, con el día primero. Se compara
  el día y no el texto con la hora, para no perder el 31 de diciembre (lección L02).
- valor_del_contrato es un decimal con punto (vacío = 0) y se suma con Decimal, sin redondeos de float.
- El NIT es nit_entidad como texto, sin espacios al borde y sin convertirlo a número.

Función pura: solo lee el CSV que recibe; no escribe, no usa la red y no ejecuta nada.
"""
import re
from collections import defaultdict
from datetime import date
from decimal import Decimal

from reglas_base import hipotesis, leer_csv

INICIO, FIN = date(2025, 1, 1), date(2025, 12, 31)
FECHA_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")       # empieza por aaaa-mm-dd
FECHA_DMA = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")   # empieza por dd/mm/aaaa, día primero
NUMERO = re.compile(r"[+-]?(\d+(\.\d*)?|\.\d+)")         # decimal con punto, sin miles ni exponente
NIT_DISTRITO = "890905211"
GIGANTE = Decimal("100000000000")                        # 100.000 millones de pesos
VENTANA = (date(2025, 10, 8), date(2025, 11, 7))         # mes anterior a la restricción de la Ley 996
DIAS_VENTANA, DIAS_RESTO = 31, 334                       # los de la medida; se comprueban con el calendario
MINIMO_H5, LIMITE_H5 = 30, Decimal(10)


def _n(x, dec=0):
    """Cifra con punto de miles y coma decimal: 49.662 · 0,5123."""
    t = f"{x:,.{dec}f}"
    return t.replace(",", " ").replace(".", ",").replace(" ", ".")


def _pesos(x):
    x = Decimal(x)
    return _n(x, 0 if x == x.to_integral_value() else 2)


def _prop(x):
    return f"{_n(x, 4)} ({_n(100 * x, 2)} %)"


def _dia(texto):
    """Día de firma según el formato del texto; None si no se puede leer."""
    s = (texto or "").strip()
    m = FECHA_ISO.match(s)
    if m:
        anio, mes, dia = (int(g) for g in m.groups())
    else:
        m = FECHA_DMA.match(s)
        if not m:
            return None
        dia, mes, anio = (int(g) for g in m.groups())
    try:
        return date(anio, mes, dia)
    except ValueError:
        return None


def _valor(texto):
    """valor_del_contrato como decimal con punto; vacío = 0. Otra forma es un error, no un cero."""
    s = (texto or "").strip()
    if not s:
        return Decimal(0)
    if not NUMERO.fullmatch(s):
        raise ValueError(f"valor_del_contrato no es un decimal con punto (forma {re.sub(r'[0-9]', '9', s)!r})")
    return Decimal(s)


def _cuentan(datos):
    """Contratos que cuentan como [(nit, día, valor)] y una frase con lo que se quitó y por qué."""
    filas = leer_csv(datos["contratos"])
    vistos, cuentan = set(), []
    repetidos = sin_fecha = fuera = 0
    for f in filas:
        llave = (f.get("id_contrato") or "").strip().upper()
        if llave in vistos:                # el repetido se quita antes de mirar su fecha
            repetidos += 1
            continue
        vistos.add(llave)
        dia = _dia(f.get("fecha_de_firma"))
        if dia is None:
            sin_fecha += 1
            continue
        if not (INICIO <= dia <= FIN):
            fuera += 1
            continue
        cuentan.append(((f.get("nit_entidad") or "").strip(), dia, _valor(f.get("valor_del_contrato"))))
    filtro = (f"{_n(len(filas))} filas leídas; {_n(repetidos)} id_contrato repetidos quitados, "
              f"{_n(sin_fecha)} sin fecha legible y {_n(fuera)} fuera de 2025: cuentan {_n(len(cuentan))} contratos")
    return cuentan, filtro


@hipotesis("H1")
def h1(datos):
    cuentan, filtro = _cuentan(datos)
    n = len(cuentan)
    if not n:
        raise ValueError("no hay contratos que cuenten")
    k = -(-n // 100)                                   # ceil(0,01 × n) con enteros, sin error de float
    valores = sorted((v for _, _, v in cuentan), reverse=True)
    total = sum(valores, Decimal(0))
    if not total:
        raise ValueError("el valor total es 0: no hay proporción")
    arriba = sum(valores[:k], Decimal(0))              # un empate en el puesto k no cambia la suma
    valor, base = float(arriba / total), k / n
    return {"valor": valor, "linea_base": base,
            "detalle": (f"{filtro}. k = ceil(0,01 × {_n(n)}) = {_n(k)}. Los {_n(k)} contratos de mayor "
                        f"valor_del_contrato suman {_pesos(arriba)} de un total de {_pesos(total)}: {_prop(valor)}. "
                        f"Línea base (reparto uniforme) k / n = {_n(k)} / {_n(n)} = {_prop(base)}.")}


@hipotesis("H2")
def h2(datos):
    cuentan, filtro = _cuentan(datos)
    total, gigantes = [Decimal(0), Decimal(0)], [Decimal(0), Decimal(0)]
    cuantos, cuantos_gig = [0, 0], [0, 0]
    otros = set()
    for nit, _, v in cuentan:
        g = 0 if nit == NIT_DISTRITO else 1            # 0 = NIT 890905211; 1 = los demás NIT juntos
        if g:
            otros.add(nit)
        total[g] += v
        cuantos[g] += 1
        if v > GIGANTE:                                # estrictamente mayor que 100.000 millones
            gigantes[g] += v
            cuantos_gig[g] += 1
    if not total[0] or not total[1]:
        raise ValueError("el NIT 890905211 o los demás NIT suman 0: no hay proporción")
    valor, base = float(gigantes[0] / total[0]), float(gigantes[1] / total[1])
    peso = float(total[0] / (total[0] + total[1]))
    return {"valor": valor, "linea_base": base,
            "detalle": (f"{filtro}. NIT {NIT_DISTRITO}: {_n(cuantos[0])} contratos suman {_pesos(total[0])} "
                        f"({_n(100 * peso, 1)} % del valor de todos los NIT); {_n(cuantos_gig[0])} de más de "
                        f"100.000.000.000 suman {_pesos(gigantes[0])}: {_prop(valor)}. Línea base, los otros "
                        f"{_n(len(otros))} NIT juntos: {_n(cuantos[1])} contratos suman {_pesos(total[1])}; "
                        f"{_n(cuantos_gig[1])} de más de 100.000.000.000 suman {_pesos(gigantes[1])}: {_prop(base)}. "
                        f"En todos los NIT, {_n(sum(cuantos_gig))} contratos de más de 100.000.000.000 suman "
                        f"{_pesos(gigantes[0] + gigantes[1])}.")}


@hipotesis("H3")
def h3(datos):
    cuentan, filtro = _cuentan(datos)
    suma, mayor, cuantos = defaultdict(Decimal), {}, defaultdict(int)
    for nit, _, v in cuentan:
        suma[nit] += v
        cuantos[nit] += 1
        if nit not in mayor or v > mayor[nit]:
            mayor[nit] = v
    if sum(suma.values(), Decimal(0)) != sum((v for _, _, v in cuentan), Decimal(0)):
        raise ValueError("la suma por NIT no conserva el total")
    en_cero = [n for n in suma if suma[n] == 0]                       # suma 0: no se cuentan
    dominados = [n for n in suma if suma[n] != 0 and 2 * mayor[n] > suma[n]]   # mayor > 50 % de la suma
    de_uno = [n for n in cuantos if cuantos[n] == 1]
    dominados_uno = sum(cuantos[n] == 1 for n in dominados)
    return {"valor": len(dominados), "linea_base": len(de_uno),
            "detalle": (f"{filtro}. {_n(len(suma))} NIT tienen al menos un contrato que cuenta; {_n(len(en_cero))} "
                        f"suman 0 y no se cuentan. En {_n(len(dominados))} NIT el mayor contrato es más del 50 % de "
                        f"su valor contratado: {_n(dominados_uno)} con un solo contrato y {_n(len(dominados) - dominados_uno)} "
                        f"con dos o más. Línea base (reparto uniforme dentro de cada NIT): {_n(len(de_uno))} NIT con "
                        f"exactamente un contrato que cuenta ({_n(sum(suma[n] == 0 for n in de_uno))} de ellos con suma 0).")}


@hipotesis("H4")
def h4(datos):
    cuentan, filtro = _cuentan(datos)
    dias_ventana = (VENTANA[1] - VENTANA[0]).days + 1
    dias_resto = (FIN - INICIO).days + 1 - dias_ventana
    if (dias_ventana, dias_resto) != (DIAS_VENTANA, DIAS_RESTO):
        raise ValueError(f"el calendario da {dias_ventana} y {dias_resto} días, no {DIAS_VENTANA} y {DIAS_RESTO}")
    s_ven, s_res = Decimal(0), Decimal(0)
    n_ven = n_res = 0
    dias_con_firma = [set(), set()]
    for _, dia, v in cuentan:
        if VENTANA[0] <= dia <= VENTANA[1]:
            s_ven += v
            n_ven += 1
            dias_con_firma[0].add(dia)
        else:
            s_res += v
            n_res += 1
            dias_con_firma[1].add(dia)
    if not s_res:
        raise ValueError("el resto de 2025 suma 0: no hay razón")
    por_dia_ven, por_dia_res = s_ven / DIAS_VENTANA, s_res / DIAS_RESTO
    valor = float(por_dia_ven / por_dia_res)
    return {"valor": valor, "linea_base": 1.0,
            "detalle": (f"{filtro}. Del 2025-10-08 al 2025-11-07 ({DIAS_VENTANA} días, {_n(len(dias_con_firma[0]))} "
                        f"con firmas): {_n(n_ven)} contratos suman {_pesos(s_ven)}, {_pesos(por_dia_ven.quantize(Decimal(1)))} "
                        f"por día. Resto de 2025 ({DIAS_RESTO} días, {_n(len(dias_con_firma[1]))} con firmas): {_n(n_res)} "
                        f"contratos suman {_pesos(s_res)}, {_pesos(por_dia_res.quantize(Decimal(1)))} por día. Razón = "
                        f"{_n(valor, 4)}. Línea base: 1,0 (firma pareja en el año: el resto de 2025 contra sí mismo).")}


@hipotesis("H5")
def h5(datos):
    cuentan, filtro = _cuentan(datos)
    total, bajos = defaultdict(int), defaultdict(int)
    for nit, _, v in cuentan:
        total[nit] += 1
        if v < LIMITE_H5:                              # menor que 10 pesos, los de valor 0 incluidos
            bajos[nit] += 1
    grandes = sorted(n for n in total if total[n] >= MINIMO_H5)
    if not grandes:
        raise ValueError(f"ningún NIT tiene {MINIMO_H5} contratos o más")
    prop = {n: bajos[n] / total[n] for n in grandes}
    valor = max(prop.values())
    en_max = [n for n in grandes if prop[n] == valor]
    pasan = sum(p > 0.1 for p in prop.values())
    n_todos, b_todos = len(cuentan), sum(bajos.values())
    ceros = sum(v == 0 for _, _, v in cuentan)
    base = b_todos / n_todos
    if len(en_max) == 1:
        donde = (f"{_n(bajos[en_max[0]])} de {_n(total[en_max[0]])} contratos de menos de 10 pesos "
                 f"en el NIT {en_max[0]}")
    else:
        donde = f"empatan {_n(len(en_max))} NIT ({', '.join(en_max)})"
    return {"valor": valor, "linea_base": base,
            "detalle": (f"{filtro}. Con {MINIMO_H5} contratos o más hay {_n(len(grandes))} NIT. El máximo es "
                        f"{_prop(valor)}: {donde}. NIT de esos {_n(len(grandes))} que pasan del 10 %: {_n(pasan)}. "
                        f"Línea base: {_n(b_todos)} de {_n(n_todos)} contratos valen menos de 10 pesos ({_n(ceros)} "
                        f"de valor 0 y {_n(b_todos - ceros)} entre 0 y 10): {_prop(base)}.")}

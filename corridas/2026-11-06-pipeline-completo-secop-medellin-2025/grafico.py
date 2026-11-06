"""Etapa 4 · Visualización: valor contratado en 2025 por entidad con sede en Medellín (SECOP II).

graficar(resultado, procedencia) recibe las filas aprobadas (nit_entidad, entidad, valor_contratado,
numero_contratos) y la procedencia de la ingesta, y devuelve una figura de Plotly.
Función pura: no lee ni escribe archivos, no usa red y no ejecuta comandos. El HTML lo escribe el verificador.

Decisiones (también en grafico.json):
- Barras horizontales de mayor a menor, desde cero, en miles de millones de pesos (escala 1e9).
- Las TOP_N entidades de mayor valor van una por una; las demás, juntas en la barra gris «Otras N entidades».
  Nada queda fuera: la suma de las barras es el total de la tabla.
- El NIT, el nombre completo y numero_contratos van en el cuadro que sale al pasar el puntero.
"""
from datetime import date

import plotly.graph_objects as go

ANIO = 2025
LUGAR = "Medellín"
ESCALA = 1e9            # el eje de valores muestra miles de millones de pesos
TOP_N = 15              # entidades que se muestran una por una
LARGO_ETIQUETA = 52     # caracteres de la etiqueta del eje; el nombre completo va en el cuadro del puntero

# Respaldo con los metadatos de la fuente de esta corrida (datos/procedencia.json, ingesta del 06-11-2026).
# Solo se usa un campo si la procedencia que llega no lo trae. Son metadatos, no datos de SECOP.
RESPALDO = {
    "titulo": "SECOP II - Contratos Electrónicos",
    "dominio": "www.datos.gov.co",
    "conjunto": "jbjy-vk9h",
    "atribucion": "Agencia Nacional de Contratación Pública – Colombia Compra Eficiente",
    "licencia": "CC BY-SA 4.0",
    "consultado": "2026-11-06T05:29:21",
}

# Tinta y colores en modo claro: una sola serie en azul; «Otras» en gris porque es un agregado.
SUPERFICIE = "#ffffff"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
REJILLA = "#e1e0d9"
BASE = "#c3c2b7"
SERIE = "#2a78d6"
GRIS_OTRAS = "#8a8880"
LETRA = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"

ALTO = 600              # cabe en el marco de 620 px del informe final
MARGEN = {"l": 370, "r": 28, "t": 78, "b": 160, "pad": 0}   # l: cabe una etiqueta de 52 caracteres
CONECTORES = {"de", "del", "la", "las", "los", "el", "y", "e", "en", "para", "a", "-", "–"}

_CAMBIO = str.maketrans({",": ".", ".": ","})


def _num(x, dec=0):
    """Número a la colombiana: punto de miles y coma decimal."""
    return f"{x:,.{dec}f}".translate(_CAMBIO)


def _valor(fila):
    return float(fila.get("valor_contratado") or 0)   # igual que la cuenta de control del verificador


def _entero(x):
    try:
        return int(x or 0)
    except (TypeError, ValueError):
        return 0


def _mm(pesos):
    """Pesos en miles de millones, con los decimales que dejan leer la cifra."""
    m = pesos / ESCALA
    a = abs(m)
    if a >= 100:
        return _num(m, 0)
    if a >= 1:
        return _num(m, 1)
    if a == 0:
        return "0"
    if a >= 0.01:
        return _num(m, 2)
    return "< 0,01"


def _pct(parte, total):
    if not total or not parte:
        return "0 %"
    p = 100 * parte / total
    if abs(p) < 0.1:
        return "< 0,1 %"
    return _num(p, 1) + " %"


def _fecha(iso):
    try:
        return date.fromisoformat(str(iso or "")[:10])
    except ValueError:
        return None


def _corto(nombre, largo=LARGO_ETIQUETA):
    """Recorta un nombre largo por el medio: el inicio dice qué es y el final, de dónde."""
    nombre = " ".join(str(nombre).split())
    if len(nombre) <= largo:
        return nombre
    palabras = nombre.split(" ")
    cab_max = (largo - 3) * 11 // 20
    cab = []
    for p in palabras:
        if len(" ".join(cab + [p])) > cab_max:
            break
        cab.append(p)
    while len(cab) > 1 and cab[-1].lower() in CONECTORES:
        cab.pop()
    inicio = " ".join(cab) if cab else nombre[:cab_max]
    cola_max = largo - 3 - len(inicio)          # lo que no usó el inicio queda para el final
    cola = []
    for p in reversed(palabras[len(cab):]):
        if len(" ".join([p] + cola)) > cola_max:
            break
        cola.insert(0, p)
    while len(cola) > 1 and cola[0].lower() in ("-", "–", "y", "e"):
        cola.pop(0)
    final = " ".join(cola) if cola else nombre[-cola_max:]
    return f"{inicio} … {final}"


def _unicas(etiquetas, nits):
    """Dos barras nunca comparten etiqueta (Plotly las juntaría en una sola fila)."""
    veces = {}
    for e in etiquetas:
        veces[e] = veces.get(e, 0) + 1
    salida, usadas = [], set()
    for i, (e, n) in enumerate(zip(etiquetas, nits), 1):
        if veces[e] > 1 and n:
            e = f"{e} · NIT {n}"
        while e in usadas:
            e = f"{e} ({i})"
        usadas.add(e)
        salida.append(e)
    return salida


def graficar(resultado, procedencia):
    proc = procedencia if isinstance(procedencia, dict) else {}
    fuente = proc.get("fuente") if isinstance(proc.get("fuente"), dict) else {}

    def dato(clave):
        return fuente.get(clave) or proc.get(clave) or RESPALDO[clave]

    filas = sorted(resultado or [], key=lambda f: (-_valor(f), str(f.get("nit_entidad") or "")))
    total = sum(_valor(f) for f in filas)
    contratos = sum(_entero(f.get("numero_contratos")) for f in filas)
    vistas, resto = (filas[:TOP_N], filas[TOP_N:]) if len(filas) > TOP_N + 1 else (filas, [])

    nombres = [" ".join(str(f.get("entidad") or "SIN NOMBRE").split()) for f in vistas]
    nits = [str(f.get("nit_entidad") or "").strip() for f in vistas]
    valores = [_valor(f) for f in vistas]
    cuentas = [_entero(f.get("numero_contratos")) for f in vistas]
    etiquetas = [_corto(n) for n in nombres]
    colores = [SERIE] * len(vistas)
    if resto:
        nombres.append(f"Otras {len(resto)} entidades (puestos {TOP_N + 1} a {len(filas)})")
        nits.append("varios")
        valores.append(sum(_valor(f) for f in resto))
        cuentas.append(sum(_entero(f.get("numero_contratos")) for f in resto))
        etiquetas.append(f"Otras {len(resto)} entidades")
        colores.append(GRIS_OTRAS)
    etiquetas = _unicas(etiquetas, nits)
    detalle = [[n, nit, _num(v, 0), _mm(v), _pct(v, total), _num(c, 0)]
               for n, nit, v, c in zip(nombres, nits, valores, cuentas)]
    x = [v / ESCALA for v in valores]

    consulta = _fecha(dato("consultado"))
    fecha = f"{consulta:%d-%m-%Y}" if consulta else "sin fecha de consulta"
    incompleto = consulta is not None and consulta <= date(ANIO, 12, 31)

    if total >= 1e12:
        total_txt = f"{_num(total / 1e12, 1)} billones de pesos ({_num(total / ESCALA, 0)} mil millones)"
    else:
        total_txt = f"{_mm(total)} mil millones de pesos"
    sub = f"{_num(len(filas))} entidades · {_num(contratos)} contratos · {total_txt}."
    if resto:
        sub += f" Las {len(vistas)} de mayor valor suman el {_pct(sum(valores[:-1]), total)}."
    if incompleto:
        sub += f" Período incompleto: datos con corte al {fecha}."
    titulo = (f"<b>Valor contratado en {ANIO} por entidad con sede en {LUGAR}</b>"
              f"<br><span style=\"font-size:13px;color:{TINTA_2}\">{sub}</span>")

    lineas = [
        f"Fuente: {dato('titulo')} ({dato('dominio')}, conjunto {dato('conjunto')}), consultado el {fecha}.",
        f"{dato('atribucion')}, licencia {dato('licencia')}.",
        f"Contratos firmados del 01-01-{ANIO} al 31-12-{ANIO}; valor del contrato con sus adiciones, no lo pagado.",
        f"«Con sede en {LUGAR}»: ciudad {LUGAR} en SECOP II; incluye regionales de entidades nacionales.",
        "Preguntas abiertas del informe: se agrupa por NIT y no por unidad que contrata; "
        "incluye una universidad privada y operaciones de crédito público.",
    ]
    if not filas:
        lineas.insert(0, "Sin filas en el resultado aprobado.")

    fig = go.Figure(go.Bar(
        x=x, y=etiquetas, orientation="h",
        marker={"color": colores, "line": {"width": 0}},
        text=[f"{_mm(v)} · {_pct(v, total)}" for v in valores],
        textposition="outside", cliponaxis=False, constraintext="none",
        textfont={"size": 11, "color": TINTA_2, "family": LETRA},
        customdata=detalle,
        hovertemplate=("<b>%{customdata[0]}</b><br>NIT: %{customdata[1]}<br>"
                       "Valor contratado: $ %{customdata[2]}<br>"
                       "%{customdata[3]} mil millones · %{customdata[4]} del total<br>"
                       "Contratos: %{customdata[5]}<extra></extra>"),
        showlegend=False,
    ))
    fig.update_layout(
        height=ALTO, margin=MARGEN, paper_bgcolor=SUPERFICIE, plot_bgcolor=SUPERFICIE,
        font={"family": LETRA, "size": 12, "color": TINTA_2},
        separators=",.", bargap=0.32, barcornerradius=4, dragmode=False,
        title={"text": titulo, "x": 0, "xref": "container", "xanchor": "left", "pad": {"l": 12},
               "y": 0.975, "yref": "container", "yanchor": "top",
               "font": {"size": 18, "color": TINTA, "family": LETRA}},
        xaxis={"title": {"text": "Valor contratado (miles de millones de pesos)", "standoff": 8,
                         "font": {"size": 12, "color": TINTA_2}},
               "range": [0, (max(x) if x and max(x) > 0 else 1) * 1.22],
               "tickformat": ",.0f", "showgrid": True, "gridcolor": REJILLA, "gridwidth": 1,
               "zeroline": True, "zerolinecolor": BASE, "zerolinewidth": 1, "showline": False,
               "ticks": "", "tickfont": {"size": 11, "color": TINTA_2}, "fixedrange": True},
        yaxis={"type": "category", "autorange": "reversed", "automargin": True, "showgrid": False,
               "showline": False, "ticks": "", "ticklabelstandoff": 8,
               "tickfont": {"size": 11, "color": TINTA_2}, "fixedrange": True},
        hoverlabel={"bgcolor": SUPERFICIE, "bordercolor": BASE, "align": "left",
                    "font": {"size": 12, "color": TINTA, "family": LETRA}},
        annotations=[{"text": "<br>".join(lineas), "xref": "paper", "yref": "paper", "x": 0, "y": 0,
                      "xanchor": "left", "yanchor": "top", "xshift": -(MARGEN["l"] - 12), "yshift": -54,
                      "align": "left", "showarrow": False,
                      "font": {"size": 11, "color": TINTA_2, "family": LETRA}}],
    )
    return fig

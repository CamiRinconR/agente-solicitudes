"""Etapa 4 · Visualización: valor contratado en 2025 por entidad pública con sede en Medellín (SECOP II).

graficar(resultado, procedencia) -> plotly.graph_objects.Figure. Función pura: no lee ni escribe archivos.
  resultado    filas aprobadas: nit_entidad, entidad, valor_contratado (pesos) y numero_contratos
  procedencia  la de la ingesta: fuente, licencia, atribución y fecha de consulta

Forma: barras horizontales de mayor a menor, un solo tono, eje de valores desde cero en miles de millones
de pesos (escala 1e9). Las PRIMERAS entidades tienen barra propia y las demás se suman en una barra gris
«Otras N entidades»: el gráfico suma el total de la tabla y no queda nada por fuera.
"""
import html
import math
import unicodedata
from datetime import date

import plotly.graph_objects as go

PRIMERAS = 12          # entidades con barra propia; las demás se suman en «Otras»
ESCALA = 1e9           # el eje muestra miles de millones de pesos
ANCHO_NOMBRE = 38      # caracteres por línea del nombre en el eje (hasta 2 líneas)
ALTO_FILA = 29         # píxeles por barra: cabe un nombre de 2 líneas con aire
MARGEN_IZQ = 270       # sitio para los nombres
BORDE = 14             # borde izquierdo común del título y de las notas
ANCHO_NOTA = 160       # caracteres por línea en las notas al pie (caben desde unos 800 px de ancho)
ALTO_LINEA_NOTA = 14   # píxeles por línea de nota
MARGEN_SUP = 88        # título y subtítulo de 2 líneas
BAJO_EJE = 50          # marcas y título del eje de valores, antes de las notas

SUPERFICIE, TINTA, TINTA_2 = "#fcfcfb", "#0b0b0b", "#52514e"
REJILLA, LINEA_BASE = "#e1e0d9", "#c3c2b7"
AZUL, GRIS = "#2a78d6", "#898781"
LETRA = 'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'

TITULO = "Valor contratado en 2025 por entidad pública con sede en Medellín"
NOTA = ("Contratos firmados del 1 de enero al 31 de diciembre de 2025, en cualquier estado, con el valor que figura "
        "en SECOP II al consultarlo (incluye adiciones). Una barra por NIT (incluye las dependencias que contratan con "
        "ese NIT). Supuestos por defecto (preguntas abiertas del informe): cuentan las unidades territoriales de "
        "entidades nacionales registradas en Medellín, las operaciones de crédito público y una universidad privada "
        "que publica en SECOP II.")


def _num(x, dec=0):
    """Número en formato colombiano: punto de miles y coma decimal."""
    return f"{x:,.{dec}f}".translate(str.maketrans(",.", ".,"))


def _mm(valor):
    """Pesos -> miles de millones, con los decimales justos para leerlo."""
    v = valor / ESCALA
    if v <= 0:
        return "0"
    dec = 0 if v >= 100 else (1 if v >= 1 else 1 - math.floor(math.log10(v)))
    return _num(v, dec)


def _limpio(texto):
    """Texto para mostrar: sin caracteres de control (no se ven) y con espacios simples."""
    t = "".join(ch for ch in str(texto or "") if unicodedata.category(ch) != "Cc")
    return " ".join(t.split())


def _lineas(texto, ancho, maximo=None):
    """Parte el texto por palabras en líneas de hasta `ancho` caracteres; con `maximo`, corta con «…»."""
    lineas, actual = [], ""
    for palabra in texto.split():
        if actual and len(actual) + 1 + len(palabra) > ancho:
            lineas.append(actual)
            actual = palabra
        else:
            actual = f"{actual} {palabra}" if actual else palabra
    if actual:
        lineas.append(actual)
    if maximo and len(lineas) > maximo:
        palabras = lineas[maximo - 1].split()
        while len(palabras) > 1 and len(" ".join(palabras)) + 1 > ancho:
            palabras.pop()
        lineas = lineas[:maximo - 1] + [" ".join(palabras).rstrip(" ,.;:-–") + "…"]
    return lineas


def _html(lineas):
    """Une líneas para Plotly, escapando &, < y > para que un nombre no se lea como etiqueta."""
    return "<br>".join(html.escape(linea, quote=False) for linea in lineas)


def _fecha_consulta(procedencia):
    texto = str(procedencia.get("consultado") or "")
    try:
        return date.fromisoformat(texto[:10]).strftime("%d-%m-%Y")
    except ValueError:
        return "sin fecha de consulta"


def _fuente(procedencia):
    f = procedencia.get("fuente") or {}
    titulo = f.get("titulo") or "SECOP II - Contratos Electrónicos"
    donde = ", ".join(x for x in (str(f.get("dominio") or "").removeprefix("www."), f.get("conjunto")) if x)
    quien = procedencia.get("atribucion") or f.get("atribucion")
    licencia = procedencia.get("licencia") or f.get("licencia")
    partes = [f"Fuente: {titulo}" + (f" ({donde})" if donde else "")]
    if quien:
        partes.append(str(quien))
    if licencia:
        partes.append(f"licencia {licencia}")
    return ", ".join(partes) + f". Consultado el {_fecha_consulta(procedencia)}."


def graficar(resultado, procedencia):
    procedencia = procedencia or {}
    filas = sorted(
        ({"nit": str(f.get("nit_entidad") or "").strip(),
          "nombre": _limpio(f.get("entidad")) or "(sin nombre)",
          "valor": float(f.get("valor_contratado") or 0),
          "contratos": int(f.get("numero_contratos") or 0)} for f in (resultado or [])),
        key=lambda f: (-f["valor"], f["nit"]))
    total = sum(f["valor"] for f in filas)
    total_contratos = sum(f["contratos"] for f in filas)
    propias = filas if len(filas) <= PRIMERAS + 1 else filas[:PRIMERAS]
    resto = filas[len(propias):]

    barras, vistas = [], set()
    for f in propias:
        clave = f["nit"] or "sin NIT"
        while clave in vistas:            # nunca dos barras en la misma categoría
            clave += "·"
        vistas.add(clave)
        barras.append({"clave": clave, "valor": f["valor"], "contratos": f["contratos"], "color": AZUL,
                       "eje": _html(_lineas(f["nombre"], ANCHO_NOMBRE, 2)),
                       "hover": _html(_lineas(f["nombre"], 48, 3)), "detalle": f"NIT {html.escape(f['nit'])}<br>"})
    if resto:
        otras = f"Otras {len(resto)} entidades"
        barras.append({"clave": "otras", "valor": sum(f["valor"] for f in resto),
                       "contratos": sum(f["contratos"] for f in resto), "color": GRIS,
                       "eje": otras, "hover": f"{otras}, sumadas", "detalle": ""})

    def punta(b):
        n = b["contratos"]
        return (f"<b>{_mm(b['valor'])}</b>  <span style=\"color:{TINTA_2}\">· {_num(n)} "
                f"contrato{'' if n == 1 else 's'}</span>")

    def parte(v):
        return f"{_num(100 * v / total, 1)} %" if total else "—"

    claves = [b["clave"] for b in barras]
    fig = go.Figure(go.Bar(
        x=[b["valor"] / ESCALA for b in barras], y=claves, orientation="h",
        marker=dict(color=[b["color"] for b in barras], cornerradius=4, line=dict(width=0)),
        text=[punta(b) for b in barras], textposition="outside", cliponaxis=False, constraintext="none",
        textfont=dict(family=LETRA, size=11, color=TINTA),
        customdata=[[b["hover"], b["detalle"], _num(b["valor"]), _num(b["contratos"]), parte(b["valor"])]
                    for b in barras],
        hovertemplate=("<b>%{customdata[0]}</b><br>%{customdata[1]}Valor contratado: %{customdata[2]} pesos"
                       "<br>Contratos: %{customdata[3]}<br>%{customdata[4]} del total<extra></extra>"),
        name="Valor contratado (miles de millones de pesos)", showlegend=False))

    sub = (f"Las {len(propias)} entidades de mayor valor"
           + (f" y las otras {len(resto)}, sumadas en «Otras»" if resto else "")
           + " · miles de millones de pesos, según SECOP II<br>"
           + f"Total: {_mm(total)} mil millones de pesos en {_num(total_contratos)} contratos de "
           + f"{_num(len(filas))} entidades")
    notas = _lineas(NOTA, ANCHO_NOTA) + _lineas(_fuente(procedencia), ANCHO_NOTA)
    alto_barras = max(1, len(barras)) * ALTO_FILA
    margen_inf = BAJO_EJE + ALTO_LINEA_NOTA * len(notas) + 10
    maximo = max((b["valor"] for b in barras), default=0) / ESCALA

    fig.update_layout(
        height=MARGEN_SUP + alto_barras + margen_inf,
        margin=dict(l=MARGEN_IZQ, r=28, t=MARGEN_SUP, b=margen_inf),
        paper_bgcolor=SUPERFICIE, plot_bgcolor=SUPERFICIE, separators=",.",
        font=dict(family=LETRA, size=12, color=TINTA_2),
        title=dict(text=TITULO, x=0, xref="container", xanchor="left", pad=dict(l=BORDE),
                   y=1 - 14 / (MARGEN_SUP + alto_barras + margen_inf), yref="container", yanchor="top",
                   font=dict(family=LETRA, size=17, color=TINTA, weight=600),
                   subtitle=dict(text=sub, font=dict(family=LETRA, size=12, color=TINTA_2))),
        bargap=0.4, showlegend=False, dragmode=False,
        hoverlabel=dict(bgcolor="#ffffff", bordercolor=REJILLA, font=dict(family=LETRA, size=12, color=TINTA)),
        xaxis=dict(title=dict(text="Valor contratado (miles de millones de pesos)", standoff=10,
                              font=dict(family=LETRA, size=11.5, color=TINTA_2)),
                   range=[0, maximo * 1.36 if maximo > 0 else 1], tickformat=",.0f", ticks="", showline=False,
                   showgrid=True, gridcolor=REJILLA, gridwidth=1, zeroline=True, zerolinecolor=LINEA_BASE,
                   zerolinewidth=1, tickfont=dict(family=LETRA, size=11, color=TINTA_2), fixedrange=True,
                   automargin=True),
        yaxis=dict(type="category", categoryorder="array", categoryarray=claves, tickmode="array",
                   tickvals=claves, ticktext=[b["eje"] for b in barras], autorange="reversed", showgrid=False,
                   ticks="", ticklabelstandoff=10, tickfont=dict(family=LETRA, size=10.5, color=TINTA),
                   automargin=True, fixedrange=True),
        annotations=[dict(text=_html(notas), xref="paper", yref="paper", x=0, y=-BAJO_EJE / alto_barras,
                          xanchor="left", yanchor="top", xshift=-(MARGEN_IZQ - BORDE), showarrow=False,
                          align="left", font=dict(family=LETRA, size=10.5, color=TINTA_2))],
    )
    return fig

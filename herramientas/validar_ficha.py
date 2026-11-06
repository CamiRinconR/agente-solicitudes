#!/usr/bin/env python3
"""Valida sin IA la ficha de oportunidad que escribe la IA para un conjunto de datos públicos grande.

Uso: python herramientas/validar_ficha.py <ficha.json> --inventario <inventario_<dominio>.json> [--sin-red]

La ficha dice qué se puede afirmar de cada unidad («el contrato {id_contrato} está {estado_contrato} en {ciudad}»),
qué preguntas de costo, calidad o impacto pueden analizar las PERSONAS (la IA no concluye), con qué otros conjuntos se
cruza, cómo se gobierna y cómo se procesa. Cada afirmación de la ficha se comprueba contra la fuente real:
  V1 estructura completa y tipos válidos;
  V2 toda columna citada existe en su conjunto (y el conjunto del cruce existe en el inventario);
  V3 privacidad: ninguna columna personal o cuasi-identificadora se usa en plantillas, preguntas, consultas ni cruces,
     y todas las del conjunto quedan en gobernanza.excluir o gobernanza.seudonimizar;
  V4 cada consulta SoQL es agregada (la cifra se calcula en la fuente, nunca se traen filas), corre en el servidor
     con LIMIT 50 o menos y devuelve filas; los grupos con menos de k_minimo registros se avisan (k-anonimato);
  V5 cada cruce se MIDE: qué fracción de las llaves de este conjunto aparece en el otro, con la normalización declarada;
  V6 sin conclusiones ni cifras inventadas en el texto (solo años y referencias legales); las preguntas son preguntas;
  V7 sin instrucciones para agentes ni datos personales en ningún texto;
  V8 la estrategia de procesamiento es coherente con el dictamen de big data medido.
Escribe <ficha>.verificacion.json. Sale con 0 si todo pasa y con 1 si algo falla.
"""
import json
import re
import sys
import time
import unicodedata
import urllib.parse
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from gobernanza import PATRONES, clasificar_columna, parece_instruccion  # noqa: E402
from explorador_catalogo import pedir  # noqa: E402

TIPOS_DECIR = {"estado", "lugar", "impacto", "dinero", "tiempo"}
TIPOS_PREGUNTA = {"costo", "calidad", "impacto"}
AGREGADO = re.compile(r"\b(group\s+by|count\s*\(|sum\s*\(|avg\s*\(|min\s*\(|max\s*\(|count_distinct)", re.I)
CONCLUSION = re.compile(
    r"\b(se concluye|concluimos|demuestra(n)? que|queda demostrado|se evidencia que|est[aá] claro que|sin duda|"
    r"se ahorr\w*|ahorrar[ií]a\w*|reduce en|reducir[ií]a en|mejora en|mejorar[ií]a en|significativamente|"
    r"la causa (es|fue)|se debe a)\b", re.I)
PERMITIDOS_NUM = re.compile(r"\b(1[89]\d\d|20\d\d)\b|\b(ley|decreto|resoluci[oó]n|circular|conpes|art[ií]culo)\s+\d[\d.]*", re.I)
CAMPOS_TEXTO = ("pregunta", "por_que_importa", "para_que", "nota", "base_legal", "estrategia", "normalizacion")


def textos(obj, ruta=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from textos(v, f"{ruta}.{k}" if ruta else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from textos(v, f"{ruta}[{i}]")
    elif isinstance(obj, str):
        yield ruta, obj


def es_personal(col):
    return clasificar_columna(col) in ("personal", "cuasi")


def soql(dominio, conjunto, consulta, timeout_s=180):
    url = f"https://{dominio}/resource/{conjunto}.json?" + urllib.parse.urlencode({"$query": consulta})
    t = time.time()
    return json.loads(pedir(url)), round(time.time() - t, 1)


def limitar(consulta, tope=50):
    m = re.search(r"\blimit\s+(\d+)", consulta, re.I)
    if not m:
        return consulta.rstrip().rstrip(";") + f" LIMIT {tope}", None
    if int(m.group(1)) > tope:
        return consulta[:m.start(1)] + str(tope) + consulta[m.end(1):], f"LIMIT {m.group(1)} se bajó a {tope}"
    return consulta, None


def normalizar(v, metodo):
    s = "" if v is None else str(v)
    m = (metodo or "").lower()
    if "dígito" in m or "digito" in m or "ceros" in m or "numér" in m or "numer" in m:
        s = re.sub(r"\D", "", s)
        ancho = re.search(r"(\d+)\s*(d[ií]gitos|caracteres|posiciones)", m)
        if s and ancho:
            s = s.zfill(int(ancho.group(1)))
        elif s:
            s = s.lstrip("0") or "0"
        return s
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()
    return re.sub(r"\s+", " ", s).strip()


def llaves_distintas(dominio, conjunto, col, tope=50000):
    filas, seg = soql(dominio, conjunto, f"SELECT {col}, count(*) AS n GROUP BY {col} LIMIT {tope}")
    return {r.get(col): int(r.get("n", 0)) for r in filas if r.get(col) not in (None, "")}, len(filas) >= tope, seg


def buscar_en_otro(dominio, otro, col, valores, lote=40):
    """Cuántos de estos valores exactos aparecen en la columna del otro conjunto (para llaves con millones de valores)."""
    hallados = set()
    for i in range(0, len(valores), lote):
        trozo = [v.replace("'", "''") for v in valores[i:i + lote]]
        lista = ", ".join(f"'{v}'" for v in trozo)
        filas, _ = soql(dominio, otro, f"SELECT {col}, count(*) AS n WHERE {col} IN ({lista}) GROUP BY {col} LIMIT {lote * 2}")
        hallados |= {r.get(col) for r in filas}
    return hallados


def medir_cruce(dominio, aqui, cruce):
    a, a_lleno, s1 = llaves_distintas(dominio, aqui, cruce["llave_aqui"])
    if a_lleno:
        # Llave de alta cardinalidad (por ejemplo, un id por contrato): comparar «los primeros 50.000» de cada lado
        # mediría subconjuntos sin relación. Se toma una muestra de llaves de aquí y se buscan tal cual allá.
        muestra = [k for k in a if isinstance(k, str)][:: max(1, len(a) // 200)][:200]
        t = time.time()
        hallados = buscar_en_otro(dominio, cruce["con"], cruce["llave_alla"], muestra)
        frac = len([k for k in muestra if k in hallados]) / max(1, len(muestra))
        return {"ok": frac >= 0.5, "llaves_aqui": "más de 50.000", "muestra": len(muestra), "coinciden_llaves": round(frac, 3),
                "segundos": round(s1 + time.time() - t, 1),
                "detalle": f"{frac:.1%} de una muestra de {len(muestra)} llaves de aquí aparece allá (búsqueda exacta)"}
    b, b_lleno, s2 = llaves_distintas(dominio, cruce["con"], cruce["llave_alla"])
    metodo = cruce.get("normalizacion", "")
    bn = {normalizar(k, metodo) for k in b}
    an = {}
    for k, n in a.items():
        nk = normalizar(k, metodo)
        an[nk] = an.get(nk, 0) + n
    if not an:
        return {"ok": False, "detalle": "la llave de este conjunto no tiene valores"}
    comunes = [k for k in an if k in bn]
    por_llaves = len(comunes) / len(an)
    por_filas = sum(an[k] for k in comunes) / max(1, sum(an.values()))
    nota = " (medido sobre los primeros 50.000 valores distintos)" if a_lleno or b_lleno else ""
    return {"ok": por_filas >= 0.5, "llaves_aqui": len(an), "llaves_alla": len(bn), "coinciden_llaves": round(por_llaves, 3),
            "coinciden_filas": round(por_filas, 3), "segundos": s1 + s2,
            "detalle": f"{por_filas:.1%} de las filas y {por_llaves:.1%} de las llaves de aquí aparecen allá{nota}"}


def validar(ficha, inv, red=True):
    res = []

    def chequeo(clave, ok, detalle):
        res.append({"chequeo": clave, "ok": bool(ok), "detalle": detalle})
        return ok

    conj = inv.get(ficha.get("id"))
    if not chequeo("V1 conjunto", conj is not None, f"{ficha.get('id')} {'existe' if conj else 'no está'} en el inventario"):
        return res
    campos = set(conj["campos"])
    dominio = ficha.get("dominio") or "www.datos.gov.co"

    faltan = [k for k in ("que_se_puede_decir", "preguntas", "cruces", "gobernanza", "procesamiento", "riesgos_de_lectura") if k not in ficha]
    ok1 = not faltan
    ok1 &= chequeo("V1 estructura", not faltan, "completa" if not faltan else f"faltan: {', '.join(faltan)}")
    if not ok1:
        return res
    malos = [d.get("tipo") for d in ficha["que_se_puede_decir"] if d.get("tipo") not in TIPOS_DECIR]
    malos += [p.get("tipo") for p in ficha["preguntas"] if p.get("tipo") not in TIPOS_PREGUNTA]
    chequeo("V1 tipos", not malos and ficha["que_se_puede_decir"] and 2 <= len(ficha["preguntas"]) <= 6,
            "válidos" if not malos else f"tipos no válidos: {malos}; entre 2 y 6 preguntas y al menos una plantilla")

    # V2 y V3: columnas citadas
    citadas = []
    for d in ficha["que_se_puede_decir"]:
        citadas += re.findall(r"\{([^}]+)\}", d.get("plantilla", "")) + d.get("columnas", [])
    for p in ficha["preguntas"]:
        citadas += p.get("columnas", [])
    citadas += [c["llave_aqui"] for c in ficha["cruces"] if c.get("llave_aqui")]
    inexistentes = sorted({c for c in citadas if c not in campos})
    chequeo("V2 columnas", not inexistentes, "todas existen" if not inexistentes else f"no existen: {inexistentes}")
    for c in ficha["cruces"]:
        otro = inv.get(c.get("con"))
        chequeo(f"V2 cruce {c.get('con')}", otro is not None and c.get("llave_alla") in set(otro["campos"]),
                "el conjunto y su llave existen" if otro and c.get("llave_alla") in set(otro["campos"])
                else "el conjunto o su llave no existen en el inventario")
    personales_usadas = sorted({c for c in citadas if es_personal(c)})
    for p in ficha["preguntas"]:
        for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", p.get("consulta_soql", "")):
            if tok in campos and es_personal(tok):
                personales_usadas.append(tok)
    chequeo("V3 sin columnas personales en uso", not personales_usadas,
            "ninguna" if not personales_usadas else f"se usan: {sorted(set(personales_usadas))}")
    gob = ficha.get("gobernanza", {})
    cubiertas = set(gob.get("excluir", [])) | set(gob.get("seudonimizar", []))
    sin_cubrir = sorted(c for c in campos if es_personal(c) and c not in cubiertas)
    chequeo("V3 gobernanza completa", not sin_cubrir,
            "todas las personales quedan excluidas o seudonimizadas" if not sin_cubrir else f"sin decisión: {sin_cubrir}")
    k = int(gob.get("k_minimo") or 0)
    chequeo("V3 k mínimo", k >= 5, f"k_minimo = {k} (se exige 5 o más)")

    # V6 y V7: textos
    cifras, conclusiones, instrucciones, personales = [], [], [], []
    for ruta, t in textos(ficha):
        hoja = ruta.split(".")[-1].split("[")[0]
        if hoja in CAMPOS_TEXTO or ruta.startswith(("riesgos_de_lectura", "procesamiento.pasos")):
            limpio = PERMITIDOS_NUM.sub("", t)
            if re.search(r"\d", limpio):
                cifras.append(f"{ruta}: «{t[:80]}»")
            if CONCLUSION.search(t):
                conclusiones.append(f"{ruta}: «{CONCLUSION.search(t).group(0)}»")
        if parece_instruccion(t):
            instrucciones.append(ruta)
        for nombre, pat in PATRONES.items():
            if pat.search(t):
                personales.append(f"{ruta}: {nombre}")
    no_preguntas = [p.get("pregunta", "")[:60] for p in ficha["preguntas"]
                    if not (p.get("pregunta", "").strip().startswith("¿") and p.get("pregunta", "").strip().endswith("?"))]
    chequeo("V6 sin cifras inventadas", not cifras, "sin cifras fuera de años y normas" if not cifras else "; ".join(cifras[:4]))
    chequeo("V6 sin conclusiones", not conclusiones, "el análisis queda para las personas" if not conclusiones else "; ".join(conclusiones[:4]))
    chequeo("V6 preguntas", not no_preguntas, "todas son preguntas" if not no_preguntas else f"no son preguntas: {no_preguntas}")
    chequeo("V7 sin instrucciones", not instrucciones, "ninguna" if not instrucciones else f"en: {instrucciones[:4]}")
    chequeo("V7 sin datos personales", not personales, "ninguno" if not personales else "; ".join(personales[:4]))

    # V8: coherencia con el dictamen
    nivel = ficha.get("nivel_big_data")
    estr = (ficha["procesamiento"].get("estrategia", "") + " " + " ".join(ficha["procesamiento"].get("pasos", []))).lower()
    if nivel == 3:
        ok8 = any(s in estr for s in ("agregar en la fuente", "spark", "distribu"))
    elif nivel == 2:
        ok8 = any(s in estr for s in ("duckdb", "parquet", "por partes", "agregar en la fuente", "spark"))
    else:
        ok8 = True
    chequeo("V8 procesamiento", ok8, f"nivel {nivel}: «{ficha['procesamiento'].get('estrategia', '')[:70]}»")

    # V4 y V5: contra la fuente real
    if red:
        for i, p in enumerate(ficha["preguntas"], 1):
            q = p.get("consulta_soql", "")
            if not AGREGADO.search(q):
                chequeo(f"V4 consulta {i}", False, "no es agregada: la cifra debe calcularse en la fuente, sin traer filas")
                continue
            q2, aviso = limitar(q)
            try:
                filas, seg = soql(dominio, ficha["id"], q2)
                pequenas = 0
                alias = re.findall(r"count\s*\([^)]*\)\s+as\s+([a-z_][a-z0-9_]*)", q2, re.I)
                for r in filas:
                    for a in alias:
                        try:
                            if 0 < float(r.get(a, k)) < k:
                                pequenas += 1
                        except (TypeError, ValueError):
                            pass
                det = f"{len(filas)} filas en {seg} s" + (f"; {aviso}" if aviso else "")
                if pequenas:
                    det += f"; AVISO: {pequenas} grupo(s) con menos de {k} registros (k-anonimato al publicar)"
                chequeo(f"V4 consulta {i}", len(filas) > 0, det)
            except Exception as e:
                chequeo(f"V4 consulta {i}", False, f"el servidor la rechazó: {type(e).__name__}: {str(e)[:120]}")
        for c in ficha["cruces"]:
            try:
                m = medir_cruce(dominio, ficha["id"], c)
                chequeo(f"V5 cruce {c['con']}", m["ok"], m["detalle"])
                c["medicion"] = m
            except Exception as e:
                chequeo(f"V5 cruce {c.get('con')}", False, f"no se pudo medir: {type(e).__name__}: {str(e)[:120]}")
    return res


def main(argv):
    if len(argv) < 3 or "--inventario" not in argv:
        raise SystemExit(__doc__)
    ruta = Path(argv[0])
    ficha = json.loads(ruta.read_text(encoding="utf-8"))
    inv = {x["id"]: x for x in json.loads(Path(argv[argv.index("--inventario") + 1]).read_text(encoding="utf-8"))}
    res = validar(ficha, inv, red="--sin-red" not in argv)
    fallas = [r for r in res if not r["ok"]]
    salida = ruta.with_suffix(".verificacion.json")
    salida.write_text(json.dumps({"ficha": ruta.name, "chequeos": res, "fallas": len(fallas),
                                  "cruces": [c.get("medicion") for c in ficha.get("cruces", [])]}, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    for r in res:
        print(f"  {'✓' if r['ok'] else '✗'} {r['chequeo']}: {r['detalle']}")
    print("RESUMEN " + json.dumps({"ficha": ruta.name, "chequeos": len(res), "fallas": len(fallas)}, ensure_ascii=False))
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

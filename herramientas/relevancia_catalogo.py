#!/usr/bin/env python3
"""Relevancia de los conjuntos de un catálogo (sin IA): ¿qué bases públicas permiten algo grande y relevante?

Uso: python herramientas/relevancia_catalogo.py <dominio> --catalogo <carpeta> [--top 40] [--min-filas 1000000]

Lee el inventario del catálogo (Socrata) y las mediciones del explorador (<carpeta>/.cache.json), y marca por el
NOMBRE de las columnas los ingredientes para poder decir algo de cada unidad, como «este contrato está en ejecución,
está en Quibdó, vale tanto y es del sector salud»:
  unidad   se puede seguir una por una (id de contrato, de proceso o de proyecto, BPIN, radicado);
  estado   en qué va (estado, fase, etapa, avance);
  lugar    dónde está (municipio, departamento, código DANE, coordenadas);
  dinero   cuánto vale o cuánto se pagó (valor, monto, presupuesto, pagos);
  tiempo   cuándo (fechas, año, vigencia);
  impacto  a quién o a qué toca (sector, población, beneficiarios, indicadores, objeto, programa).
Las llaves de cruce (código DANE, NIT de la entidad, BPIN, id de contrato o de proceso) dicen con qué otros conjuntos
grandes se puede unir cada uno: así se pasa de «un contrato» a «su efecto en el municipio». Las llaves que identifican
personas (documento o NIT del proveedor, nombres) NO cuentan como llaves: eso es gobernanza, no relevancia.

Puntaje (regla declarada, no un juicio; sirve para ordenar qué revisar primero):
  tamaño 0–3 (3 big data, 2 frontera, 1 al menos --min-filas) + estado 2 + lugar 2 (+1 con código DANE)
  + unidad 1 + dinero 1 + tiempo 1 + impacto 1 + cruces con otros conjuntos grandes (1 por tipo de llave, hasta 3)
  + actualizado en los últimos 12 meses 1.                                                     Máximo: 17.
Escribe <carpeta>/relevancia_<dominio>.csv y .json, y el inventario usado (inventario_<dominio>.json).
"""
import csv
import json
import re
import sys
import unicodedata
import urllib.parse
from datetime import date, timedelta
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from gobernanza import clasificar_columna  # noqa: E402
from explorador_catalogo import pedir  # noqa: E402


def normal(texto):
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    return re.sub(r"\ba o\b", "ano", t)          # Socrata escribe «año» como «a_o»


ES_FECHA = re.compile(r"^fecha\b")
INGREDIENTES = {
    "unidad": re.compile(r"\b(id|identificador|referencia|numero|codigo|nro|no)\b.*\b(contrato|proceso|proyecto|obra|convenio|"
                         r"orden|radicado|caso|solicitud|tramite|expediente|bpin)\b|\bbpin\b|\bradicado\b|\bproceso de compra\b|"
                         r"\burlproceso\b|\bid (del )?(contrato|proceso|proyecto)\b"),
    "estado": re.compile(r"^(estado|fase|etapa|situacion|status)\b|\bestado\b|\bavance\b|\bporcentaje de ejecucion\b"),
    "lugar": re.compile(r"\b(municipio|mpio|departamento|depto|ciudad|divipola|dane|latitud|longitud|localizacion|ubicacion|"
                        r"georreferenciacion|coordenada|vereda|corregimiento|region|territorial)\b"),
    "dinero": re.compile(r"\b(valor|monto|presupuesto|pagad\w*|pagos?|recursos?|costo|precio|apropiacion|compromiso|obligacion|"
                         r"giros?|desembolso|saldo|facturad\w*|inversion|gasto|ingresos?|recaudo)\b"),
    "tiempo": re.compile(r"^fecha\b|\b(ano|anio|vigencia|periodo|mes|trimestre|semestre)\b"),
    "impacto": re.compile(r"\b(sector|poblacion|beneficiari\w*|cobertura|meta|indicador\w*|matricula\w*|atencion\w*|vacun\w*|"
                          r"mortalidad|desercion|victimas?|pobreza|objeto|programa|categoria)\b"),
}
LLAVES = [   # (tipo, patrón sobre el nombre normalizado); el orden importa: la primera que encaja gana
    ("dane_municipio", re.compile(r"\b(cod\w*|dane|divipola)\b.*\b(municipio|mpio|ciudad)\b|\b(municipio|mpio)\b.*\b(cod\w*|dane|divipola)\b|^divipola$|^(cod\w* )?dane$")),
    ("dane_departamento", re.compile(r"\b(cod\w*|dane)\b.*\b(departamento|depto)\b|\b(departamento|depto)\b.*\b(cod\w*|dane)\b")),
    ("bpin", re.compile(r"\bbpin\b")),
    ("nit_entidad", re.compile(r"\b(nit|codigo)\b.*\bentidad\b|\bentidad\b.*\bnit\b")),
    ("id_contrato", re.compile(r"\b(id|referencia|numero)\b.*\bcontrato\b")),
    ("id_proceso", re.compile(r"\bproceso de compra\b|\b(id|numero|referencia)\b.*\bproceso\b")),
    ("municipio", re.compile(r"^(nombre )?(municipio|ciudad)( nombre)?$")),
    ("departamento", re.compile(r"^(nombre )?departamento( nombre)?$")),
]


def inventario_completo(dominio, carpeta):
    """El inventario con nombres de campo y nombres visibles de columnas (se guarda para repetir sin red)."""
    ruta = carpeta / f"inventario_{dominio.replace('www.', '').replace('.', '_')}.json"
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    out, off = [], 0
    while True:
        d = json.loads(pedir("https://api.us.socrata.com/api/catalog/v1?" +
                             urllib.parse.urlencode({"domains": dominio, "only": "dataset", "limit": 1000, "offset": off})))
        for x in d["results"]:
            r, cl = x["resource"], x.get("classification", {})
            out.append({"id": r["id"], "nombre": r["name"], "categoria": cl.get("domain_category"),
                        "campos": r.get("columns_field_name", []), "visibles": r.get("columns_name", []),
                        "tipos": r.get("columns_datatype", []), "actualizado": (r.get("data_updated_at") or "")[:10],
                        "publicador": r.get("attribution"), "url": x.get("permalink")})
        off += 1000
        if off >= d.get("resultSetSize", 0) or not d["results"]:
            break
    ruta.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def analizar_columnas(campos, visibles):
    ingr = {k: [] for k in INGREDIENTES}
    llaves = {}
    for i, campo in enumerate(campos):
        vis = visibles[i] if i < len(visibles) else ""
        if clasificar_columna(campo) in ("personal", "cuasi") or clasificar_columna(normal(vis).replace(" ", "_")) in ("personal", "cuasi"):
            continue                                   # lo que identifica personas no es ingrediente ni llave
        for n in {normal(campo), normal(vis)} - {""}:
            for k, pat in INGREDIENTES.items():
                if k != "tiempo" and ES_FECHA.search(n):
                    continue
                if pat.search(n) and campo not in ingr[k]:
                    ingr[k].append(campo)
            for tipo, pat in LLAVES:
                if pat.search(n):
                    llaves.setdefault(tipo, campo)
                    break
    return ingr, llaves


def main(argv):
    if len(argv) < 3 or "--catalogo" not in argv:
        raise SystemExit(__doc__)
    dominio = argv[0]
    carpeta = Path(argv[argv.index("--catalogo") + 1])
    top = int(argv[argv.index("--top") + 1]) if "--top" in argv else 40
    min_filas = int(argv[argv.index("--min-filas") + 1]) if "--min-filas" in argv else 1_000_000
    cache = json.loads((carpeta / ".cache.json").read_text())
    inv = inventario_completo(dominio, carpeta)
    hace_un_ano = (date.today() - timedelta(days=365)).isoformat()

    filas = []
    for x in inv:
        c = cache.get(x["id"], {})
        n = c.get("filas")
        nivel = c.get("nivel") or (1 if n is not None and n >= min_filas else (0 if n is not None else None))
        ingr, llaves = analizar_columnas(x["campos"], x["visibles"])
        filas.append({"x": x, "filas": n, "nivel": nivel, "ingr": ingr, "llaves": llaves})

    grandes = [f for f in filas if (f["nivel"] or 0) >= 1]
    por_llave = {}
    for f in grandes:
        for tipo in f["llaves"]:
            por_llave.setdefault(tipo, []).append(f["x"]["id"])

    salida = []
    for f in filas:
        x, ingr, llaves = f["x"], f["ingr"], f["llaves"]
        socios = {t: [i for i in por_llave.get(t, []) if i != x["id"]] for t in llaves}
        tipos_cruce = [t for t, s in socios.items() if s]
        tamano = {3: 3, 2: 2, 1: 1}.get(f["nivel"] or 0, 0)
        puntos = {
            "tamano": tamano, "estado": 2 * bool(ingr["estado"]),
            "lugar": (2 + ("dane_municipio" in llaves or "dane_departamento" in llaves)) if ingr["lugar"] else 0,
            "unidad": int(bool(ingr["unidad"])), "dinero": int(bool(ingr["dinero"])), "tiempo": int(bool(ingr["tiempo"])),
            "impacto": int(bool(ingr["impacto"])), "cruces": min(3, len(tipos_cruce)),
            "fresco": int((x["actualizado"] or "") >= hace_un_ano),
        }
        salida.append({
            "id": x["id"], "nombre": x["nombre"], "categoria": x["categoria"], "publicador": x["publicador"],
            "filas": f["filas"], "nivel_big_data": f["nivel"], "puntaje": sum(puntos.values()), "puntos": puntos,
            "dice_estado": bool(ingr["unidad"] and ingr["estado"]), "dice_lugar": bool(ingr["lugar"]),
            "dice_impacto": bool(ingr["impacto"] and tipos_cruce),
            "ingredientes": {k: v[:4] for k, v in ingr.items() if v}, "llaves": llaves,
            "se_cruza_con": {t: s[:5] for t, s in socios.items() if s}, "actualizado": x["actualizado"], "url": x["url"]})
    salida.sort(key=lambda r: (-r["puntaje"], -(r["filas"] or 0)))
    base = carpeta / f"relevancia_{dominio.replace('www.', '').replace('.', '_')}"
    base.with_suffix(".json").write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(base.with_suffix(".csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["puntaje", "id", "nombre", "categoria", "filas", "nivel_big_data", "dice_estado", "dice_lugar", "dice_impacto",
                    "llaves", "actualizado", "url"])
        for r in salida:
            w.writerow([r["puntaje"], r["id"], r["nombre"], r["categoria"], r["filas"], r["nivel_big_data"], r["dice_estado"],
                        r["dice_lugar"], r["dice_impacto"], " ".join(r["llaves"]), r["actualizado"], r["url"]])
    medidos = sum(1 for r in salida if r["filas"] is not None)
    tres = [r for r in salida if r["dice_estado"] and r["dice_lugar"] and r["dice_impacto"] and (r["nivel_big_data"] or 0) >= 1]
    print(f"Relevancia de {dominio}: {len(salida)} conjuntos, {medidos} con filas medidas; "
          f"{len(tres)} grandes que permiten decir estado, lugar e impacto")
    for r in salida[:top]:
        marca = "".join(s if r[k] else "·" for s, k in (("E", "dice_estado"), ("L", "dice_lugar"), ("I", "dice_impacto")))
        filas_txt = f"{r['filas']:,}".replace(",", ".") if r["filas"] is not None else "sin medir"
        print(f"  {r['puntaje']:>2} {marca} {r['id']} {filas_txt:>12}  {r['nombre'][:70]}")
    print("RESUMEN " + json.dumps({"conjuntos": len(salida), "medidos": medidos, "estado_lugar_impacto": len(tres)}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""Genera el ejemplo de ventas con trampas realistas y su respuesta correcta.

Uso: python3 generar_datos.py <carpeta_datos> <ruta_verdad.json>

Escribe ventas.csv y clientes.csv en <carpeta_datos> y, en <ruta_verdad.json>,
la respuesta correcta según el glosario (ejemplo/negocio.md), junto con lo que
mueve el resultado cada trampa si se maneja mal. Ningún agente debe ver ese archivo.

La respuesta correcta se calcula por dos caminos independientes (los documentos
limpios y la lectura de los CSV escritos) y el script se detiene si no coinciden.
"""
import csv
import json
import random
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

SEMILLA = 20261106
INICIO, FIN = date(2026, 1, 1), date(2026, 6, 30)        # primer semestre de 2026
VENTANA = (date(2025, 12, 1), date(2026, 7, 31))         # lo que trae la exportación
REGIONES = ["Antioquia", "Bogotá D.C.", "Caldas", "Risaralda", "Valle del Cauca"]
PESOS_REGION = [0.34, 0.26, 0.12, 0.10, 0.18]
VARIANTES = {
    "Antioquia": ["antioquia", "ANTIOQUIA", " Antioquia"],
    "Bogotá D.C.": ["Bogota D.C.", "Bogotá", "BOGOTA DC"],
    "Caldas": ["caldas", "CALDAS "],
    "Risaralda": ["risaralda"],
    "Valle del Cauca": ["Valle", "VALLE DEL CAUCA", "Valle del cauca"],
}
SIN_REGION = "Sin región"
N_CLIENTES = 60
N_CAMBIARON = 5           # clientes con dos registros en el maestro (cambio de región)
N_FV = 1400
N_NC = 90
N_REPETIDAS = 30          # filas exportadas dos veces, idénticas
N_HUERFANAS = 16          # código que no existe en el maestro
N_VACIAS = 6              # código vacío
N_VARIANTES_ID = 40       # " C017", "c017", "C017 "
PROP_FECHA_VIEJA = 0.30   # sistema viejo: dd/mm/aaaa


def fecha_azar(rng, desde, hasta):
    return desde + timedelta(days=rng.randrange((hasta - desde).days + 1))


def generar():
    rng = random.Random(SEMILLA)
    ids = [f"C{i:03d}" for i in range(1, N_CLIENTES + 1)]
    vigente = {cid: rng.choices(REGIONES, PESOS_REGION)[0] for cid in ids}
    cambiaron = sorted(rng.sample(ids, N_CAMBIARON))

    maestro = []
    for n, cid in enumerate(ids):
        reg = vigente[cid]
        escrito = reg if rng.random() < 0.7 else rng.choice(VARIANTES[reg])
        nombre = f"Distribuidora {cid[1:]} S.A.S."
        if cid in cambiaron:
            anterior = rng.choice([r for r in REGIONES if r != reg])
            vieja = {"cliente_id": cid, "nombre": nombre, "region": anterior,
                     "fecha_actualizacion": fecha_azar(rng, date(2023, 1, 1), date(2024, 12, 31)).isoformat()}
            nueva = {"cliente_id": cid, "nombre": nombre, "region": escrito,
                     "fecha_actualizacion": fecha_azar(rng, date(2025, 2, 1), date(2026, 4, 30)).isoformat()}
            # en 3 de los 5 el registro nuevo va primero: ni «quedarse con el primero»
            # ni «quedarse con el último» aciertan; solo ordenar por fecha_actualizacion
            pareja = [nueva, vieja] if cambiaron.index(cid) < 3 else [vieja, nueva]
            maestro.extend(pareja)
        else:
            maestro.append({"cliente_id": cid, "nombre": nombre, "region": escrito,
                            "fecha_actualizacion": fecha_azar(rng, date(2023, 1, 1), date(2025, 12, 31)).isoformat()})

    docs = []
    for k in range(1, N_FV + 1):
        sub = rng.randrange(800, 45001) * 100
        iva = 0 if rng.random() < 0.15 else round(sub * 0.19)
        docs.append({"numero": f"FV-{k:06d}", "tipo": "FV", "fecha": fecha_azar(rng, *VENTANA),
                     "cliente": rng.choice(ids), "escrito_id": None, "subtotal": sub, "iva": iva})
    for k in range(1, N_NC + 1):
        sub = rng.randrange(500, 15001) * 100
        iva = 0 if rng.random() < 0.15 else round(sub * 0.19)
        docs.append({"numero": f"NC-{k:06d}", "tipo": "NC", "fecha": fecha_azar(rng, *VENTANA),
                     "cliente": rng.choice(ids), "escrito_id": None, "subtotal": sub, "iva": iva})

    fvs = [d for d in docs if d["tipo"] == "FV"]
    elegidos = rng.sample(fvs, N_HUERFANAS + N_VACIAS + N_VARIANTES_ID)
    for d in elegidos[:N_HUERFANAS]:
        d["cliente"] = f"C9{rng.randrange(1, 6):02d}"      # C901..C905: no están en el maestro
    for d in elegidos[N_HUERFANAS:N_HUERFANAS + N_VACIAS]:
        d["cliente"] = ""
    for d in elegidos[N_HUERFANAS + N_VACIAS:]:
        cid = d["cliente"]
        d["escrito_id"] = rng.choice([" " + cid, cid.lower(), cid + " ", " " + cid.lower()])

    filas = []
    for d in docs:
        vieja = rng.random() < PROP_FECHA_VIEJA
        filas.append({
            "numero_documento": d["numero"],
            "tipo_documento": d["tipo"],
            "fecha": d["fecha"].strftime("%d/%m/%Y") if vieja else d["fecha"].isoformat(),
            "cliente_id": d["escrito_id"] if d["escrito_id"] is not None else d["cliente"],
            "subtotal": str(d["subtotal"]),
            "iva": str(d["iva"]),
            "total": str(d["subtotal"] + d["iva"]),
        })
    for f in rng.sample([f for f in filas if f["tipo_documento"] == "FV"], N_REPETIDAS):
        filas.append(dict(f))
    rng.shuffle(filas)
    return vigente, maestro, docs, filas


# ---------- camino 1: los documentos limpios ----------
def verdad_directa(vigente, docs):
    tot = defaultdict(int)
    for d in docs:
        if INICIO <= d["fecha"] <= FIN:
            region = vigente.get(d["cliente"], SIN_REGION) if d["cliente"] else SIN_REGION
            tot[region] += d["subtotal"] if d["tipo"] == "FV" else -d["subtotal"]
    return dict(tot)


# ---------- camino 2: leer los CSV escritos, con opciones para cada trampa ----------
def sin_tildes(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


ALIAS = {"bogota": "bogotadc", "valle": "valledelcauca"}
OFICIAL = {re.sub(r"[^0-9a-z]", "", sin_tildes(r).casefold()): r for r in REGIONES}


def unificar_region(texto):
    k = re.sub(r"[^0-9a-z]", "", sin_tildes(texto).casefold())
    return OFICIAL[ALIAS.get(k, k)]


def leer_fecha(texto, mes_primero=False, iso_invertida=False):
    if "-" in texto:
        a, m, d = map(int, texto.split("-"))
        if iso_invertida and d <= 12:     # pandas con dayfirst=True invierte las ISO ambiguas
            return date(a, d, m)
        return date(a, m, d)
    x, y, a = map(int, texto.split("/"))
    if mes_primero and x <= 12:         # como lee pandas una fecha con barras si no se le dice nada
        return date(a, x, y)
    return date(a, y, x)


CORRECTO = dict(iva=False, nc="restar", repetidas="una_vez", fechas="dia_primero", maestro="reciente",
                ids="normalizar", huerfanas="sin_region", regiones="unificar")


def interpretar(filas, registros_maestro, **cambios):
    op = {**CORRECTO, **cambios}
    norm = (lambda s: s.strip().upper()) if op["ids"] == "normalizar" else (lambda s: s)
    regiones_de = defaultdict(list)     # id -> [regiones] (más de una si el maestro no se depura)
    if op["maestro"] == "todos":
        for m in registros_maestro:
            regiones_de[norm(m["cliente_id"])].append(m["region"])
    else:
        elegido = {}
        for m in registros_maestro:
            k = norm(m["cliente_id"])
            if k not in elegido:
                elegido[k] = m
            elif op["maestro"] == "ultimo":
                elegido[k] = m
            elif op["maestro"] == "reciente" and m["fecha_actualizacion"] > elegido[k]["fecha_actualizacion"]:
                elegido[k] = m
        for k, m in elegido.items():
            regiones_de[k].append(m["region"])

    vistas, tot = set(), defaultdict(int)
    for f in filas:
        clave = tuple(f.values())
        if op["repetidas"] == "una_vez":
            if clave in vistas:
                continue
            vistas.add(clave)
        fecha = leer_fecha(f["fecha"], mes_primero=op["fechas"] == "mes_primero",
                           iso_invertida=op["fechas"] == "iso_invertida")
        if not (INICIO <= fecha <= FIN):
            continue
        monto = int(f["total"] if op["iva"] else f["subtotal"])
        if f["tipo_documento"] == "NC":
            if op["nc"] == "ignorar":
                continue
            if op["nc"] == "restar":
                monto = -monto
        regs = regiones_de.get(norm(f["cliente_id"])) if f["cliente_id"].strip() else None
        if not regs:
            if op["huerfanas"] == "descartar":
                continue
            regs = [SIN_REGION]
        for r in regs:
            r = r if r == SIN_REGION or op["regiones"] == "tal_cual" else unificar_region(r)
            tot[r] += monto
    return dict(tot)


ALTERNATIVAS = {
    "iva_incluido (usar total en vez de subtotal)": dict(iva=True),
    "notas_credito_sumadas": dict(nc="sumar"),
    "notas_credito_ignoradas": dict(nc="ignorar"),
    "filas_repetidas_contadas_dos_veces": dict(repetidas="todas"),
    "fechas_con_barras_leidas_mes_primero": dict(fechas="mes_primero"),
    "fechas_iso_invertidas (pandas dayfirst=True)": dict(fechas="iso_invertida"),
    "maestro_primer_registro_del_archivo": dict(maestro="primero"),
    "maestro_ultimo_registro_del_archivo": dict(maestro="ultimo"),
    "maestro_sin_depurar (la unión duplica ventas)": dict(maestro="todos"),
    "codigos_de_cliente_sin_normalizar": dict(ids="tal_cual"),
    "ventas_sin_cliente_descartadas": dict(huerfanas="descartar"),
    "regiones_sin_unificar": dict(regiones="tal_cual"),
}


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    carpeta, ruta_verdad = Path(sys.argv[1]), Path(sys.argv[2])
    carpeta.mkdir(parents=True, exist_ok=True)
    vigente, maestro, docs, filas = generar()

    with open(carpeta / "clientes.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["cliente_id", "nombre", "region", "fecha_actualizacion"])
        w.writeheader()
        w.writerows(maestro)
    with open(carpeta / "ventas.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["numero_documento", "tipo_documento", "fecha", "cliente_id",
                                           "subtotal", "iva", "total"])
        w.writeheader()
        w.writerows(filas)

    # releer lo escrito, para que el camino 2 parta del archivo real
    with open(carpeta / "ventas.csv", encoding="utf-8") as fh:
        filas_csv = list(csv.DictReader(fh))
    with open(carpeta / "clientes.csv", encoding="utf-8") as fh:
        maestro_csv = list(csv.DictReader(fh))

    directa = verdad_directa(vigente, docs)
    leida = interpretar(filas_csv, maestro_csv)
    if directa != leida:
        raise SystemExit(f"Los dos caminos no coinciden:\n{directa}\n{leida}")

    orden = REGIONES + [SIN_REGION]
    total = sum(directa.values())
    alternativas = {}
    for nombre, cambios in ALTERNATIVAS.items():
        r = interpretar(filas_csv, maestro_csv, **cambios)
        alternativas[nombre] = {"total": sum(r.values()), "cambio_en_el_total": sum(r.values()) - total,
                                "por_region": dict(sorted(r.items()))}

    en_periodo = [d for d in docs if INICIO <= d["fecha"] <= FIN]
    verdad = {
        "peticion": "Ventas totales por región del primer semestre de 2026",
        "resultado": [{"region": r, "ventas": directa[r]} for r in orden if r in directa],
        "total": total,
        "alternativas": alternativas,
        "conteos": {
            "filas_ventas_csv": len(filas_csv), "documentos_unicos": len(docs),
            "documentos_en_periodo": len(en_periodo), "filas_repetidas": N_REPETIDAS,
            "registros_maestro": len(maestro_csv), "clientes": len(vigente),
            "clientes_con_dos_registros": N_CAMBIARON,
        },
    }
    ruta_verdad.write_text(json.dumps(verdad, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Datos en {carpeta} · verdad en {ruta_verdad}")
    print(f"Total correcto: {total:,}".replace(",", "."))
    for nombre, a in alternativas.items():
        print(f"  {nombre:52s} cambia el total en {a['cambio_en_el_total']:>+15,}".replace(",", "."))


if __name__ == "__main__":
    main()

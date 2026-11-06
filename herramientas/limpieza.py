#!/usr/bin/env python3
"""Limpieza declarada (sin IA): del dato crudo a la capa limpia, marcando y sin borrar.

Uso: python limpieza.py <plan_limpieza.json>   (las rutas del plan son relativas a la carpeta del plan)

La IA escribe el plan; este motor lo ejecuta igual cada vez y lo prueba:
  - el dato crudo no se toca (capa cruda, con su procedencia);
  - la capa limpia tiene las mismas filas: limpiar es marcar (R14). Cada problema queda en una columna
    calidad_<marca> (1/0), y calidad_ok vale 1 si la fila no tiene marcas;
  - cada operación informa cuántas filas cambió y cuántas marcó, con ejemplos (nunca de columnas privadas);
  - completitud, validez y unicidad se miden antes y después, y los umbrales del plan bloquean.

Operaciones (en orden):
  {"op": "texto", "columna", "recortar": true, "unicode": true, "invisibles": true, "espacios_internos": true}
  {"op": "reemplazar", "columna", "patron": regex, "por": texto, "marca": opcional}
  {"op": "nulos_disfrazados", "columna", "valores": ["No Definido", "N/A", "-"], "marca"}
  {"op": "mapear", "columna", "mapa": {variante: oficial}, "normalizar_clave": true, "marca": "fuera_de_mapa"}
  {"op": "fecha", "columna", "formatos": ["%Y-%m-%d", "%d/%m/%Y"], "marca": "fecha_invalida"}   → aaaa-mm-dd (se guarda la hora aparte si viene)
  {"op": "numero", "columna", "decimal": "." , "marca": "numero_invalido"}
  {"op": "rango", "columna", "min", "max", "marca"}                 marca, no corrige (R7)
  {"op": "atipicos", "columna", "k": 3, "marca"}                    rango intercuartílico sobre log10 de los positivos
  {"op": "repetidos", "columnas": [...] o "fila_completa", "marca": "repetido"}   marca desde la segunda aparición
  {"op": "comparar", "izquierda", "operador": "<", "derecha", "marca"}             p. ej. fin antes de inicio
Umbrales: {"completitud_minima": {col: 0.99}, "validez_minima": {col: 0.999}, "unicidad": [col], "marcadas_maximo": {marca: n}}
"""
import csv
import hashlib
import io
import json
import math
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gobernanza import clasificar_columna, enmascarar  # noqa: E402

INVISIBLES = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f​-‏  ‪-‮⁠﻿]")
OPS = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
       "==": lambda a, b: a == b, "!=": lambda a, b: a != b}


def clave_norm(s):
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^0-9a-z]", "", s.casefold())


def privada(col):
    return clasificar_columna(col) in ("personal", "texto_libre")


def ejemplo(col, antes, despues):
    if privada(col):
        return f"{enmascarar(antes)} → {enmascarar(despues)}"
    return f"«{antes[:40]}» → «{despues[:40]}»"


def leer_fecha(v, formatos):
    for f in formatos:
        try:
            return datetime.strptime(v, f)
        except ValueError:
            continue
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", v):
        try:
            return datetime.fromisoformat(v[:19])
        except ValueError:
            return None
    return None


def metricas(filas, cols, tipos):
    out = {}
    n = len(filas) or 1
    for c in cols:
        vals = [f.get(c, "") for f in filas]
        llenos = [v for v in vals if v.strip()]
        m = {"completitud": round(len(llenos) / n, 6), "distintos": len(set(llenos))}
        t = tipos.get(c)
        if t == "fecha":
            m["validez"] = round(sum(1 for v in llenos if re.match(r"^\d{4}-\d{2}-\d{2}$", v)) / (len(llenos) or 1), 6)
        elif t == "numero":
            def ok(v):
                try:
                    return math.isfinite(float(v))
                except ValueError:
                    return False
            m["validez"] = round(sum(1 for v in llenos if ok(v)) / (len(llenos) or 1), 6)
        out[c] = m
    return out


def limpiar(plan_ruta, entrada=None, salida=None, informe=True):
    plan_ruta = Path(plan_ruta).resolve()
    base = plan_ruta.parent
    plan = json.loads(plan_ruta.read_text(encoding="utf-8"))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from rutas import resolver
    e = entrada or plan["entrada"]
    ent = Path(resolver(e)) if Path(e).is_absolute() else base / e
    s_ = salida or plan["salida"]
    sal = Path(s_) if Path(s_).is_absolute() else base / s_
    with open(ent, newline="", encoding="utf-8-sig") as fh:
        lector = csv.DictReader(fh, strict=True)
        cols = list(lector.fieldnames or [])
        crudas = list(lector)
    huella_cruda = hashlib.sha256(ent.read_bytes()).hexdigest()
    filas = [dict(f) for f in crudas]
    marcas = [set() for _ in filas]
    tipos = {o["columna"]: o["op"] for o in plan["operaciones"] if o.get("op") in ("fecha", "numero")}
    antes = metricas(crudas, cols, {})
    reporte = []

    for o in plan["operaciones"]:
        op, col = o["op"], o.get("columna")
        if col and col not in cols:
            raise SystemExit(f"La operación {op} usa la columna {col}, que no existe (R1)")
        cambiadas, marcadas, ej = 0, 0, []

        def cambia(i, nuevo):
            nonlocal cambiadas
            viejo = filas[i][col]
            if nuevo != viejo:
                cambiadas += 1
                if len(ej) < 3:
                    ej.append(ejemplo(col, viejo, nuevo))
                filas[i][col] = nuevo

        def marca(i, m):
            nonlocal marcadas
            if m not in marcas[i]:
                marcas[i].add(m)
                marcadas += 1

        if op == "texto":
            for i, f in enumerate(filas):
                v = f[col]
                if o.get("invisibles", True):
                    v = INVISIBLES.sub("", v)
                if o.get("unicode", True):
                    v = unicodedata.normalize("NFC", v)
                if o.get("espacios_internos", True):
                    v = re.sub(r"\s+", " ", v)
                if o.get("recortar", True):
                    v = v.strip()
                if o.get("mayusculas"):
                    v = v.upper()
                cambia(i, v)
        elif op == "reemplazar":
            rx = re.compile(o["patron"])
            for i, f in enumerate(filas):
                nuevo = rx.sub(o.get("por", ""), f[col]).strip()
                if nuevo != f[col] and o.get("marca"):
                    marca(i, o["marca"])
                cambia(i, nuevo)
        elif op == "nulos_disfrazados":
            disfraz = {clave_norm(x) for x in o["valores"]}
            for i, f in enumerate(filas):
                if f[col].strip() and clave_norm(f[col]) in disfraz:
                    marca(i, o.get("marca", f"nulo_disfrazado_{col}"))
                    cambia(i, "")
        elif op == "mapear":
            norm = o.get("normalizar_clave", True)
            mapa = {(clave_norm(k) if norm else k): v for k, v in o["mapa"].items()}
            fuera = {}
            for i, f in enumerate(filas):
                v = f[col]
                if not v.strip():
                    continue
                k = clave_norm(v) if norm else v
                if k in mapa:
                    cambia(i, mapa[k])
                else:
                    marca(i, o.get("marca", f"fuera_de_mapa_{col}"))
                    fuera[v] = fuera.get(v, 0) + 1
            if fuera:
                ej.append(f"sin mapear: {list(fuera)[:5] if not privada(col) else len(fuera)}")
        elif op == "fecha":
            formatos = o.get("formatos", ["%Y-%m-%d"])
            hora = f"{col}__hora"
            for i, f in enumerate(filas):
                v = f[col].strip()
                if not v:
                    continue
                d = leer_fecha(v, formatos)
                if d is None:
                    marca(i, o.get("marca", f"fecha_invalida_{col}"))
                    continue
                if o.get("guardar_hora") and (d.hour or d.minute or d.second):
                    f[hora] = d.strftime("%H:%M:%S")
                cambia(i, d.strftime("%Y-%m-%d"))
            if o.get("guardar_hora") and hora not in cols:
                cols.append(hora)
                for f in filas:
                    f.setdefault(hora, "")
        elif op == "numero":
            for i, f in enumerate(filas):
                v = f[col].strip()
                if not v:
                    continue
                if o.get("decimal") == ",":
                    v = v.replace(".", "").replace(",", ".")
                try:
                    x = float(v)
                    if not math.isfinite(x):
                        raise ValueError
                    cambia(i, v)
                except ValueError:
                    marca(i, o.get("marca", f"numero_invalido_{col}"))
        elif op == "rango":
            lo, hi = o.get("min"), o.get("max")
            for i, f in enumerate(filas):
                v = f[col].strip()
                if not v:
                    continue
                try:
                    x = v if tipos.get(col) == "fecha" else float(v)
                except ValueError:
                    continue
                if (lo is not None and x < lo) or (hi is not None and x > hi):
                    marca(i, o["marca"])
        elif op == "atipicos":
            logs = []
            for f in filas:
                try:
                    x = float(f[col])
                    if x > 0:
                        logs.append(math.log10(x))
                except ValueError:
                    pass
            logs.sort()
            if len(logs) >= 20:
                q1, q3 = logs[len(logs) // 4], logs[(3 * len(logs)) // 4]
                k = float(o.get("k", 3))
                bajo, alto = q1 - k * (q3 - q1), q3 + k * (q3 - q1)
                for i, f in enumerate(filas):
                    try:
                        x = float(f[col])
                    except ValueError:
                        continue
                    if x > 0 and not (bajo <= math.log10(x) <= alto):
                        marca(i, o["marca"])
                ej.append(f"límites: {10 ** bajo:,.0f} a {10 ** alto:,.0f}".replace(",", "."))
        elif op == "repetidos":
            claves = cols if o.get("columnas") == "fila_completa" else o["columnas"]
            vistos = set()
            for i, f in enumerate(filas):
                k = tuple(f.get(c, "").strip().upper() for c in claves)
                if k in vistos:
                    marca(i, o.get("marca", "repetido"))
                vistos.add(k)
        elif op == "comparar":
            fn = OPS[o["operador"]]
            for i, f in enumerate(filas):
                a, b = f.get(o["izquierda"], "").strip(), f.get(o["derecha"], "").strip()
                if a and b:
                    try:
                        a2, b2 = (float(a), float(b)) if tipos.get(o["izquierda"]) == "numero" else (a, b)
                    except ValueError:
                        continue
                    if fn(a2, b2):
                        marca(i, o["marca"])
        else:
            raise SystemExit(f"Operación desconocida: {op}")
        reporte.append({"op": op, "columna": col or o.get("columnas") or f"{o.get('izquierda')} {o.get('operador')} {o.get('derecha')}",
                        "filas_cambiadas": cambiadas, "filas_marcadas": marcadas, "ejemplos": ej, "marca": o.get("marca")})

    todas = sorted({m for ms in marcas for m in ms})
    salida_cols = cols + [f"calidad_{m}" for m in todas] + ["calidad_ok"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=salida_cols, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    for f, ms in zip(filas, marcas):
        fila = dict(f)
        for m in todas:
            fila[f"calidad_{m}"] = int(m in ms)
        fila["calidad_ok"] = int(not ms)
        w.writerow(fila)
    contenido = buf.getvalue().encode("utf-8")
    sal.parent.mkdir(parents=True, exist_ok=True)
    sal.write_bytes(contenido)
    despues = metricas(filas, cols, tipos)

    pruebas = [
        {"prueba": "limpiar es marcar: mismas filas antes y después", "ok": len(filas) == len(crudas),
         "detalle": f"{len(crudas)} → {len(filas)}"},
        {"prueba": "el dato crudo no se tocó", "ok": hashlib.sha256(ent.read_bytes()).hexdigest() == huella_cruda,
         "detalle": f"sha256 {huella_cruda[:16]}…"},
    ]
    llave = plan.get("llave")
    if llave:
        orden_ok = [f.get(llave) for f in filas] == [f.get(llave) for f in crudas]
        pruebas.append({"prueba": "la llave y el orden de las filas se conservan", "ok": orden_ok,
                        "detalle": "cada fila limpia corresponde a su fila cruda"})
    u = plan.get("umbrales", {})
    for c, mn in u.get("completitud_minima", {}).items():
        v = despues.get(c, {}).get("completitud", 0)
        pruebas.append({"prueba": f"completitud de {c} ≥ {mn}", "ok": v >= mn, "detalle": f"{v:.4%}"})
    for c, mn in u.get("validez_minima", {}).items():
        v = despues.get(c, {}).get("validez")
        pruebas.append({"prueba": f"validez de {c} ≥ {mn}", "ok": v is not None and v >= mn,
                        "detalle": "sin tipo declarado" if v is None else f"{v:.4%}"})
    for c in u.get("unicidad", []):
        vals = [f[c] for f in filas if f.get(c, "").strip()]
        pruebas.append({"prueba": f"{c} única", "ok": len(vals) == len(set(vals)), "detalle": f"{len(vals) - len(set(vals))} repetidas"})
    for m, mx in u.get("marcadas_maximo", {}).items():
        n = sum(1 for ms in marcas if m in ms)
        pruebas.append({"prueba": f"filas marcadas «{m}» ≤ {mx}", "ok": n <= mx, "detalle": f"{n}"})
    conteo_marcas = {m: sum(1 for ms in marcas if m in ms) for m in todas}
    informe_escribir = informe
    informe = {"tabla": plan.get("tabla"), "entrada": str(ent), "salida": str(sal), "filas": len(filas),
               "filas_ok": sum(1 for ms in marcas if not ms), "marcas": conteo_marcas, "operaciones": reporte,
               "calidad_antes": antes, "calidad_despues": despues, "pruebas": pruebas,
               "sha256_limpio": hashlib.sha256(contenido).hexdigest(),
               "estado": "aprobada" if all(p["ok"] for p in pruebas) else "rechazada"}
    if not informe_escribir:
        return informe
    (base / f"limpieza_{plan.get('tabla', 'tabla')}.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Limpieza {informe['estado']}: {len(filas)} filas → {sal} · sin marcas {informe['filas_ok']}")
    for r in reporte:
        print(f"  · {r['op']} {r['columna']}: cambiadas {r['filas_cambiadas']} · marcadas {r['filas_marcadas']}"
              + (f" · {'; '.join(r['ejemplos'][:2])}" if r["ejemplos"] else ""))
    for p in pruebas:
        print(f"  {'✓' if p['ok'] else '✗'} {p['prueba']}: {p['detalle']}")
    print("RESUMEN " + json.dumps({"estado": informe["estado"], "filas": len(filas), "marcas": conteo_marcas,
                                   "fallas": [p["prueba"] for p in pruebas if not p["ok"]]}, ensure_ascii=False))
    return 0 if informe["estado"] == "aprobada" else 1


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__)
    g = lambda k: args[args.index(k) + 1] if k in args else None
    sys.exit(limpiar(args[0], entrada=g("--entrada"), salida=g("--salida")))

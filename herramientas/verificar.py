#!/usr/bin/env python3
"""Verificación determinista de una corrida (sin IA).

Uso:
  python verificar.py <corrida>                verifica impl_a.py e impl_b.py; escribe informe.json e informe.md
  python verificar.py <corrida> --autoprueba   corre las reglas sobre el caso conocido con su resultado esperado
  python verificar.py <corrida> --sellar       guarda las huellas de spec.json, reglas.py y caso_conocido/
  python verificar.py <corrida> --impl nombre=ruta.py [nombre=ruta.py ...]
                                               verifica otras implementaciones (escribe informe_extra.json)

Una corrida es una carpeta con:
  spec.json                 lo que debe salir (la escribe el especificador)
  reglas.py                 las reglas ejecutables (usa herramientas/reglas_base.py)
  caso_conocido/<tabla>.csv datos pequeños hechos a mano, y caso_conocido/esperado.json
  impl_a.py, impl_b.py      dos implementaciones independientes de analizar(datos) -> list[dict]
"""
import csv
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import dependencias  # noqa: E402
import seguridad  # noqa: E402
from rutas import resolver_datos  # noqa: E402

TIEMPO_IMPL = 300
TIEMPO_REGLA = 120
MARCA = "<<<RESULTADO-VERIFICAR>>>"
CAJA = shutil.which("sandbox-exec")
RUNNER = r'''
import importlib.util, json, math, os, sys
ruta, datos = sys.argv[1], json.loads(sys.argv[2])
sys.path.insert(0, os.path.dirname(os.path.abspath(ruta)))
import types
mod = types.ModuleType("impl_bajo_prueba"); mod.__file__ = ruta
exec(compile(open(ruta, encoding="utf-8").read(), ruta, "exec"), mod.__dict__)   # desde la fuente sellada, sin .pyc
conc = mod.conciliar(datos) if hasattr(mod, "conciliar") else None
res = mod.analizar(datos)
try:
    import pandas as pd
    if isinstance(res, pd.DataFrame):
        res = res.to_dict(orient="records")
except ImportError:
    pass
if isinstance(res, dict):
    raise TypeError("analizar debe devolver una lista de filas (list[dict]), no un dict")
def limpio(v):
    if hasattr(v, "item") and not isinstance(v, (str, bytes)):
        try:
            v = v.item()
        except Exception:
            pass
    if isinstance(v, float) and math.isnan(v):
        return None
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    return str(v)
filas = [{str(k): limpio(v) for k, v in dict(f).items()} for f in res]
if conc is not None:
    conc = json.loads(json.dumps(conc, default=lambda v: v.item() if hasattr(v, "item") else str(v)))
print("MARCA" + json.dumps({"filas": filas, "conciliacion": conc}, ensure_ascii=False))
'''.replace("MARCA", MARCA)


# ---------------- carga ----------------
def cargar_spec(c):
    ruta = c / "spec.json"
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta}")
    spec = json.loads(ruta.read_text(encoding="utf-8"))
    faltan = [k for k in ("datos", "salida") if k not in spec]
    if "datos" in spec:
        resolver_datos(spec)
    if spec.get("datos_crudos"):
        from rutas import resolver
        spec["datos_crudos"] = {k: resolver(r) for k, r in spec["datos_crudos"].items()}
    if faltan:
        raise SystemExit(f"spec.json no tiene: {', '.join(faltan)}")
    for k in ("claves", "valores"):
        if not spec["salida"].get(k):
            raise SystemExit(f"spec.json: salida.{k} está vacío")
    for tabla, ruta_csv in spec["datos"].items():
        if not Path(ruta_csv).exists():
            raise SystemExit(f"spec.json: la tabla {tabla} apunta a {ruta_csv}, que no existe")
    return spec


RUNNER_REGLAS = r'''
import json, math, re, signal, sys, types
ruta, modo, herr = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, herr)
import reglas_base
mod = types.ModuleType("reglas_corrida"); mod.__file__ = ruta
exec(compile(open(ruta, encoding="utf-8").read(), ruta, "exec"), mod.__dict__)   # desde la fuente sellada
reglas = list(reglas_base.REGLAS) or list(getattr(mod, "REGLAS", []) or [])
def sanear(t):
    t = re.sub(r"'[^']*'", "'•••'", str(t)); t = re.sub(r'"[^"]*"', '"•••"', t)
    return t[:300]
if modo == "listar":
    out = [{"id": r["id"], "tipo": r["tipo"], "descripcion": r["descripcion"]} for r in reglas]
else:
    d = json.loads(sys.stdin.read())
    class T(Exception): pass
    def alarma(*_): raise T()
    signal.signal(signal.SIGALRM, alarma)
    out = []
    for r in reglas:
        signal.alarm(TIEMPO)
        try:
            s = r["fn"](dict(d["datos"]), [dict(f) for f in d["resultado"]])
            ok, msg = (bool(s[0]), str(s[1]) if len(s) > 1 else "") if isinstance(s, tuple) else (bool(s), "")
            out.append({"id": r["id"], "estado": "pasa" if ok else "falla", "mensaje": msg[:600]})
        except T:
            out.append({"id": r["id"], "estado": "error", "mensaje": "la regla tardó más de TIEMPO s"})
        except Exception as e:
            out.append({"id": r["id"], "estado": "error", "mensaje": f"{type(e).__name__}: {sanear(e)}"})
        finally:
            signal.alarm(0)
print("MARCA" + json.dumps(out, ensure_ascii=False))
'''


def cargar_reglas(c):
    """Las reglas también las escribe la IA: pasan por las compuertas y se ejecutan en la caja de arena,
    nunca dentro del proceso del verificador."""
    ruta = c / "reglas.py"
    if not ruta.exists():
        return [], ["no existe reglas.py"]
    bloqueos = compuertas(ruta)
    if bloqueos:
        return [], [f"reglas.py no pasa las compuertas: {b}" for b in bloqueos]
    import caja
    lista, err = caja.correr(RUNNER_REGLAS.replace("MARCA", caja.MARCA).replace("TIEMPO", str(TIEMPO_REGLA)),
                             str(ruta), "listar", str(AQUI))
    if err:
        return [], [f"reglas.py no carga: {sanear(err)}"]
    reglas = [{**r, "ruta": str(ruta)} for r in lista]
    ids = [r["id"] for r in reglas]
    problemas = [f"id de regla repetido: {i}" for i in sorted(set(ids)) if ids.count(i) > 1]
    return reglas, problemas


def correr_reglas(reglas, datos, resultado):
    """Corre todas las reglas en la caja de arena; el resultado entra por la entrada estándar."""
    if not reglas:
        return []
    import caja
    salida, err = caja.correr(RUNNER_REGLAS.replace("MARCA", caja.MARCA).replace("TIEMPO", str(TIEMPO_REGLA)),
                              reglas[0]["ruta"], "correr", str(AQUI), tiempo=TIEMPO_REGLA * max(1, len(reglas)),
                              entrada=json.dumps({"datos": datos, "resultado": resultado}, ensure_ascii=False))
    if err:
        return [{"id": r["id"], "estado": "error", "mensaje": f"las reglas no corrieron: {sanear(err)}"} for r in reglas]
    return salida


def sanear(t):
    """Los mensajes de error no copian el texto de las celdas a las salidas publicadas."""
    t = re.sub(r"'[^']*'", "'•••'", str(t))
    return re.sub(r'"[^"]*"', '"•••"', t)[:300]


def cargar_caso(c, spec):
    carpeta = c / "caso_conocido"
    esperado = carpeta / "esperado.json"
    if not esperado.exists():
        return None, "no existe caso_conocido/esperado.json"
    datos = {}
    for tabla in spec["datos"]:
        ruta = carpeta / f"{tabla}.csv"
        if not ruta.exists():
            return None, f"falta caso_conocido/{tabla}.csv"
        datos[tabla] = str(ruta)
    caso = {"datos": datos, "datos_crudos": dict(datos), "esperado": json.loads(esperado.read_text(encoding="utf-8"))}
    # si la corrida tiene capa limpia, el caso conocido pasa por el MISMO plan de limpieza antes de la implementación
    planes = {p.stem.replace("plan_limpieza_", ""): p for p in c.glob("plan_limpieza_*.json")}
    if planes and spec.get("datos_crudos"):
        import limpieza
        destino = c / "caso_conocido" / "_limpio"
        for tabla, plan in planes.items():
            if tabla in datos:
                inf = limpieza.limpiar(plan, entrada=datos[tabla], salida=str(destino / f"{tabla}.csv"), informe=False)
                if inf.get("estado") != "aprobada":
                    return None, f"el caso conocido no pasa la limpieza de {tabla}: {[p['prueba'] for p in inf['pruebas'] if not p['ok']]}"
                caso["datos"][tabla] = str(destino / f"{tabla}.csv")
    return caso, None


# ---------------- sellos ----------------
def archivos_sellados(c):
    rutas = [c / "spec.json", c / "reglas.py"] + sorted(c.glob("plan_limpieza_*.json"))
    carpeta = c / "caso_conocido"
    if carpeta.exists():
        rutas += sorted(p for p in carpeta.rglob("*") if p.is_file() and "_limpio" not in p.parts)
    return rutas


def huellas(c):
    return {str(p.relative_to(c)): hashlib.sha256(p.read_bytes()).hexdigest() for p in archivos_sellados(c) if p.exists()}


def revisar_sellos(c):
    ruta = c / "sellos.json"
    if not ruta.exists():
        return {"estado": "sin_sellar", "cambios": []}
    antes = json.loads(ruta.read_text(encoding="utf-8"))
    ahora = huellas(c)
    cambios = sorted(k for k in set(antes) | set(ahora) if antes.get(k) != ahora.get(k))
    return {"estado": "alterados" if cambios else "intactos", "cambios": cambios}


def sellar(c):
    ruta = c / "sellos.json"
    ahora = huellas(c)
    if ruta.exists():
        antes = json.loads(ruta.read_text(encoding="utf-8"))
        if antes == ahora:
            print("Ya estaba sellada con estas mismas huellas.")
            return 0
        print("La corrida ya está sellada y los archivos cambiaron. Cambiar el criterio es una decisión "
              "humana: si es intencional, borra sellos.json a mano y vuelve a sellar.")
        return 1
    ruta.write_text(json.dumps(ahora, indent=2), encoding="utf-8")
    print(f"Sellada: {len(ahora)} archivos.")
    return 0


# ---------------- ejecución ----------------
def ejecutar_impl(ruta, datos, detalle=False):
    """Corre analizar(datos) en otro proceso, dentro de la caja de arena (herramientas/caja.py): sin red, sin
    escribir, sin leer la carpeta personal, sin las variables de entorno del verificador y con topes de tiempo y
    memoria. Devuelve (filas, error) o, con detalle=True, (filas, error, conciliacion, segundos)."""
    import caja
    lecturas = [Path(str(v)).resolve().parent for v in datos.values()] + [Path(ruta).resolve().parent]
    so, se, motivo, seg = caja.ejecutar(["-c", RUNNER, str(ruta), json.dumps(datos)], TIEMPO_IMPL, lecturas=lecturas)
    if motivo:
        out = (None, motivo, None, seg)
        return out if detalle else out[:2]
    for linea in reversed(so.splitlines()):
        if linea.startswith(MARCA):
            d = json.loads(linea[len(MARCA):])
            out = (d["filas"], None, d.get("conciliacion"), seg)
            return out if detalle else out[:2]
    err = (se.strip().splitlines() or ["terminó sin devolver resultado"])[-1]
    out = (None, f"falló al ejecutarse: {sanear(err)}", None, seg)
    return out if detalle else out[:2]


def compuertas(ruta):
    """Seguridad y librerías ANTES de ejecutar: si algo bloquea, el código no corre."""
    fallas = []
    dep = dependencias.revisar(ruta)
    if dep.get("error"):
        fallas.append(f"no se puede leer el código: {dep['error']}")
    if dep.get("no_permitidas"):
        fallas.append(f"librerías no permitidas (posible paquete inventado): {dep['no_permitidas']}")
    if dep.get("intenta_instalar"):
        fallas.append(f"intenta instalar paquetes desde el código: {dep['intenta_instalar']}")
    seg, _ = seguridad.revisar([ruta])
    for h in seg[0]["bloquean"][:5]:
        fallas.append(f"seguridad, línea {h['linea']}: {h['regla']} ({h['detalle']})")
    return fallas


def revisar_conciliacion(conc):
    """R3 y R5 del curso: toda fila leída se usa o se excluye con su motivo; nada se borra en silencio."""
    if not isinstance(conc, dict):
        return "conciliar(datos) no devolvió un diccionario"
    try:
        leidas, usadas = int(conc["filas_leidas"]), int(conc["usadas"])
        excl = {k: int(v) for k, v in (conc.get("excluidas") or {}).items()}
    except (KeyError, TypeError, ValueError) as e:
        return f"conciliación incompleta: falta {e}"
    if leidas != usadas + sum(excl.values()):
        return f"no cierra: leídas {leidas} ≠ usadas {usadas} + excluidas {sum(excl.values())} {excl}"
    return None


class _Tiempo(Exception):
    pass


def _alarma(*_):
    raise _Tiempo()


def correr_regla(r, datos, resultado):
    signal.signal(signal.SIGALRM, _alarma)
    signal.alarm(TIEMPO_REGLA)
    try:
        salida = r["fn"](dict(datos), [dict(f) for f in resultado])
        if isinstance(salida, tuple):
            ok, msg = bool(salida[0]), (str(salida[1]) if len(salida) > 1 else "")
        else:
            ok, msg = bool(salida), ""
        return {"estado": "pasa" if ok else "falla", "mensaje": msg}
    except _Tiempo:
        return {"estado": "error", "mensaje": f"la regla tardó más de {TIEMPO_REGLA} s"}
    except Exception as e:
        return {"estado": "error", "mensaje": f"{type(e).__name__}: {e}"}
    finally:
        signal.alarm(0)


def a_num(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v))
    except ValueError:
        return None


def revisar_forma(resultado, claves, valores):
    problemas = []
    if not isinstance(resultado, list) or not resultado:
        return ["el resultado está vacío"]
    for i, f in enumerate(resultado):
        falta = [c for c in claves + valores if c not in f]
        if falta:
            problemas.append(f"la fila {i} no tiene {', '.join(falta)}")
        for v in valores:
            if v in f and (a_num(f[v]) is None or not math.isfinite(a_num(f[v]))):
                problemas.append(f"la fila {i}: {v} no es un número finito")
        if len(problemas) >= 5:
            break
    return problemas


def comparar(x, y, claves, valores, tol):
    def indexar(res):
        idx, rep = {}, []
        for f in res:
            k = tuple(str(f.get(c, "")).strip() for c in claves)
            if k in idx:
                rep.append(list(k))
            idx[k] = f
        return idx, rep
    ix, rx = indexar(x)
    iy, ry = indexar(y)
    difs = []
    for k in sorted(set(ix) & set(iy)):
        for v in valores:
            a, b = a_num(ix[k].get(v)), a_num(iy[k].get(v))
            if a is None or b is None or abs(a - b) > tol:
                difs.append({"clave": list(k), "columna": v, "primero": a, "segundo": b})
    out = {"solo_en_primero": [list(k) for k in sorted(set(ix) - set(iy))],
           "solo_en_segundo": [list(k) for k in sorted(set(iy) - set(ix))],
           "diferencias": difs[:50], "claves_repetidas_primero": rx, "claves_repetidas_segundo": ry}
    out["ok"] = not (out["solo_en_primero"] or out["solo_en_segundo"] or difs or rx or ry)
    return out


def describir_comparacion(cmp, primero, segundo):
    partes = []
    if cmp["solo_en_primero"]:
        partes.append(f"solo en {primero}: {cmp['solo_en_primero'][:5]}")
    if cmp["solo_en_segundo"]:
        partes.append(f"solo en {segundo}: {cmp['solo_en_segundo'][:5]}")
    for d in cmp["diferencias"][:5]:
        partes.append(f"{'/'.join(d['clave'])}.{d['columna']}: {primero} {fmt(d['primero'])} · {segundo} {fmt(d['segundo'])}")
    if cmp["claves_repetidas_primero"] or cmp["claves_repetidas_segundo"]:
        partes.append(f"claves repetidas: {(cmp['claves_repetidas_primero'] + cmp['claves_repetidas_segundo'])[:5]}")
    return "; ".join(partes)


def evaluar_impl(nombre, ruta, spec, reglas, caso):
    claves, valores = spec["salida"]["claves"], spec["salida"]["valores"]
    tol = float(spec["salida"].get("tolerancia", 0.5))
    try:
        ruta_rel = str(Path(ruta).resolve().relative_to(AQUI.parent))
    except ValueError:
        ruta_rel = Path(ruta).name
    r = {"ruta": ruta_rel, "fallas": [], "reglas": [], "reglas_con_error": []}
    if not Path(ruta).exists():
        r["fallas"].append(f"no existe {ruta}")
        return r
    r["compuertas"] = compuertas(ruta)
    if r["compuertas"]:
        r["fallas"] += r["compuertas"]
        r["resultado"] = None
        return r              # el código que no pasa las compuertas no se ejecuta
    resultado, err, conc, seg = ejecutar_impl(ruta, spec["datos"], detalle=True)
    r["resultado"], r["conciliacion"], r["segundos"] = resultado, conc, seg
    if not err:
        segundo, err2 = ejecutar_impl(ruta, spec["datos"])
        r["repetible"] = segundo == resultado
        if not r["repetible"]:
            r["fallas"].append("correr dos veces no da lo mismo (R12): el resultado cambió entre corridas"
                               + (f" ({err2})" if err2 else ""))
        if conc is None:
            if spec.get("conciliacion_requerida", False):
                r["fallas"].append("falta conciliar(datos): las filas leídas, usadas y excluidas por motivo (R3, R5)")
        else:
            problema = revisar_conciliacion(conc)
            if problema:
                r["fallas"].append(f"conciliación: {problema}")
    if err:
        r["fallas"].append(f"no se pudo ejecutar con los datos reales: {err}")
    else:
        forma = revisar_forma(resultado, claves, valores)
        if forma:
            r["fallas"].append("forma del resultado: " + "; ".join(forma))
        else:
            por_id = {x["id"]: x for x in correr_reglas(reglas, spec.get("datos_crudos") or spec["datos"], resultado)}
            for rg in reglas:
                res_r = por_id.get(rg["id"], {"estado": "error", "mensaje": "la regla no devolvió resultado"})
                out = {"id": rg["id"], "tipo": rg["tipo"], "descripcion": rg["descripcion"],
                       "estado": res_r["estado"], "mensaje": res_r.get("mensaje", "")}
                r["reglas"].append(out)
                if out["estado"] == "falla":
                    r["fallas"].append(f"regla {rg['id']} ({rg['tipo']}) no pasa: {out['mensaje']}")
                elif out["estado"] == "error":
                    r["reglas_con_error"].append(f"{rg['id']}: {out['mensaje']}")
    if caso:
        rc, errc = ejecutar_impl(ruta, caso["datos"])
        if errc:
            r["caso_conocido"] = {"ok": False, "error": errc}
            r["fallas"].append(f"no se pudo ejecutar con el caso conocido: {errc}")
        else:
            cmp = comparar(rc, caso["esperado"], claves, valores, tol)
            cmp["obtenido"] = rc
            r["caso_conocido"] = cmp
            if not cmp["ok"]:
                r["fallas"].append("caso con respuesta conocida no coincide: "
                                   + describir_comparacion(cmp, "obtenido", "esperado"))
    return r


# ---------------- informe ----------------
def fmt(v):
    if v is None:
        return "—"
    if isinstance(v, (int, float)):
        if float(v).is_integer():
            return f"{v:,.0f}".replace(",", ".")
        return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return str(v)


def tabla_md(filas, columnas):
    L = ["| " + " | ".join(columnas) + " |", "|" + "|".join("---" for _ in columnas) + "|"]
    for f in filas:
        L.append("| " + " | ".join(fmt(f.get(c)).replace("|", "\\|").replace("\n", " ") for c in columnas) + " |")
    return "\n".join(L)


def icono(estado):
    return {"pasa": "✅", "falla": "❌", "error": "⚠️"}.get(estado, "—")


def informe_md(spec, inf):
    claves, valores = spec["salida"]["claves"], spec["salida"]["valores"]
    L = [f"# {spec.get('peticion', 'Petición')}", ""]
    if inf["estado"] == "aprobado":
        L.append("**Estado: ✅ aprobado.** Las dos implementaciones pasan todas las reglas, aciertan el caso con "
                 "respuesta conocida y dan exactamente lo mismo.")
    else:
        L.append("**Estado: ⚠️ revisar.** No se debe usar la cifra hasta resolver esto:")
        L += [f"- {m}" for m in inf["motivos"]]
    preguntas = spec.get("preguntas", [])
    if preguntas:
        L += ["", f"> Hay {len(preguntas)} pregunta(s) abierta(s). El resultado usa el valor por defecto de cada una; "
                  "confírmalas en la sección «Preguntas abiertas»."]
    L += ["", "## Resultado"]
    if inf.get("resultado_oficial"):
        filas = inf["resultado_oficial"]
        L.append(tabla_md(filas, claves + valores))
        tot = {v: sum(a_num(f.get(v)) or 0 for f in filas) for v in valores}
        L.append("| **Total** | " + " | ".join([""] * (len(claves) - 1) + [f"**{fmt(tot[v])}**" for v in valores]) + " |")
        L.append(f"\n_Fuente: implementación {inf['fuente_resultado'].upper()}._")
    else:
        L.append("Ninguna implementación pasó todas las comprobaciones; no hay resultado confiable.")
    L += ["", "## Lo que se entendió", spec.get("interpretacion", "—")]
    if spec.get("definiciones"):
        L += ["", "## Definiciones y de dónde sale cada una",
              tabla_md(spec["definiciones"], ["termino", "definicion", "fuente"])]
    if spec.get("tratamiento_de_datos"):
        L += ["", "## Tratamiento de los datos"]
        for t in spec["tratamiento_de_datos"]:
            if isinstance(t, dict):
                L.append(f"- **{t.get('hallazgo', '')}** → {t.get('tratamiento', '')} _(fuente: {t.get('fuente', '—')})_")
            else:
                L.append(f"- {t}")
    if spec.get("supuestos"):
        L += ["", "## Supuestos (confírmalos)",
              tabla_md(spec["supuestos"], ["id", "decision", "alternativa", "impacto"])]
    L += ["", "## Preguntas abiertas"]
    if preguntas:
        L += [f"- **{p.get('id', '')}** {p.get('pregunta', '')} — por defecto: _{p.get('por_defecto', '—')}_. "
              f"{p.get('por_que_importa', '')}" for p in preguntas]
    else:
        L.append("Ninguna: el glosario y los datos resuelven todo lo que cambia la cifra.")
    L += ["", "## Comprobaciones", "| Comprobación | Tipo | Qué verifica | A | B |", "|---|---|---|---|---|"]
    impls = inf["implementaciones"]
    a, b = impls.get("a", {}), impls.get("b", {})
    estados = {n: {x["id"]: x for x in impls.get(n, {}).get("reglas", [])} for n in ("a", "b")}
    for rg in inf["reglas"]:
        ea, eb = estados["a"].get(rg["id"], {}), estados["b"].get(rg["id"], {})
        L.append(f"| {rg['id']} | {rg['tipo']} | {rg['descripcion']} | {icono(ea.get('estado'))} | {icono(eb.get('estado'))} |")
    ca, cb = a.get("caso_conocido", {}), b.get("caso_conocido", {})
    L.append(f"| Caso conocido | respuesta conocida | Con datos pequeños hechos a mano, el resultado es el esperado | "
             f"{'✅' if ca.get('ok') else '❌'} | {'✅' if cb.get('ok') else '❌'} |")
    if inf.get("concordancia") is not None:
        L.append(f"| A = B | doble implementación | Las dos implementaciones independientes dan lo mismo | "
                 f"{'✅' if inf['concordancia']['ok'] else '❌'} | |")
    marca = lambda x: "✅" if x else ("❌" if x is False else "—")
    L.append(f"| Compuertas | seguridad y librerías | Sin código peligroso ni librerías fuera de la lista, antes de ejecutar"
             f"{' (corre en caja de arena: sin red ni escritura)' if inf.get('caja_de_arena') else ''} | "
             f"{marca(not a.get('compuertas'))} | {marca(not b.get('compuertas'))} |")
    L.append(f"| Repetible | correr dos veces da lo mismo | La segunda corrida da exactamente el mismo resultado | "
             f"{marca(a.get('repetible'))} | {marca(b.get('repetible'))} |")
    ok_conc = lambda x: None if x.get("conciliacion") is None else revisar_conciliacion(x["conciliacion"]) is None
    L.append(f"| Conciliación | todo conteo cierra | Filas leídas = usadas + excluidas por motivo; nada se borra en silencio | "
             f"{marca(ok_conc(a))} | {marca(ok_conc(b))} |")
    if a.get("segundos") is not None or b.get("segundos") is not None:
        L.append(f"| Tiempo | medir | Segundos de una corrida con los datos reales | {a.get('segundos', '—')} s | {b.get('segundos', '—')} s |")
    ca_conc = a.get("conciliacion") if isinstance(a.get("conciliacion"), dict) else None
    if ca_conc:
        L += ["", "## Conciliación de filas (implementación A)",
              f"- Filas leídas: **{fmt(a_num(ca_conc.get('filas_leidas')))}** · usadas: **{fmt(a_num(ca_conc.get('usadas')))}**"]
        L += [f"- Excluidas por «{k}»: {fmt(a_num(v))}" for k, v in (ca_conc.get("excluidas") or {}).items()]
        L += [f"- Marcadas (se usan, pero se avisa) por «{k}»: {fmt(a_num(v))}" for k, v in (ca_conc.get("marcadas") or {}).items()]
        if inf.get("conciliaciones_iguales") is not None:
            L.append(f"- La conciliación de B {'es igual' if inf['conciliaciones_iguales'] else '**es distinta**'}.")
    ant = inf.get("anticipo")
    if ant:
        L += ["", "## Número anticipado antes de ejecutar",
              f"Se anticipó {ant.get('medida')} entre {fmt(a_num(ant.get('minimo')))} y {fmt(a_num(ant.get('maximo')))} "
              f"({ant.get('razon', '')}). Resultado: {fmt(ant.get('total'))} → "
              + ("**dentro** del anticipo." if ant.get("dentro") else "**fuera** del anticipo: revisar antes de usar la cifra.")]
    detalle = [(n, f) for n in ("a", "b") for f in impls.get(n, {}).get("fallas", [])]
    if detalle or inf["reglas_rotas"]:
        L += ["", "## Detalle de lo que falló"]
        L += [f"- **{n.upper()}**: {f}" for n, f in detalle]
        L += [f"- **Regla rota** (problema de la especificación, no del código): {x}" for x in inf["reglas_rotas"]]
    mensajes = [(x["id"], x["mensaje"]) for x in a.get("reglas", []) if x.get("mensaje")]
    if mensajes:
        L += ["", "## Cifras de cada regla (implementación A)"] + [f"- **{i}**: {m}" for i, m in mensajes]
    s = inf["sellos"]
    L += ["", f"_Criterio sellado: {'sí, sin cambios' if s['estado'] == 'intactos' else s['estado']}"
              f"{(' — ' + ', '.join(s['cambios'])) if s['cambios'] else ''}._"]
    return "\n".join(L) + "\n"


def verificar(c, impls, extra=False):
    spec = cargar_spec(c)
    reglas, problemas_reglas = cargar_reglas(c)
    caso, error_caso = cargar_caso(c, spec)
    sellos = revisar_sellos(c)
    res = {n: evaluar_impl(n, Path(r), spec, reglas, caso) for n, r in impls.items()}
    reglas_rotas = list(problemas_reglas)
    for n, r in res.items():
        reglas_rotas += [f"{x} (con {n.upper()})" for x in r["reglas_con_error"]]
    claves, valores = spec["salida"]["claves"], spec["salida"]["valores"]
    tol = float(spec["salida"].get("tolerancia", 0.5))
    nombres = list(res)
    conc = None
    if len(nombres) == 2 and all(res[n].get("resultado") for n in nombres):
        conc = comparar(res[nombres[0]]["resultado"], res[nombres[1]]["resultado"], claves, valores, tol)

    motivos = []
    if sellos["estado"] == "sin_sellar":
        motivos.append("el criterio (spec, reglas y caso conocido) no está sellado")
    elif sellos["estado"] == "alterados":
        motivos.append("el criterio cambió después de sellarse: " + ", ".join(sellos["cambios"]))
    if not reglas:
        motivos.append("no hay reglas ejecutables")
    if error_caso:
        motivos.append(error_caso)
    if reglas_rotas:
        motivos.append(f"{len(reglas_rotas)} regla(s) con error: revisar la especificación")
    for n, r in res.items():
        if r["fallas"]:
            motivos.append(f"la implementación {n.upper()} tiene {len(r['fallas'])} falla(s)")
    if conc is not None and not conc["ok"]:
        motivos.append(f"las dos implementaciones no dan lo mismo: {describir_comparacion(conc, nombres[0].upper(), nombres[1].upper())}")
    if len(nombres) == 2 and conc is None:
        motivos.append("no se pudieron comparar las dos implementaciones")

    cab = set()
    for ruta_csv in spec["datos"].values():
        with open(ruta_csv, newline="", encoding="utf-8-sig") as fh:
            cab |= set(next(csv.reader(fh)))
    inventadas = [c for c in spec.get("columnas_usadas", []) if c not in cab]
    if inventadas:
        motivos.append(f"la spec usa columnas que no existen en los datos (R1): {inventadas}")
    concs = [res[n].get("conciliacion") for n in nombres]
    conciliaciones_iguales = None
    if len(concs) == 2 and all(isinstance(x, dict) for x in concs):
        clave = lambda x: (int(x.get("filas_leidas", -1)), int(x.get("usadas", -1)), sum(int(v) for v in (x.get("excluidas") or {}).values()))
        conciliaciones_iguales = clave(concs[0]) == clave(concs[1])

    oficial, fuente = None, None
    for n in nombres:
        if not res[n]["fallas"] and res[n].get("resultado"):
            oficial, fuente = res[n]["resultado"], n
            break
    anticipo = dict(spec.get("anticipo") or {})
    if anticipo and oficial and anticipo.get("medida") in valores:
        total = sum(a_num(f.get(anticipo["medida"])) or 0 for f in oficial)
        lo, hi = a_num(anticipo.get("minimo")), a_num(anticipo.get("maximo"))
        anticipo.update({"total": total, "dentro": (lo is None or total >= lo) and (hi is None or total <= hi)})
    inf = {
        "peticion": spec.get("peticion"), "estado": "aprobado" if not motivos else "revisar", "motivos": motivos,
        "preguntas_abiertas": len(spec.get("preguntas", [])), "sellos": sellos, "reglas_rotas": reglas_rotas,
        "reglas": [{"id": r["id"], "tipo": r["tipo"], "descripcion": r["descripcion"]} for r in reglas],
        "implementaciones": res, "concordancia": conc, "resultado_oficial": oficial, "fuente_resultado": fuente,
        "anticipo": anticipo or None, "conciliaciones_iguales": conciliaciones_iguales, "caja_de_arena": bool(CAJA),
    }
    resumen = {"estado": inf["estado"], "motivos": motivos, "preguntas_abiertas": inf["preguntas_abiertas"],
               "reglas_rotas": reglas_rotas, "concuerdan": bool(conc and conc["ok"])}
    for n in nombres:
        resumen[f"fallas_{n}"] = res[n]["fallas"]
    if extra:
        (c / "informe_extra.json").write_text(json.dumps(inf, ensure_ascii=False, indent=2), encoding="utf-8")
        for n, r in res.items():
            print(f"\n{n}: {'sin fallas' if not r['fallas'] else str(len(r['fallas'])) + ' falla(s)'}")
            for f in r["fallas"]:
                print(f"  - {f}")
    else:
        (c / "informe.json").write_text(json.dumps(inf, ensure_ascii=False, indent=2), encoding="utf-8")
        (c / "informe.md").write_text(informe_md(spec, inf), encoding="utf-8")
        print(f"Estado: {inf['estado']}")
        for m in motivos:
            print(f"  - {m}")
        print(f"Informe: {c / 'informe.md'}")
    print("RESUMEN " + json.dumps(resumen, ensure_ascii=False))
    return 0 if inf["estado"] == "aprobado" else 1


def autoprueba(c):
    spec = cargar_spec(c)
    reglas, problemas = cargar_reglas(c)
    caso, error_caso = cargar_caso(c, spec)
    if problemas or error_caso or not reglas:
        for p in problemas + ([error_caso] if error_caso else []) + ([] if reglas else ["no hay reglas"]):
            print(f"✗ {p}")
        return 1
    forma = revisar_forma(caso["esperado"], spec["salida"]["claves"], spec["salida"]["valores"])
    if forma:
        print("✗ esperado.json no tiene la forma de la salida: " + "; ".join(forma))
        return 1
    fallas = 0
    por_id = {x["id"]: x for x in correr_reglas(reglas, caso["datos_crudos"], caso["esperado"])}
    for rg in reglas:
        out = por_id.get(rg["id"], {"estado": "error", "mensaje": "sin resultado"})
        print(f"{'✓' if out['estado'] == 'pasa' else '✗'} {rg['id']} ({rg['tipo']}): {out['estado']} — {out['mensaje']}")
        fallas += out["estado"] != "pasa"
    print(f"\n{len(reglas) - fallas}/{len(reglas)} reglas pasan sobre el caso conocido con su resultado esperado.")
    if fallas:
        print("Una regla que falla aquí está mal escrita, o el resultado esperado está mal calculado.")
    return 1 if fallas else 0


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    c = Path(argv[0]).resolve()
    resto = argv[1:]
    if "--sellar" in resto:
        return sellar(c)
    if "--autoprueba" in resto:
        return autoprueba(c)
    if "--impl" in resto:
        pares = resto[resto.index("--impl") + 1:]
        impls = dict(p.split("=", 1) for p in pares)
        return verificar(c, impls, extra=True)
    return verificar(c, {"a": c / "impl_a.py", "b": c / "impl_b.py"})


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

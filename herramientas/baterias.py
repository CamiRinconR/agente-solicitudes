#!/usr/bin/env python3
"""Baterías: lo que falló una vez se vuelve prueba para siempre (sin IA).

Uso:
  python baterias.py                         corre las tres baterías
  python baterias.py --agregar-malo nombre archivo.py   guarda un hallazgo confirmado como código que debe bloquearse
  python baterias.py --leccion "texto" --origen "..." --prueba "..."   agrega una lección

1. Seguridad: todo lo de baterias/seguridad/malos debe quedar bloqueado y todo lo de buenos debe pasar
   (así también se prueba al probador: un falso positivo es una falla de la compuerta).
2. Privacidad: el perfil de un CSV con datos personales no puede mostrar ninguno de los valores de
   no_deben_salir.txt, y el barrido de gobernanza tiene que encontrarlos.
3. Lecciones: cada lección apunta a una prueba; si apunta a un archivo de la batería, el archivo existe.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
BAT = RAIZ / "baterias"
sys.path.insert(0, str(AQUI))
import dependencias  # noqa: E402
import seguridad  # noqa: E402
from gobernanza import barrer_tabla  # noqa: E402


def bloquea(ruta):
    d = dependencias.revisar(ruta)
    s, _ = seguridad.revisar([ruta])
    return bool(d.get("no_permitidas") or d.get("intenta_instalar") or s[0]["bloquean"])


def bateria_seguridad():
    fallas = []
    malos = sorted((BAT / "seguridad" / "malos").glob("*.py"))
    buenos = sorted((BAT / "seguridad" / "buenos").glob("*.py"))
    for p in malos:
        if not bloquea(p):
            fallas.append(f"no se bloqueó {p.name}")
    for p in buenos:
        if bloquea(p):
            fallas.append(f"falso positivo: se bloqueó {p.name}")
    return {"bateria": "seguridad", "casos": len(malos) + len(buenos), "fallas": fallas}


def bateria_privacidad():
    fallas = []
    csv_ = BAT / "privacidad" / "con_datos_personales.csv"
    secretos = [s for s in (BAT / "privacidad" / "no_deben_salir.txt").read_text(encoding="utf-8").splitlines() if s]
    p = subprocess.run([sys.executable, str(AQUI / "perfilar.py"), f"t={csv_}"], capture_output=True, text=True)  # nosec B603
    for s in secretos:
        if s in p.stdout:
            fallas.append(f"el perfil muestra un dato personal: {s[:3]}…")
    from gobernanza import escanear_texto
    for t in (BAT / "privacidad" / "no_son_personales.txt").read_text(encoding="utf-8").splitlines():
        if t and escanear_texto(t):
            fallas.append(f"falso positivo: «{t}» se marcó como dato personal {escanear_texto(t)}")
    barrido = barrer_tabla(csv_)
    detectadas = {c for c, i in barrido["columnas"].items() if i.get("hallazgos") or i.get("clase_por_nombre") == "personal"}
    for c in ("proveedor_adjudicado", "documento_proveedor", "objeto_del_contrato"):
        if c not in detectadas:
            fallas.append(f"el barrido no detectó {c}")
    from gobernanza import clasificar_columna
    cols = json.loads((BAT / "privacidad" / "columnas_secop.json").read_text(encoding="utf-8"))
    n_cols = 0
    for grupo, aceptadas in (("personal", {"personal"}), ("cuasi_o_personal", {"personal", "cuasi"}),
                             ("texto_libre", {"texto_libre"}), ("sin_marca", {None})):
        for c in cols[grupo]:
            n_cols += 1
            if clasificar_columna(c) not in aceptadas:
                fallas.append(f"columna de SECOP mal clasificada: {c} → {clasificar_columna(c)} (se esperaba {grupo})")
    return {"bateria": "privacidad", "casos": len(secretos) + 3 + 6 + n_cols, "fallas": fallas}


def bateria_failfast():
    """Un CSV mal formado detiene la lectura: nunca se lee a medias en silencio (FAILFAST)."""
    from reglas_base import leer_csv
    fallas, casos = [], sorted((BAT / "failfast").glob("*.csv"))
    for p in casos:
        try:
            leer_csv(p)
            fallas.append(f"{p.name} se leyó sin error")
        except Exception:
            pass
    return {"bateria": "failfast", "casos": len(casos), "fallas": fallas}


def bateria_lecciones():
    d = json.loads((BAT / "lecciones.json").read_text(encoding="utf-8"))
    fallas = []
    for l in d["lecciones"]:
        prueba = l.get("prueba", "")
        if not prueba:
            fallas.append(f"{l['id']} no tiene prueba")
        for parte in prueba.split():
            if parte.startswith("bateria:"):
                ruta = parte.split(":", 1)[1]
                if not ((BAT / ruta).exists() or (RAIZ / ruta).exists()):
                    fallas.append(f"{l['id']}: no existe {parte}")
    return {"bateria": "lecciones", "casos": len(d["lecciones"]), "fallas": fallas}


def main(argv):
    if "--agregar-malo" in argv:
        i = argv.index("--agregar-malo")
        nombre, origen = argv[i + 1], Path(argv[i + 2])
        destino = BAT / "seguridad" / "malos" / f"{nombre}.py"
        shutil.copy(origen, destino)
        print(f"Agregado {destino.name}. {'Se bloquea hoy.' if bloquea(destino) else 'HOY NO SE BLOQUEA: hay que mejorar la compuerta.'}")
        return 0
    if "--leccion" in argv:
        d = json.loads((BAT / "lecciones.json").read_text(encoding="utf-8"))
        g = lambda k: argv[argv.index(k) + 1] if k in argv else ""
        ident = g("--id") or f"L{len(d['lecciones']) + 1:02d}"   # en un aporte: --id L-<usuario>-<tema>; el dueño renumera al aceptar
        d["lecciones"].append({"id": ident, "leccion": g("--leccion"), "origen": g("--origen"), "prueba": g("--prueba")})
        (BAT / "lecciones.json").write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Lección {d['lecciones'][-1]['id']} agregada.")
        return 0
    res = [bateria_seguridad(), bateria_privacidad(), bateria_failfast(), bateria_lecciones()]
    for r in res:
        print(f"{'✓' if not r['fallas'] else '✗'} {r['bateria']}: {r['casos']} casos" + ("" if not r["fallas"] else " · " + "; ".join(r["fallas"])))
    malos = sum(len(r["fallas"]) for r in res)
    print("RESUMEN " + json.dumps({"baterias": len(res), "fallas": malos}, ensure_ascii=False))
    return 1 if malos else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

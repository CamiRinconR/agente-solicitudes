#!/usr/bin/env python3
"""Compuerta de seguridad para el código que escribe la IA (sin IA).

Uso: python seguridad.py archivo.py [archivo.py ...]

El código de la IA en este pipeline es una función pura: lee los CSV que recibe y devuelve filas.
Por eso se bloquea todo lo que se sale de ese contrato:
  - ejecución de código o de comandos: eval, exec, compile, __import__, os.system, subprocess, pty...
  - deserialización insegura: pickle, marshal, shelve, dill
  - red: socket, urllib, http, requests, ftplib, smtplib...
  - escritura: open en modo w/a/x/+, Path.write_*, os.remove, shutil.rmtree, to_csv/to_parquet...
  - acceso por reflexión: ctypes, importlib, getattr sobre __builtins__
  - secretos en el código (llaves de API, tokens, contraseñas)
y además corre Bandit (el analizador estático estándar de Python): severidad media o alta bloquea.
Las librerías se revisan aparte con dependencias.py (solo las de permitidas.json).
"""
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

MODULOS_PROHIBIDOS = {
    "subprocess": "ejecuta comandos", "pty": "ejecuta comandos", "socket": "red", "http": "red",
    "urllib": "red", "requests": "red", "ftplib": "red", "smtplib": "red", "telnetlib": "red", "ssl": "red",
    "pickle": "deserialización insegura", "marshal": "deserialización insegura", "shelve": "deserialización insegura",
    "dill": "deserialización insegura", "ctypes": "acceso a memoria", "importlib": "importación dinámica",
    "shutil": "borra o mueve archivos", "tempfile": "escribe archivos", "multiprocessing": "lanza procesos",
}
BUILTINS_PROHIBIDOS = {   # solo cuando se llaman como función del sistema: eval(...), no re.compile(...)
    "eval": "ejecuta texto como código", "exec": "ejecuta texto como código", "compile": "ejecuta texto como código",
    "__import__": "importación dinámica", "breakpoint": "abre un depurador",
}
ATRIBUTOS_PROHIBIDOS = {  # sobre cualquier objeto: escriben, borran o deserializan
    "write_text": "escribe archivos", "write_bytes": "escribe archivos", "to_csv": "escribe archivos",
    "to_parquet": "escribe archivos", "to_excel": "escribe archivos", "to_pickle": "escribe archivos",
    "to_json": "escribe archivos", "read_pickle": "deserialización insegura", "read_html": "red y HTML no confiable", "unlink": "borra archivos",
    "rmtree": "borra carpetas", "rmdir": "borra carpetas",
}
OS_PROHIBIDOS = {  # solo sobre os: os.system(...), no lista.remove(...)
    "system": "ejecuta comandos", "popen": "ejecuta comandos", "remove": "borra archivos", "spawnl": "lanza procesos",
    "execv": "reemplaza el proceso", "execl": "reemplaza el proceso", "fork": "lanza procesos", "kill": "envía señales",
    **{f: "reemplaza el proceso" for f in ("execle", "execlp", "execlpe", "execve", "execvp", "execvpe")},
    **{f: "lanza procesos" for f in ("spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve", "spawnvp", "spawnvpe",
                                     "posix_spawn", "posix_spawnp", "forkpty", "startfile")},
    "killpg": "envía señales", "putenv": "cambia el entorno", "chmod": "cambia permisos", "rename": "mueve archivos", "replace": "mueve archivos",
}
SECRETOS = re.compile(
    r"(sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{30,}|"
    r"(?i:(api[_-]?key|token|secret|password|contraseña|clave)\s*=\s*['\"][^'\"]{8,}['\"]))")


def revisar_ast(texto):
    hallazgos = []
    try:
        arbol = ast.parse(texto)
        alias_os = {"os"} | {a.asname for n in ast.walk(arbol) if isinstance(n, ast.Import) for a in n.names if a.name == "os" and a.asname}
    except SyntaxError as e:
        return [{"linea": e.lineno, "regla": "sintaxis", "detalle": str(e)}]
    for n in ast.walk(arbol):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            nombres = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""]
            for m in nombres:
                raiz = m.split(".")[0]
                if raiz in MODULOS_PROHIBIDOS:
                    hallazgos.append({"linea": n.lineno, "regla": f"importa {raiz}", "detalle": MODULOS_PROHIBIDOS[raiz]})
            if isinstance(n, ast.ImportFrom) and n.module == "os":
                for a in n.names:
                    if a.name in OS_PROHIBIDOS:
                        hallazgos.append({"linea": n.lineno, "regla": f"from os import {a.name}", "detalle": OS_PROHIBIDOS[a.name]})
        elif isinstance(n, ast.Call):
            f = n.func
            nombre = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
            sobre = f.value.id if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) else None
            if isinstance(f, ast.Name) and nombre in BUILTINS_PROHIBIDOS:
                hallazgos.append({"linea": n.lineno, "regla": f"llama {nombre}", "detalle": BUILTINS_PROHIBIDOS[nombre]})
            elif isinstance(f, ast.Attribute) and nombre in ATRIBUTOS_PROHIBIDOS:
                hallazgos.append({"linea": n.lineno, "regla": f"llama .{nombre}", "detalle": ATRIBUTOS_PROHIBIDOS[nombre]})
            elif sobre in alias_os and nombre in OS_PROHIBIDOS:
                hallazgos.append({"linea": n.lineno, "regla": f"llama os.{nombre}", "detalle": OS_PROHIBIDOS[nombre]})
            if nombre == "open":
                modo = None
                if len(n.args) > 1 and isinstance(n.args[1], ast.Constant):
                    modo = n.args[1].value
                for k in n.keywords:
                    if k.arg == "mode" and isinstance(k.value, ast.Constant):
                        modo = k.value.value
                if isinstance(modo, str) and any(c in modo for c in "wax+"):
                    hallazgos.append({"linea": n.lineno, "regla": f"open(..., '{modo}')", "detalle": "escribe archivos"})
                elif modo is not None and not isinstance(modo, str):
                    hallazgos.append({"linea": n.lineno, "regla": "open con modo calculado", "detalle": "no se puede saber si escribe"})
            if nombre == "getattr" and n.args and isinstance(n.args[0], ast.Name) and n.args[0].id in ("__builtins__", "builtins", "os"):
                hallazgos.append({"linea": n.lineno, "regla": "getattr sobre builtins/os", "detalle": "evade la revisión"})
        elif isinstance(n, ast.Attribute) and n.attr in ("parent", "parents"):
            hallazgos.append({"linea": n.lineno, "regla": f"navega carpetas (.{n.attr})", "detalle": "lee fuera de lo que recibe en datos"})
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and (
                re.match(r"^(/|~|[A-Za-z]:\\)[\w.-]", n.value) or "../" in n.value or n.value == ".."):
            hallazgos.append({"linea": n.lineno, "regla": "ruta fija en el código", "detalle": "lee fuera de lo que recibe en datos"})
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and re.match(r"^\s*(https?|ftp|s3|gs|file|wss?)://", n.value, re.I):
            hallazgos.append({"linea": n.lineno, "regla": "URL en el código", "detalle": "red: el código solo lee las rutas que recibe en datos"})
        elif isinstance(n, ast.Attribute) and n.attr in ("__subclasses__", "__globals__", "__code__", "__builtins__"):
            hallazgos.append({"linea": n.lineno, "regla": f"usa {n.attr}", "detalle": "acceso por reflexión"})
    for i, linea in enumerate(texto.splitlines(), 1):
        if SECRETOS.search(linea):
            hallazgos.append({"linea": i, "regla": "secreto en el código", "detalle": "llave, token o contraseña escrita en el código"})
    return hallazgos


def bandit(rutas):
    exe = Path(sys.executable).parent / "bandit"
    if not exe.exists():
        return {}, "Bandit no está instalado en este Python"
    p = subprocess.run([str(exe), "-q", "-f", "json", *map(str, rutas)], capture_output=True, text=True)  # nosec B603
    try:
        res = json.loads(p.stdout or "{}").get("results", [])
    except json.JSONDecodeError:
        return {}, f"Bandit no devolvió JSON: {p.stderr.strip()[:200]}"
    por = {}
    for r in res:
        por.setdefault(str(Path(r["filename"]).resolve()), []).append(
            {"linea": r["line_number"], "regla": f"bandit {r['test_id']}", "severidad": r["issue_severity"],
             "detalle": r["issue_text"]})
    return por, None


def revisar(rutas):
    rutas = [Path(r).resolve() for r in rutas]
    por_bandit, aviso = bandit(rutas)
    out = []
    for r in rutas:
        propios = revisar_ast(r.read_text(encoding="utf-8"))
        b = por_bandit.get(str(r), [])
        bloquean = propios + [x for x in b if x["severidad"] in ("MEDIUM", "HIGH")]
        out.append({"archivo": str(r), "bloquean": bloquean, "avisos": [x for x in b if x["severidad"] == "LOW"]})
    return out, aviso


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    res, aviso = revisar(argv)
    if aviso:
        print(f"! {aviso}")
    malos = 0
    for r in res:
        malos += bool(r["bloquean"])
        print(f"{'✗' if r['bloquean'] else '✓'} {Path(r['archivo']).name}: "
              + ("sin hallazgos que bloqueen" if not r["bloquean"] else
                 "; ".join(f"línea {h['linea']}: {h['regla']} ({h['detalle']})" for h in r["bloquean"][:6]))
              + (f" · {len(r['avisos'])} avisos leves de Bandit" if r["avisos"] else ""))
    print("RESUMEN " + json.dumps({"archivos": len(res), "bloqueados": malos, "bandit": not aviso}, ensure_ascii=False))
    return 1 if malos else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Ejecuta código escrito por la IA en otro proceso, dentro de la caja de arena de macOS (sin red, sin escribir)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

CAJA = shutil.which("sandbox-exec")
MARCA = "<<<SALIDA-CAJA>>>"


def correr(codigo, *args, tiempo=300, entrada=None):
    """Corre `codigo` (texto Python) con args; el código debe imprimir MARCA + json. Devuelve (dato, error)."""
    tmp = tempfile.mkdtemp(prefix="caja-")
    cmd = [sys.executable, "-c", codigo, *args]
    if CAJA:
        perfil = ('(version 1)(allow default)(deny network*)(deny file-write*)'
                  f'(allow file-write* (subpath "{os.path.realpath(tmp)}") (literal "/dev/null") (literal "/dev/dtracehelper"))')
        cmd = [CAJA, "-p", perfil] + cmd
    entorno = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "TMPDIR": tmp, "MPLCONFIGDIR": tmp}
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=tiempo, env=entorno, input=entrada)  # nosec B603
    except subprocess.TimeoutExpired:
        return None, f"tardó más de {tiempo} s"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for linea in reversed(p.stdout.splitlines()):
        if linea.startswith(MARCA):
            return json.loads(linea[len(MARCA):]), None
    return None, (p.stderr.strip().splitlines() or ["terminó sin devolver resultado"])[-1]

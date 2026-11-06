"""Caja de arena para el código que escribe la IA (macOS: sandbox-exec; en Linux, solo entorno y límites).

Lo que el código de la IA NO puede hacer aquí:
  - usar la red;
  - escribir fuera de una carpeta temporal propia;
  - leer la carpeta personal (/Users), salvo el repositorio y las rutas que se le pasan explícitamente;
  - ver las variables de entorno del proceso que la lanza (secretos): recibe un entorno mínimo y HOME temporal;
  - pasar de un tope de tiempo y de memoria (un vigilante lo detiene).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CAJA = shutil.which("sandbox-exec")
MARCA = "<<<SALIDA-CAJA>>>"
RAIZ = Path(__file__).resolve().parent.parent
LIMITE_MB = int(os.environ.get("LIMITE_MEMORIA_MB", "1536"))
ENTORNO_PERMITIDO = ("PATH", "LANG", "LC_ALL", "LC_CTYPE")


def entorno(tmp):
    e = {k: os.environ[k] for k in ENTORNO_PERMITIDO if k in os.environ}
    e.update({"HOME": tmp, "TMPDIR": tmp, "MPLCONFIGDIR": tmp, "PYTHONDONTWRITEBYTECODE": "1",
              "PYTHONHASHSEED": "0", "PYTHONIOENCODING": "utf-8", "PYTHONNOUSERSITE": "1"})
    return e


def perfil(tmp, lecturas=()):
    # El intérprete necesita leer su propia instalación (pyvenv.cfg, biblioteca estándar, paquetes): si el entorno vive
    # fuera del repositorio (un worktree que usa el .venv de la copia principal), sin esto Python ni arranca.
    entorno_py = [os.path.realpath(sys.prefix), os.path.realpath(sys.base_prefix)]
    leer = [os.path.realpath(RAIZ), os.path.realpath(tmp)] + entorno_py + [os.path.realpath(str(p)) for p in lecturas]
    permitir = "".join(f'(allow file-read-data (subpath "{p}"))' for p in dict.fromkeys(leer))
    return ('(version 1)(allow default)(deny network*)(deny file-write*)'
            f'(allow file-write* (subpath "{os.path.realpath(tmp)}") (literal "/dev/null") (literal "/dev/dtracehelper"))'
            # se niega LEER EL CONTENIDO de la carpeta personal; consultar nombres y rutas sí (Python lo necesita al arrancar)
            '(deny file-read-data (subpath "/Users"))' + permitir)


def _limites():
    try:
        import resource
        b = LIMITE_MB * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (b, b))      # efectivo en Linux; en macOS lo cubre el vigilante
    except Exception:
        pass


def _huella_mb(pid):
    """Memoria del proceso en MB. En macOS, la huella física (phys_footprint): cuenta también la memoria comprimida
    y la enviada al disco; la residente (RSS) deja de crecer bajo presión y engaña al vigilante."""
    if sys.platform == "darwin":
        try:
            import ctypes
            class _Info(ctypes.Structure):
                _fields_ = [("uuid", ctypes.c_uint8 * 16)] + [(n, ctypes.c_uint64) for n in (
                    "user", "system", "idle", "interrupt", "pageins", "wired", "resident", "phys_footprint", "start", "exit")]
            info = _Info()
            if ctypes.CDLL("/usr/lib/libproc.dylib").proc_pid_rusage(int(pid), 0, ctypes.byref(info)) == 0:
                return info.phys_footprint / 1024 / 1024
        except Exception:
            pass
    try:
        o = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True, timeout=2).stdout.strip()  # nosec B603 B607
        return int(o) / 1024 if o else None
    except Exception:
        return None


def ejecutar(args_python, tiempo=300, entrada=None, lecturas=()):
    """Corre `python <args>` en la caja. Devuelve (stdout, stderr, motivo_de_corte, segundos)."""
    tmp = tempfile.mkdtemp(prefix="caja-")
    cmd = [sys.executable, *args_python]
    if CAJA:
        cmd = [CAJA, "-p", perfil(tmp, lecturas)] + cmd
    t0 = time.perf_counter()
    motivo = None
    try:
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE if entrada is not None else subprocess.DEVNULL,  # nosec B603
                                 stdout=out, stderr=err, env=entorno(tmp), preexec_fn=_limites)
            if entrada is not None:
                try:
                    p.stdin.write(entrada.encode("utf-8"))
                    p.stdin.close()
                except BrokenPipeError:
                    pass
            while p.poll() is None:
                if time.perf_counter() - t0 > tiempo:
                    motivo = f"tardó más de {tiempo} s"
                    p.kill()
                    break
                rss = _huella_mb(p.pid)
                if rss and rss > LIMITE_MB:
                    motivo = f"superó el tope de memoria ({LIMITE_MB} MB)"
                    p.kill()
                    break
                time.sleep(0.05)
            p.wait()
            out.seek(0)
            err.seek(0)
            so = out.read().decode("utf-8", errors="replace")
            se = err.read().decode("utf-8", errors="replace")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return so, se, motivo, round(time.perf_counter() - t0, 2)


def correr(codigo, *args, tiempo=300, entrada=None, lecturas=()):
    """Corre `codigo` (texto Python) con args; el código imprime MARCA + json. Devuelve (dato, error)."""
    so, se, motivo, _ = ejecutar(["-c", codigo, *args], tiempo, entrada, lecturas)
    if motivo:
        return None, motivo
    for linea in reversed(so.splitlines()):
        if linea.startswith(MARCA):
            return json.loads(linea[len(MARCA):]), None
    return None, (se.strip().splitlines() or ["terminó sin devolver resultado"])[-1]

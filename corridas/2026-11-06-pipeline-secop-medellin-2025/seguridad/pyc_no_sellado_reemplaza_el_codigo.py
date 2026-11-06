"""pyc_no_sellado_reemplaza_el_codigo · lo que se ejecuta puede no ser el .py que pasó la compuerta y el sello.

verificar.py:107-109 (reglas.py) y los RUNNER de verificar.py:44-46, verificar_hipotesis.py y
verificar_grafico.py cargan el código con spec_from_file_location: si __pycache__/<nombre>.cpython-313.pyc
trae en su cabecera la misma fecha y el mismo tamaño del .py, Python ejecuta ese .pyc sin volver a leer la
fuente. La compuerta (seguridad.py, dependencias.py) y los sellos (sellos.json: sha256 de spec, reglas y
caso conocido) solo miran el .py; PYTHONDONTWRITEBYTECODE impide escribir .pyc, no leerlos. En esta corrida
ya hay __pycache__/reglas.cpython-313.pyc y grafico.cpython-313.pyc, y cualquier agente que escribe en la
corrida puede dejar uno.
La prueba arma en una carpeta temporal un .py inocente y un .pyc de otro código con la cabecera del .py, y lo
carga como el verificador. Luego revisa que los .pyc que hay hoy en la corrida coinciden con su fuente.
Prueba de la revisión ciega (no es código de la IA). Solo escribe en una carpeta temporal.
"""
import importlib._bootstrap_external as externo
import importlib.util
import marshal
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
C = Path(__file__).resolve().parent.parent
H = C.parent.parent / "herramientas"
sys.path.insert(0, str(H))
import seguridad  # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="seg-pyc-"))
fuente = tmp / "impl_x.py"
fuente.write_text("def analizar(datos):\n    return []\n", encoding="utf-8")
otro = compile("def analizar(datos):\n    return [{'lo_que_corre': 'otro codigo'}]\n", str(fuente), "exec")
st = fuente.stat()
pyc = Path(importlib.util.cache_from_source(str(fuente)))
pyc.parent.mkdir(exist_ok=True)
pyc.write_bytes(externo._code_to_timestamp_pyc(otro, int(st.st_mtime), st.st_size))

spec = importlib.util.spec_from_file_location("impl_bajo_prueba", fuente)   # igual que el RUNNER
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
corre = mod.analizar({})
compuerta = seguridad.revisar([fuente])[0][0]["bloquean"]
print(f"la compuerta revisa {fuente.name} y no ve nada: {not compuerta} · su fuente devuelve []")
print(f"lo que de verdad corre devuelve: {corre}")


def igual(a, b):
    if a.co_code != b.co_code or a.co_names != b.co_names or len(a.co_consts) != len(b.co_consts):
        return False
    for x, y in zip(a.co_consts, b.co_consts):
        if hasattr(x, "co_code"):
            if not (hasattr(y, "co_code") and igual(x, y)):
                return False
        elif type(x) is not type(y) or x != y:
            return False
    return True


for nombre in ("reglas", "grafico", "impl_a", "impl_b", "hipotesis"):
    p = C / "__pycache__" / f"{nombre}.cpython-{sys.version_info.major}{sys.version_info.minor}.pyc"
    if not p.exists():
        print(f"corrida: no hay .pyc de {nombre}.py")
        continue
    datos_pyc, src = p.read_bytes(), C / f"{nombre}.py"
    cab = (int.from_bytes(datos_pyc[8:12], "little"), int.from_bytes(datos_pyc[12:16], "little"))
    vigente = cab == (int(src.stat().st_mtime) & 0xFFFFFFFF, src.stat().st_size)
    mismo = igual(marshal.loads(datos_pyc[16:]), compile(src.read_bytes(), str(src), "exec"))
    print(f"corrida: {p.name} vigente (Python lo usaría): {vigente} · coincide con {nombre}.py: {mismo}")

ok = not compuerta and corre == [{"lo_que_corre": "otro codigo"}]
print("CONFIRMADO" if ok else "NO SE REPRODUJO")
sys.exit(0 if ok else 1)

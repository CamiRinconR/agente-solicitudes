"""memoria_y_lecturas_repetidas · todo el CSV va a memoria, varias veces, sin tope de tamaño.

reglas.py:29-39 (_contratos_2025) vuelve a leer y a parsear el CSV completo en R1, R2, R4, R5, R6 y R8 (6 de 9
reglas), y verificar.py corre las reglas una vez por implementación, dentro de su propio proceso y sin tope de
memoria. hipotesis.py:78-99 (_cuentan) lo relee en cada una de H1-H5. impl_b.py:145 y :151 guarda dos copias
(listas y luego dicts). Nadie limita el tamaño del archivo, y impl_a.py:86 (pandas) tampoco limita el de una
celda: un nombre de 200.000 caracteres pasa entero al resultado publicado (el módulo csv corta en 131.072).
La prueba mide sobre el CSV real de la corrida. Prueba de la revisión ciega (no es código de la IA).
Solo escribe en una carpeta temporal.
"""
import importlib.util
import json
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

sys.dont_write_bytecode = True
C = Path(__file__).resolve().parent.parent
H = C.parent.parent / "herramientas"
sys.path.insert(0, str(H))
import reglas_base  # noqa: E402

REAL = C / "datos" / "contratos.csv"
DATOS = {"contratos": str(REAL)}
MB = REAL.stat().st_size / 1e6
LECTURAS = {"n": 0}
_original = reglas_base.leer_csv


def contando(ruta):
    LECTURAS["n"] += 1
    return _original(ruta)


reglas_base.leer_csv = contando   # reglas.py e hipotesis.py lo importan con «from reglas_base import leer_csv»


def cargar(archivo):
    spec = importlib.util.spec_from_file_location(Path(archivo).stem + "_bajo_prueba", C / archivo)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


reglas_base.REGLAS.clear()
cargar("reglas.py")
resultado = json.loads((C / "informe.json").read_text(encoding="utf-8"))["resultado_oficial"]
t0 = time.perf_counter()
for r in reglas_base.REGLAS:
    r["fn"](dict(DATOS), [dict(f) for f in resultado])
seg_reglas, lect_reglas = time.perf_counter() - t0, LECTURAS["n"]
LECTURAS["n"] = 0
cargar("hipotesis.py")
t0 = time.perf_counter()
for fn in reglas_base.HIPOTESIS.values():
    fn(dict(DATOS))
seg_hip, lect_hip = time.perf_counter() - t0, LECTURAS["n"]
print(f"CSV real: {MB:.1f} MB · reglas.py lo parsea {lect_reglas} veces en una pasada de sus "
      f"{len(reglas_base.REGLAS)} reglas ({seg_reglas:.1f} s; verificar.py hace una pasada por implementación) · "
      f"hipotesis.py {lect_hip} veces ({seg_hip:.1f} s)")

impl_a, impl_b = cargar("impl_a.py"), cargar("impl_b.py")
for nombre, leer in (("reglas_base.leer_csv", lambda: _original(str(REAL))),
                     ("impl_b._cargar", lambda: impl_b._cargar(DATOS)),
                     ("impl_a._tabla (pandas)", lambda: impl_a._tabla(DATOS))):
    tracemalloc.start()
    x = leer()
    pico = tracemalloc.get_traced_memory()[1] / 1e6
    tracemalloc.stop()
    del x
    print(f"  {nombre}: pico {pico:.0f} MB para {MB:.1f} MB de archivo (x{pico / MB:.0f})")

grande = "X" * 200_000
tmp = Path(tempfile.mkdtemp(prefix="seg-mem-"))
(tmp / "contratos.csv").write_text("id_contrato,nit_entidad,codigo_entidad,nombre_entidad,fecha_de_firma,"
                                   f"valor_del_contrato\nC1,890905211,1,{grande},2025-03-01T10:00:00.000,100\n",
                                   encoding="utf-8")
largo_a = len(impl_a.analizar({"contratos": str(tmp / "contratos.csv")})[0]["entidad"])
try:
    impl_b.analizar({"contratos": str(tmp / "contratos.csv")})
    b = "sin error"
except Exception as e:
    b = f"{type(e).__name__}: {e}"
print(f"celda de 200.000 caracteres: impl_a la publica entera ({largo_a:,} caracteres en entidad) · impl_b: {b}")
ok = lect_reglas == 6 and lect_hip == 5 and largo_a == 200_000
print("CONFIRMADO" if ok else "NO SE REPRODUJO")
sys.exit(0 if ok else 1)

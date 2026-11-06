"""hipotesis_lee_fechas_distinto · hipotesis.py cuenta otros contratos que el resultado oficial, sin avisar.

hipotesis.py:26-27 y 51-65 (_dia) leen fecha_de_firma con \\d (acepta dígitos Unicode, que int() convierte),
aceptan día y mes de un dígito (\\d{1,2}) y descartan fechas que no existen (2025-02-30). impl_a, impl_b y
reglas.py leen por texto con [0-9]{2}: excluyen las dos primeras y cuentan la tercera. Nada compara cuántos
contratos usa hipotesis.py con los del resultado, así que H1-H5 se publican sobre otra población.
Datos ficticios. Prueba de la revisión ciega (no es código de la IA). Solo escribe en una carpeta temporal.
"""
import importlib.util
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
C = Path(__file__).resolve().parent.parent
H = C.parent.parent / "herramientas"
sys.path.insert(0, str(H))
import reglas_base  # noqa: E402

ENC = "id_contrato,nit_entidad,codigo_entidad,nombre_entidad,fecha_de_firma,valor_del_contrato"
FILAS = {
    "C1": "2025-03-01T10:00:00.000",       # normal
    "C2": "２０２５-０３-１０T10:00:00.000",  # dígitos de ancho completo
    "C3": "5/3/2025",                      # día y mes de un dígito
    "C4": "2025-02-30T10:00:00.000",       # no existe en el calendario
}


def cargar(archivo):
    spec = importlib.util.spec_from_file_location(Path(archivo).stem + "_bajo_prueba", C / archivo)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tmp = Path(tempfile.mkdtemp(prefix="seg-fechas-"))
ruta = tmp / "contratos.csv"
ruta.write_text("\n".join([ENC] + [f"{k},890905211,1,ALCALDIA,{f},{10 ** i}" for i, (k, f) in enumerate(FILAS.items(), 2)])
                + "\n", encoding="utf-8")
datos = {"contratos": str(ruta)}
impl_a, impl_b, hip = cargar("impl_a.py"), cargar("impl_b.py"), cargar("hipotesis.py")
reglas_base.REGLAS.clear()
cargar("reglas.py")
r2 = next(r for r in reglas_base.REGLAS if r["id"] == "R2")

oficial = impl_a.analizar(datos)
total_oficial = sum(f["valor_contratado"] for f in oficial)
n_oficial = sum(f["numero_contratos"] for f in oficial)
n_b = sum(f["numero_contratos"] for f in impl_b.analizar(datos))
cuentan, frase = hip._cuentan(dict(datos))
total_h = sum(v for _, _, v in cuentan)
print(f"impl_a: {n_oficial} contratos, {total_oficial:,.0f} pesos · impl_b: {n_b} · R2 de reglas.py pasa: "
      f"{r2['fn'](dict(datos), oficial)[0]}")
print(f"hipotesis.py: {len(cuentan)} contratos, {total_h:,.0f} pesos · «{frase}»")
print(f"H1 corre sin error: {hip.h1(dict(datos))['detalle'][:90]}…")
ok = len(cuentan) != n_oficial and float(total_h) != total_oficial
print("CONFIRMADO" if ok else "NO SE REPRODUJO")
sys.exit(0 if ok else 1)

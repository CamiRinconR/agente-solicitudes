"""impl_b.py (línea 290) e impl_a.py (línea 351): cada valor pasa la prueba de número finito, pero la suma de un
NIT puede pasarse del máximo de float.

B devuelve valor_contratado = inf sin ningún aviso sobre el total (solo marca cada fila como mayor de 100 mil
millones); A se cae con OverflowError en math.fsum. Hoy R1 lo ataja porque inf - inf no es <= 0,5.
Datos sintéticos; no modifica el código revisado.

Uso: .venv/bin/python -B seguridad/suma_desborda_float.py
Sale con 0 e imprime REPRODUCIDO si el patrón se reproduce; con 1 si ya no.
"""
import math
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
CORRIDA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CORRIDA))
import impl_a  # noqa: E402
import impl_b  # noqa: E402

ENCABEZADO = "id_contrato,nit_entidad,nombre_entidad,fecha_de_firma,valor_del_contrato\n"
FILAS = ["C1,800000001,ENTIDAD UNO,2025-03-01,1e308", "C2,800000001,ENTIDAD UNO,2025-03-02,1e308"]

with tempfile.TemporaryDirectory() as t:
    ruta = Path(t) / "contratos.csv"
    ruta.write_text(ENCABEZADO + "\n".join(FILAS) + "\n", encoding="utf-8")
    datos = {"contratos": str(ruta)}
    b, cb = impl_b.analizar(datos), impl_b.conciliar(datos)
    try:
        impl_a.analizar(datos)
        a = "sin error"
    except OverflowError as e:
        a = f"OverflowError: {e}"

total_b = b[0]["valor_contratado"]
print(f"B: valor_contratado = {total_b} · marcadas {cb['marcadas']} · A: {a}")
ok = not math.isfinite(total_b) and a.startswith("OverflowError")
print("REPRODUCIDO" if ok else "NO SE REPRODUJO")
sys.exit(0 if ok else 1)

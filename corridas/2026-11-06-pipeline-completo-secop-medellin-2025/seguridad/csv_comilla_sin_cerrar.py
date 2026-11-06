"""impl_b.py (línea 160) e hipotesis.py (línea 73) leen el CSV con el módulo csv sin strict=True.

Una comilla de apertura sin cierre vuelve el resto del archivo (hasta 128 KiB) un solo campo: esas filas
desaparecen sin error ni aviso, y conciliar cierra igual porque solo cuenta lo que leyó. impl_a (pandas) y
reglas.py (strict=True) sí fallan con error, así que hoy A = B y las reglas lo atajan.
Datos sintéticos; no modifica el código revisado.

Uso: .venv/bin/python -B seguridad/csv_comilla_sin_cerrar.py
Sale con 0 e imprime REPRODUCIDO si el patrón se reproduce; con 1 si ya no.
"""
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
CORRIDA = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(CORRIDA), str(CORRIDA.parent.parent / "herramientas")]
import hipotesis  # noqa: E402
import impl_a  # noqa: E402
import impl_b  # noqa: E402
from reglas_base import leer_csv  # noqa: E402

ENCABEZADO = "id_contrato,nit_entidad,codigo_entidad,nombre_entidad,fecha_de_firma,valor_del_contrato\n"
FILAS = [f"C{i},800000001,1,ENTIDAD UNO,2025-03-0{i},1000" for i in range(1, 6)]
FILAS[2] = 'C3,800000001,1,"ENTIDAD UNO,2025-03-03,1000'   # comilla que abre y nunca cierra


def falla(fn):
    try:
        fn()
        return None
    except Exception as e:  # noqa: BLE001
        return type(e).__name__


with tempfile.TemporaryDirectory() as t:
    ruta = Path(t) / "contratos.csv"
    ruta.write_text(ENCABEZADO + "\n".join(FILAS) + "\n", encoding="utf-8")
    datos = {"contratos": str(ruta)}
    b = impl_b.conciliar(datos)
    h = len(hipotesis._registros(str(ruta.resolve())))
    a, r = falla(lambda: impl_a.conciliar(datos)), falla(lambda: leer_csv(str(ruta)))

print(f"filas en el archivo: {len(FILAS)} · B lee {b['filas_leidas']} y su conciliación cierra "
      f"({b['usadas']} usadas + {sum(b['excluidas'].values())} excluidas), marcadas {b['marcadas']} · "
      f"hipotesis lee {h} · A: {a} · reglas: {r}")
ok = b["filas_leidas"] < len(FILAS) and h < len(FILAS) and a is not None and r is not None
print("REPRODUCIDO" if ok else "NO SE REPRODUJO")
sys.exit(0 if ok else 1)

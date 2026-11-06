"""impl_a.py (líneas 135-146): pd.read_csv sin index_col=False.

Si la primera fila de datos trae un campo de más, pandas toma la primera columna (id_contrato) como índice,
corre todas las columnas un lugar y reset_index(drop=True) bota los id: A lee el NIT como id, el nombre como
NIT y el valor como fecha, sin error. impl_b lo marca como fila_mal_formada y reglas.py falla, así que hoy
A = B lo ataja. Datos sintéticos; no modifica el código revisado.

Uso: .venv/bin/python -B seguridad/pandas_indice_implicito.py
Sale con 0 e imprime REPRODUCIDO si el patrón se reproduce; con 1 si ya no.
"""
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
CORRIDA = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(CORRIDA), str(CORRIDA.parent.parent / "herramientas")]
import impl_a  # noqa: E402
import impl_b  # noqa: E402
from reglas_base import leer_csv  # noqa: E402

ENCABEZADO = "id_contrato,nit_entidad,nombre_entidad,fecha_de_firma,valor_del_contrato\n"
FILAS = [f"C{i},800000001,ENTIDAD UNO,2025-03-0{i},1000" for i in range(1, 5)]
FILAS[0] += ",EXTRA"   # un solo campo de más, en la primera fila de datos

with tempfile.TemporaryDirectory() as t:
    ruta = Path(t) / "contratos.csv"
    ruta.write_text(ENCABEZADO + "\n".join(FILAS) + "\n", encoding="utf-8")
    datos = {"contratos": str(ruta)}
    a, b = impl_a.conciliar(datos), impl_b.conciliar(datos)
    try:
        leer_csv(str(ruta))
        reglas = "lee sin error"
    except ValueError as e:
        reglas = f"falla: {e}"

print(f"A sin error: usadas {a['usadas']} de {a['filas_leidas']}, excluidas {a['excluidas']}")
print(f"B: usadas {b['usadas']} de {b['filas_leidas']}, marcadas {b['marcadas']} · reglas {reglas}")
ok = a["usadas"] == 0 and b["usadas"] == len(FILAS) and reglas.startswith("falla")
print("REPRODUCIDO" if ok else "NO SE REPRODUJO")
sys.exit(0 if ok else 1)

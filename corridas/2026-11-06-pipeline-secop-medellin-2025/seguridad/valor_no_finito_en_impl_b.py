"""valor_no_finito_en_impl_b · impl_b.py publica valor_contratado = inf y el JSON sale con «Infinity».

impl_b.py:55 (NUMERO) acepta exponentes y :325 hace float(Decimal) sin mirar si es finito: «1e309» o dos
«1e308» del mismo NIT dan inf. El RUNNER de verificar.py solo cambia NaN por None, así que informe.json
(implementaciones.b.resultado, publicado) lleva el símbolo Infinity, que no es JSON estándar (JSON.parse de un
navegador lo rechaza). Contraste: impl_a toma 1e309 como no numérico y falla fuerte (OverflowError de
math.fsum) con dos 1e308; impl_b falla con decimal.Overflow si el exponente pasa de 999999.
Datos ficticios. Prueba de la revisión ciega (no es código de la IA). Solo escribe en una carpeta temporal.
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
C = Path(__file__).resolve().parent.parent
H = C.parent.parent / "herramientas"
sys.path.insert(0, str(H))
import verificar  # noqa: E402

ENC = "id_contrato,nit_entidad,codigo_entidad,nombre_entidad,fecha_de_firma,valor_del_contrato"


def csv_temporal(lineas):
    ruta = Path(tempfile.mkdtemp(prefix="seg-inf-")) / "contratos.csv"
    ruta.write_text("\n".join([ENC] + lineas) + "\n", encoding="utf-8")
    return str(ruta)


def cargar(archivo):
    spec = importlib.util.spec_from_file_location(Path(archivo).stem + "_bajo_prueba", C / archivo)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def estricto(texto):
    def rechazar(simbolo):
        raise ValueError(f"símbolo no estándar {simbolo}")
    try:
        json.loads(texto, parse_constant=rechazar)
        return "JSON estándar"
    except ValueError as e:
        return str(e)


datos = {"contratos": csv_temporal(["C1,890905211,1,ALCALDIA,2025-03-01T10:00:00.000,1e308",
                                    "C2,890905211,1,ALCALDIA,2025-03-02T10:00:00.000,1e308",
                                    "C3,890905212,1,GOBERNACION,2025-03-03T10:00:00.000,1e309"])}
filas, err = verificar.ejecutar_impl(C / "impl_b.py", datos)          # el camino real, en la caja
publicado = json.dumps({"resultado": filas}, ensure_ascii=False)
print(f"impl_b por verificar.ejecutar_impl: {filas} · error: {err}")
print(f"así queda en informe.json: {publicado[:120]} → con un lector estricto: {estricto(publicado)}")
try:
    cargar("impl_a.py").analizar(datos)
    a = "sin error"
except Exception as e:
    a = f"{type(e).__name__}: {e}"
print(f"impl_a con los mismos datos: {a}")
try:
    cargar("impl_b.py").analizar({"contratos": csv_temporal(["C1,890905211,1,ALCALDIA,2025-03-01T10:00:00.000,1e1000000"])})
    b = "sin error"
except Exception as e:
    b = type(e).__name__
print(f"impl_b con 1e1000000: {b}")
ok = err is None and filas and all(f["valor_contratado"] == float("inf") for f in filas) and "Infinity" in publicado
print("CONFIRMADO" if ok else "NO SE REPRODUJO")
sys.exit(0 if ok else 1)

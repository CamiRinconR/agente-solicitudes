"""csv_malformado_se_lee_en_silencio · impl_b.py, reglas.py e hipotesis.py leen un CSV roto sin avisar.

impl_b.py:136-151 (_leer_csv) y reglas_base.leer_csv (que usan reglas.py:32 e hipotesis.py:80) usan el
módulo csv con strict=False: una comilla sin cerrar se traga en silencio todas las filas que siguen, y un
separador de más corre las columnas de esa fila (impl_b recorta con zip y el contrato sale como
«sin_fecha_de_firma»). impl_a.py (pandas) falla en esos dos casos. Como reglas.py lee con el mismo lector
que impl_b, R1, R2, R4 y R8 pasan con la cifra equivocada (falla de modo común). impl_a tiene su propio modo
silencioso: la coma de más en la primera fila de datos corre todas las columnas. Al final corre
verificar.verificar() sobre una corrida temporal: B queda como resultado_oficial, que es lo que grafica
verificar_grafico.py (no mira el estado del informe).
Prueba de la revisión ciega (no es código de la IA). Solo escribe en una carpeta temporal.
"""
import contextlib
import importlib.util
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
C = Path(__file__).resolve().parent.parent
H = C.parent.parent / "herramientas"
sys.path.insert(0, str(H))
import reglas_base  # noqa: E402
import verificar  # noqa: E402

ENC = "id_contrato,nit_entidad,codigo_entidad,nombre_entidad,fecha_de_firma,valor_del_contrato"


def cargar(archivo):
    spec = importlib.util.spec_from_file_location(Path(archivo).stem + "_bajo_prueba", C / archivo)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def csv_temporal(lineas, carpeta=None):
    carpeta = Path(carpeta or tempfile.mkdtemp(prefix="seg-csv-"))
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / "contratos.csv"
    ruta.write_text("\n".join([ENC] + lineas) + "\n", encoding="utf-8")
    return str(ruta)


impl_a, impl_b, hip = cargar("impl_a.py"), cargar("impl_b.py"), cargar("hipotesis.py")
reglas_base.REGLAS.clear()
cargar("reglas.py")
REGLAS = {r["id"]: r for r in reglas_base.REGLAS}

BUENAS = [f"C{i},89090521{i},1,ALCALDIA {i},2025-03-0{i}T10:00:00.000,100" for i in (1, 2, 3)]
DESPUES = [f"D{i},81000000{i},1,ENTIDAD {i},2025-04-0{i}T10:00:00.000,200" for i in (1, 2, 3)]
CASOS = {
    "comilla sin cerrar en la fila 4 de 7": (
        BUENAS + ['C4,890905214,1,"ALCALDIA SIN CIERRE,2025-03-04T10:00:00.000,100'] + DESPUES, 7, 1000.0),
    "coma de más sin comillas en la fila 2 de 3": (
        [BUENAS[0], "C2,890905212,1,ALCALDIA, DISTRITO,2025-03-02T10:00:00.000,100", BUENAS[2]], 3, 300.0),
}

confirmados = []
for nombre, (lineas, contratos, total_real) in CASOS.items():
    datos = {"contratos": csv_temporal(lineas)}
    res_b, conc_b = impl_b.analizar(datos), impl_b.conciliar(datos)
    total_b = sum(f["valor_contratado"] for f in res_b)
    pasan = {rid: bool(REGLAS[rid]["fn"](dict(datos), res_b)[0]) for rid in ("R1", "R2", "R4", "R8")}
    cuentan_h = len(hip._cuentan(dict(datos))[0])
    try:
        impl_a.analizar(datos)
        error_a = None
    except Exception as e:  # lo esperado: pandas no acepta el archivo
        error_a = f"{type(e).__name__}: {str(e)[:70]}"
    print(f"[{nombre}] {contratos} contratos escritos, {total_real:,.0f} pesos")
    print(f"  impl_b sin error: lee {conc_b['filas_leidas']} filas, usa {conc_b['usadas']}, excluye "
          f"{conc_b['excluidas']}; suma {total_b:,.0f}")
    print(f"  reglas con el resultado de B: {pasan} · hipotesis.py cuenta {cuentan_h} contratos")
    print(f"  impl_a: {error_a or 'sin error'}")
    if error_a and all(pasan.values()) and total_b < total_real:
        confirmados.append(nombre)

# impl_a tampoco es inmune: con la coma de más en la PRIMERA fila de datos, pandas toma la primera columna
# como índice, corre todas las columnas y impl_a.py:113 la bota con reset_index(drop=True). No hay error.
primera = {"contratos": csv_temporal(["C1,890905211,1,ALCALDIA, DISTRITO,2025-03-01T10:00:00.000,100"] + BUENAS[1:])}
res_a1, conc_a1 = impl_a.analizar(primera), impl_a.conciliar(primera)
print(f"[coma de más en la primera fila de datos] impl_a sin error: {res_a1} · excluye {conc_a1['excluidas']} "
      f"(se escribieron 3 contratos de 3 NIT; las reglas sí lo atrapan: R1 "
      f"{'pasa' if REGLAS['R1']['fn'](dict(primera), res_a1)[0] else 'falla'})")
a_silencioso = len(res_a1) == 1 and res_a1[0]["nit_entidad"] == "1"

# Corrida temporal completa: spec y caso conocido de esta corrida, CSV con la comilla sin cerrar.
tmp = Path(tempfile.mkdtemp(prefix="seg-corrida-"))
spec = json.loads((C / "spec.json").read_text(encoding="utf-8"))
spec["datos"] = {"contratos": csv_temporal(CASOS["comilla sin cerrar en la fila 4 de 7"][0], tmp / "datos")}
(tmp / "spec.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
shutil.copy(C / "reglas.py", tmp / "reglas.py")
shutil.copytree(C / "caso_conocido", tmp / "caso_conocido")
with contextlib.redirect_stdout(io.StringIO()):
    verificar.verificar(tmp, {"a": C / "impl_a.py", "b": C / "impl_b.py"})
inf = json.loads((tmp / "informe.json").read_text(encoding="utf-8"))
oficial = inf.get("resultado_oficial") or []
print(f"[verificar.py de punta a punta] estado {inf['estado']} · resultado_oficial de "
      f"{inf.get('fuente_resultado')}: {len(oficial)} NIT, {sum(f['valor_contratado'] for f in oficial):,.0f} pesos "
      f"(se escribieron 7 contratos, 1.000 pesos)")
print(f"  motivos: {inf['motivos']}")
e2e = inf.get("fuente_resultado") == "b" and len(oficial) == 3
ok = len(confirmados) == len(CASOS) and e2e and a_silencioso
print("CONFIRMADO" if ok else "NO SE REPRODUJO")
sys.exit(0 if ok else 1)

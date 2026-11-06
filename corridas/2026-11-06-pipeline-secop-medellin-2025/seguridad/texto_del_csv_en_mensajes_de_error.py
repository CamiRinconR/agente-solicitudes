"""texto_del_csv_en_mensajes_de_error · el texto crudo de una celda llega a las salidas publicadas.

reglas.py:22 (_valor) hace float(t): con un texto, el ValueError trae la celda completa («could not convert
string to float: '…'»); verificar.py la copia en informe.json (reglas_rotas, mensajes) y en informe.md
(«Detalle de lo que falló», «Cifras de cada regla»). hipotesis.py:74 (_valor) arma su error con la celda y
solo cambia los dígitos por 9: letras, correos sin dígitos y HTML pasan a hipotesis_resultado.json (detalle).
Sin tope de largo. El barrido de gobernanza solo ve correos y cédulas con contexto, no nombres ni HTML, y en
informe.json solo barre resultado_oficial.
La prueba corre verificar.verificar() en una corrida temporal y el RUNNER real de verificar_hipotesis.py en la
caja. Datos ficticios. Prueba de la revisión ciega (no es código de la IA). Solo escribe en carpetas temporales.
"""
import contextlib
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
import caja  # noqa: E402
import verificar  # noqa: E402
import verificar_hipotesis  # noqa: E402
from gobernanza import escanear_texto  # noqa: E402

ENC = "id_contrato,nit_entidad,codigo_entidad,nombre_entidad,fecha_de_firma,valor_del_contrato"
CELDA = "Juan Pérez Gómez (juan.perez@correo.invalid) <img src=x onerror=alert(1)> " + "relleno " * 600
FILAS = ["C1,890905211,1,ALCALDIA,2025-03-01T10:00:00.000,100",
         f'C2,890905211,1,ALCALDIA,2025-03-02T10:00:00.000,"{CELDA}"',
         "C3,890905212,1,GOBERNACION,2025-03-03T10:00:00.000,300"]

tmp = Path(tempfile.mkdtemp(prefix="seg-error-"))
(tmp / "datos").mkdir()
ruta_csv = tmp / "datos" / "contratos.csv"
ruta_csv.write_text("\n".join([ENC] + FILAS) + "\n", encoding="utf-8")
spec = json.loads((C / "spec.json").read_text(encoding="utf-8"))
spec["datos"] = {"contratos": str(ruta_csv)}
(tmp / "spec.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
shutil.copy(C / "reglas.py", tmp / "reglas.py")
shutil.copytree(C / "caso_conocido", tmp / "caso_conocido")
with contextlib.redirect_stdout(io.StringIO()):
    verificar.verificar(tmp, {"a": C / "impl_a.py", "b": C / "impl_b.py"})
md = (tmp / "informe.md").read_text(encoding="utf-8")
inf_txt = (tmp / "informe.json").read_text(encoding="utf-8")
veces_md = md.count("Juan Pérez Gómez")
veces_json = inf_txt.count("Juan Pérez Gómez")
html_md = "<img src=x onerror=alert(1)>" in md
largo_mensaje = max((len(x) for x in json.loads(inf_txt)["reglas_rotas"]), default=0)
print(f"informe.md: el nombre aparece {veces_md} veces, el HTML crudo {'sí' if html_md else 'no'} está; "
      f"informe.json: {veces_json} veces; mensaje de regla más largo {largo_mensaje:,} caracteres")
print(f"  ejemplo: {json.loads(inf_txt)['reglas_rotas'][0][:120]}…")
print(f"  barrido de gobernanza sobre informe.md: {escanear_texto(md)} (no ve el nombre ni el HTML)")

salida, err = caja.correr(verificar_hipotesis.RUNNER, str(C / "hipotesis.py"),
                          json.dumps({"contratos": str(ruta_csv)}), str(H))
detalle = (salida or {}).get("H1", {}).get("error", "") if not err else ""
print(f"hipotesis_resultado.json (detalle de H1, por el RUNNER real en la caja): {detalle[:150]}…")
print(f"  largo {len(detalle):,} caracteres · trae el nombre: {'Juan Pérez Gómez' in detalle} · "
      f"el correo: {'juan.perez@correo.invalid' in detalle} · el HTML: {'<img src=x' in detalle}")
ok = (veces_md > 0 and html_md and veces_json > 0 and "Juan Pérez Gómez" in detalle
      and "<img src=x" in detalle and "Juan" not in str(escanear_texto(md)))
print("CONFIRMADO" if ok else "NO SE REPRODUJO")
sys.exit(0 if ok else 1)

"""enlace_externo_en_informe_final · un nombre_entidad con forma de enlace Markdown se vuelve un enlace vivo.

informe_final.py:199 (md_a_html.linea) escapa el HTML y después convierte [texto](ruta.html) en <a href>; la
ruta admite «//», así que «[ver detalle](//ejemplo.invalid/pago.html)» en nombre_entidad sale como enlace a
otro dominio en informe_final.html (publicado). El nombre llega ahí sin tocar por impl_a/impl_b (S4) y R5/R6
lo aceptan porque no está vacío y es el nombre real del NIT.
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
import informe_final  # noqa: E402
import verificar  # noqa: E402

ENC = "id_contrato,nit_entidad,codigo_entidad,nombre_entidad,fecha_de_firma,valor_del_contrato"
NOMBRE = "[ver detalle](//ejemplo.invalid/pago.html)"

spec = importlib.util.spec_from_file_location("impl_a_bajo_prueba", C / "impl_a.py")
impl_a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(impl_a)
tmp = Path(tempfile.mkdtemp(prefix="seg-enlace-"))
ruta = tmp / "contratos.csv"
ruta.write_text(f"{ENC}\nC1,890905211,1,{NOMBRE},2025-03-01T10:00:00.000,100\n", encoding="utf-8")
res = impl_a.analizar({"contratos": str(ruta)})
md = verificar.tabla_md(res, ["nit_entidad", "entidad", "valor_contratado", "numero_contratos"])
html = informe_final.md_a_html(md, "prueba")
enlace = '<a href="//ejemplo.invalid/pago.html">ver detalle</a>' in html
print(f"entidad devuelta por impl_a: {res[0]['entidad']!r}")
print(f"informe_final.html trae un enlace vivo a otro dominio: {enlace}")
ok = res[0]["entidad"] == NOMBRE and enlace
print("CONFIRMADO" if ok else "NO SE REPRODUJO")
sys.exit(0 if ok else 1)

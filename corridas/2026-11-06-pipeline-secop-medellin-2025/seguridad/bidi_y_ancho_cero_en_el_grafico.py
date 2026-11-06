"""bidi_y_ancho_cero_en_el_grafico · grafico.py deja pasar caracteres invisibles de formato al gráfico publicado.

grafico.py:56-59 (_limpio) quita solo la categoría Unicode Cc (control). Los de formato (Cf) siguen: U+202E
(escritura de derecha a izquierda) voltea en pantalla el texto que viene después, y U+200B (espacio de ancho
cero) hace que dos nombres distintos se vean iguales. Así un nombre_entidad puede mostrar en el eje y en el
cuadro emergente otra cosa que lo que dice el dato.
Datos ficticios. Prueba de la revisión ciega (no es código de la IA). No escribe archivos.
"""
import importlib.util
import json
import sys
import unicodedata
from pathlib import Path

sys.dont_write_bytecode = True
C = Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location("grafico_bajo_prueba", C / "grafico.py")
grafico = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grafico)
proc = json.loads((C / "datos" / "procedencia_contratos.json").read_text(encoding="utf-8"))
filas = [
    {"nit_entidad": "890905211", "entidad": "ENTIDAD ‮NILLEDEM ED", "valor_contratado": 3e9, "numero_contratos": 2},
    {"nit_entidad": "890905212", "entidad": "GOBERNACI​ON", "valor_contratado": 2e9, "numero_contratos": 1},
    {"nit_entidad": "890905213", "entidad": "GOBERNACION", "valor_contratado": 1e9, "numero_contratos": 1},
]
fig = grafico.graficar(filas, proc)
eje = list(fig.layout.yaxis.ticktext)
hover = [c[0] for c in fig.data[0].customdata]
invisibles = sorted({f"U+{ord(ch):04X}" for t in eje + hover for ch in t if unicodedata.category(ch) == "Cf"})
print(f"_limpio('A\\x96B\\u202eC') = {grafico._limpio('A' + chr(0x96) + 'B' + chr(0x202E) + 'C')!r} "
      "(quita el control U+0096, deja U+202E)")
print(f"etiquetas del eje: {eje}")
print(f"caracteres de formato que llegan al eje y al cuadro emergente: {invisibles}")
print(f"«GOBERNACI\\u200bON» y «GOBERNACION» se ven iguales y son distintos: {eje[1] != eje[2]}")
ok = "U+202E" in invisibles and "U+200B" in invisibles
print("CONFIRMADO" if ok else "NO SE REPRODUJO")
sys.exit(0 if ok else 1)

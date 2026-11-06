"""grafico.py (líneas 25-32 y 146): si la procedencia llega vacía, el pie del gráfico sale de un respaldo escrito
en el código (fuente, licencia y fecha de consulta del 06-11-2026), sin error ni aviso.

En esta corrida pasó: el verificador busca procedencia.json en la corrida y junto a la capa limpia, no la
encuentra (está en datos/), le pasa {} al gráfico y su comprobación «fuente y fecha de consulta visibles»
pasa en vacío. Datos sintéticos; no modifica el código revisado.

Uso: .venv/bin/python -B seguridad/procedencia_fija_en_grafico.py
Sale con 0 e imprime REPRODUCIDO si el patrón se reproduce; con 1 si ya no.
"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
CORRIDA = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(CORRIDA), str(CORRIDA.parent.parent / "herramientas")]
import grafico  # noqa: E402
from rutas import resolver  # noqa: E402

FILAS = [{"nit_entidad": "800000001", "entidad": "ENTIDAD DE PRUEBA", "valor_contratado": 5e9, "numero_contratos": 3}]


def pie(procedencia):
    return grafico.graficar(FILAS, procedencia).layout.annotations[0].text


vacia, ninguna = pie({}), pie(None)
otra = pie({"fuente": {"titulo": "OTRA FUENTE", "dominio": "otro.example", "conjunto": "x0", "atribucion": "Otra",
                       "licencia": "CC0"}, "consultado": "2027-02-01T10:00:00"})
fijo = all("consultado el 06-11-2026" in t and "CC BY-SA 4.0" in t for t in (vacia, ninguna))
usa_la_que_llega = "01-02-2027" in otra and "06-11-2026" not in otra
print(f"con procedencia vacía o None el pie dice «consultado el 06-11-2026» y «CC BY-SA 4.0»: {fijo}")
print(f"con otra procedencia usa la que llega: {usa_la_que_llega}")

spec = json.loads((CORRIDA / "spec.json").read_text(encoding="utf-8"))
buscadas = [CORRIDA / "procedencia.json"] + [Path(resolver(r)).parent / "procedencia.json" for r in spec["datos"].values()]
no_hay = not any(p.exists() for p in buscadas)
verif = json.loads((CORRIDA / "grafico_verificacion.json").read_text(encoding="utf-8"))
det = next(c["detalle"] for c in verif["comprobaciones"] if c["comprobacion"].startswith("fuente y fecha"))
en_vacio = "«fuente»" in det and "fecha []" in det
print(f"el verificador no encuentra procedencia en {[p.relative_to(CORRIDA).as_posix() for p in buscadas]}: {no_hay}")
print(f"su comprobación pasó sin procedencia («{det}»): {en_vacio}")

ok = fijo and usa_la_que_llega and no_hay and en_vacio
print("REPRODUCIDO" if ok else "NO SE REPRODUJO")
sys.exit(0 if ok else 1)

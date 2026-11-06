#!/usr/bin/env python3
"""Integridad del pipeline (sin IA): ¿alguien cambió las herramientas, las fichas o las reglas durante la corrida?

Uso:
  python herramientas/integridad.py --sellar <corrida>/integridad.json     al inicio, antes de cualquier agente
  python herramientas/integridad.py --comprobar <corrida>/integridad.json  al final, antes del informe

Un agente con acceso a archivos podría editar verificar.py para que todo apruebe, o quitar un caso de la batería.
El manifiesto guarda la huella SHA-256 de cada archivo protegido al inicio y la compara al final:
  - herramientas, fichas de los agentes, flujo, dependencias y librerías permitidas: no pueden cambiar;
  - baterías: solo pueden crecer (el revisor de seguridad agrega casos); modificar o borrar un caso es una alerta.
"""
import hashlib
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FIJOS = ["herramientas/*.py", "herramientas/permitidas.json", "requirements.txt", "flujo.js", "agentes/*.md"]
CRECEN = ["baterias/**/*"]


def huellas(patrones):
    out = {}
    for pat in patrones:
        for p in sorted(RAIZ.glob(pat)):
            if p.is_file() and "__pycache__" not in p.parts:
                out[str(p.relative_to(RAIZ))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def sellar(destino):
    m = {"fijos": huellas(FIJOS), "crecen": huellas(CRECEN)}
    Path(destino).parent.mkdir(parents=True, exist_ok=True)
    Path(destino).write_text(json.dumps(m, indent=1), encoding="utf-8")
    print(f"Integridad sellada: {len(m['fijos'])} archivos fijos y {len(m['crecen'])} de las baterías.")
    return 0


def comprobar(origen):
    m = json.loads(Path(origen).read_text(encoding="utf-8"))
    ahora_f, ahora_c = huellas(FIJOS), huellas(CRECEN)
    cambiados = sorted(k for k in set(m["fijos"]) | set(ahora_f) if m["fijos"].get(k) != ahora_f.get(k))
    tocados = sorted(k for k in m["crecen"] if ahora_c.get(k) != m["crecen"][k])
    nuevos = sorted(set(ahora_c) - set(m["crecen"]))
    alertas = [f"cambió una herramienta, ficha o regla: {k}" for k in cambiados] + \
              [f"se modificó o borró un caso de las baterías: {k}" for k in tocados]
    out = {"estado": "intacta" if not alertas else "alterada", "alertas": alertas, "casos_nuevos_en_baterias": nuevos}
    Path(origen).with_name("integridad_comprobacion.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Integridad {out['estado']}" + (f": {len(alertas)} alerta(s)" if alertas else "") +
          (f" · {len(nuevos)} caso(s) nuevo(s) en las baterías" if nuevos else ""))
    for a in alertas:
        print(f"  ✗ {a}")
    print("RESUMEN " + json.dumps(out, ensure_ascii=False))
    return 1 if alertas else 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) != 2 or a[0] not in ("--sellar", "--comprobar"):
        raise SystemExit(__doc__)
    sys.exit(sellar(a[1]) if a[0] == "--sellar" else comprobar(a[1]))

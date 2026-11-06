#!/usr/bin/env python3
"""Auditoría de independencia (sin IA): ¿algún subagente abrió lo que su ficha le prohíbe?

Uso: python evidencia/blindaje/auditar_independencia.py <carpeta de transcripciones del flujo> [...]

Lee las transcripciones (agent-*.jsonl) de una corrida orquestada, reconoce el rol de cada agente por su
instrucción y revisa cada herramienta que usó (leer archivos, comandos) contra lo que su rol no puede leer.
Hoy la independencia depende de la instrucción: esto mide si se cumple.
"""
import json
import re
import sys
from pathlib import Path

PROHIBIDO = {
    "generador A": [r"reglas\.py", r"caso_conocido", r"sellos\.json", r"impl_b\.py"],
    "generador B": [r"reglas\.py", r"caso_conocido", r"sellos\.json", r"impl_a\.py"],
    "reparador A": [r"(?<!/)reglas\.py", r"impl_b\.py"],
    "reparador B": [r"(?<!/)reglas\.py", r"impl_a\.py"],
    "probador": [r"bitacora/[\w.-]+\.json", r"impl_a\.py", r"impl_b\.py"],
    "revisor ciego de seguridad": [r"bitacora/[\w.-]+\.json"],
    "custodio": [r"(cat|head|tail|less|sed -n|awk)[^|;&]*datos/[^ ]*\.csv", r"datos/contratos\.csv\"?\s*$"],
}


PROPIA = {"probador": "3-analisis-prueba.json", "revisor ciego de seguridad": "5-gobernanza-seguridad.json"}


def rol(texto):
    t = texto
    for patron, nombre in [(r"Eres el GENERADOR A\b", "generador A"), (r"Eres el GENERADOR B\b", "generador B"),
                           (r"REPARADOR de [^\n]*impl_a", "reparador A"), (r"REPARADOR de [^\n]*impl_b", "reparador B"),
                           (r"Eres el PROBADOR", "probador"), (r"Eres el REVISOR DE SEGURIDAD", "revisor ciego de seguridad"), (r"Eres el CUSTODIO", "custodio")]:
        if re.search(patron, t):
            return nombre
    return None


def usos(lineas):
    for l in lineas:
        try:
            d = json.loads(l)
        except json.JSONDecodeError:
            continue
        msg = d.get("message") or {}
        for c in (msg.get("content") or []) if isinstance(msg.get("content"), list) else []:
            if isinstance(c, dict) and c.get("type") == "tool_use":
                i = c.get("input") or {}
                yield c.get("name"), " ".join(str(i.get(k, "")) for k in ("file_path", "command", "path", "pattern") if i.get(k))


def primera_instruccion(lineas):
    """Junta los primeros mensajes del usuario: el primero suele ser el contexto que se inyecta al iniciar."""
    textos = []
    for l in lineas:
        try:
            d = json.loads(l)
        except json.JSONDecodeError:
            continue
        msg = d.get("message") or {}
        if msg.get("role") == "user":
            c = msg.get("content")
            textos.append(c if isinstance(c, str) else " ".join(x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text"))
            if len(textos) >= 4:
                break
    return "\n".join(textos)


def main(carpetas):
    total, violaciones = 0, []
    for carpeta in carpetas:
        for f in sorted(Path(carpeta).glob("agent-*.jsonl")):
            lineas = f.read_text(encoding="utf-8", errors="ignore").splitlines()
            r = rol(primera_instruccion(lineas))
            if not r:
                continue
            total += 1
            for herramienta, arg in usos(lineas):
                propia = PROPIA.get(r)
                for p in PROHIBIDO[r]:
                    m = re.search(p, arg)
                    if m and propia and propia in m.group(0):
                        continue    # su propia bitácora: la escribe y la relee, como pide su ficha
                    if m and not re.search(r"(seguridad|dependencias|verificar|verificar_hipotesis|validar_aporte)\.py", arg):
                        violaciones.append({"corrida": Path(carpeta).name, "rol": r, "herramienta": herramienta, "uso": arg[:180]})
    print(f"Agentes con rol auditado: {total} · usos prohibidos: {len(violaciones)}")
    for v in violaciones[:40]:
        print(f"  ✗ [{v['corrida']}] {v['rol']} · {v['herramienta']}: {v['uso']}")
    print("RESUMEN " + json.dumps({"agentes": total, "violaciones": len(violaciones)}, ensure_ascii=False))
    return 1 if violaciones else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

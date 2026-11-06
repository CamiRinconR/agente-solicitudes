#!/usr/bin/env python3
"""¿Puede cualquier persona hacer fork y proponer un aporte? Comprobación sin IA de la configuración pública del repositorio.

Uso: python herramientas/abierta_a_aportes.py [dueño/repositorio]      (por defecto CristianBTA/agente-solicitudes)

Consulta lo mismo que ve un participante sin iniciar sesión (si existe GITHUB_TOKEN, lo usa solo para no chocar con
el límite de consultas de la API):
  1. el repositorio es público y no está archivado ni deshabilitado;
  2. se permite el fork (en un repositorio público de una cuenta personal, GitHub no deja apagarlo);
  3. cualquiera puede abrir pull requests (pull_request_creation_policy = all);
  4. el formulario «Proponer un aporte» está disponible (issues activos y la plantilla en main);
  5. el instructivo APORTAR-CON-TU-AGENTE.md se sirve desde main.
Sale con 1 si algo impide aportar. El flujo .github/workflows/abierta-a-aportes.yml lo corre cada día: si falla,
GitHub le avisa al dueño por correo.
"""
import json
import os
import sys
import urllib.error
import urllib.request


def pedir(url):
    cab = {"User-Agent": "agente-solicitudes (comprobación de aportes)", "Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN") and "api.github.com" in url:
        cab["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=cab), timeout=30) as r:  # nosec B310
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, ""


def main(argv):
    repo = argv[0] if argv else "CristianBTA/agente-solicitudes"
    res = []
    st, cuerpo = pedir(f"https://api.github.com/repos/{repo}")
    if st != 200:
        print(f"✗ el repositorio {repo} no responde en la API pública (HTTP {st}): nadie podría verlo ni hacer fork")
        return 1
    d = json.loads(cuerpo)
    res.append(("público", d.get("visibility") == "public" and not d.get("private"), f"visibilidad {d.get('visibility')}"))
    res.append(("activo", not d.get("archived") and not d.get("disabled"),
                "ni archivado ni deshabilitado" if not d.get("archived") and not d.get("disabled") else "archivado o deshabilitado"))
    res.append(("fork permitido", d.get("allow_forking") is True, f"allow_forking = {d.get('allow_forking')}"))
    politica = d.get("pull_request_creation_policy")
    res.append(("pull requests de cualquiera", politica in ("all", None),
                f"pull_request_creation_policy = {politica}" + (" (la API no lo expone; se revisa a mano)" if politica is None else "")))
    res.append(("issues activos", d.get("has_issues") is True, f"has_issues = {d.get('has_issues')}"))
    st, _ = pedir(f"https://api.github.com/repos/{repo}/contents/.github/ISSUE_TEMPLATE/aporte.yml?ref=main")
    res.append(("formulario «Proponer un aporte»", st == 200, f"plantilla en main: HTTP {st}"))
    st, md = pedir(f"https://raw.githubusercontent.com/{repo}/main/APORTAR-CON-TU-AGENTE.md")
    res.append(("instructivo publicado", st == 200 and "Instrucciones para el agente" in md, f"APORTAR-CON-TU-AGENTE.md: HTTP {st}"))
    for nombre, ok, detalle in res:
        print(f"  {'✓' if ok else '✗'} {nombre}: {detalle}")
    fallas = [n for n, ok, _ in res if not ok]
    print("RESUMEN " + json.dumps({"repositorio": repo, "abierto_a_aportes": not fallas, "fallas": fallas}, ensure_ascii=False))
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

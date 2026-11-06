import re

# Patrón de reglas.py, línea 25: controles bidireccionales (U+200F, U+202A, U+202E) y separadores de
# línea (U+2028, U+2029) escritos crudos dentro de un literal. Es el patrón Trojan Source (CVE-2021-42574):
# un editor puede mostrar un código distinto del que corre. Lo correcto es escribirlos como escapes \u202a.
INVISIBLES = re.compile("[​-‏  ‪-‮⁠﻿]")


def analizar(datos):
    return []

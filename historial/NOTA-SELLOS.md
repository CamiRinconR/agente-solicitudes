# Nota sobre un sello que se rehízo

**6 de noviembre de 2026.** En la corrida `corridas/2026-11-06-secop-medellin-2025`, el archivo `caso_conocido/cuentas.md` traía la ruta temporal del script con el que el especificador comprobó su cuenta a mano. Era una ruta de la máquina donde se corrió, sin valor para nadie más.

Antes de publicar el repositorio se reemplazó esa ruta por el texto «un script de comprobación aparte (fuera del repositorio)». No cambió ninguna cifra, regla ni dato del caso conocido. Como el archivo está sellado, se volvió a sellar la corrida. Cambiar un sello es una decisión humana, y por eso queda esta constancia.

- Huella SHA-256 anterior de `cuentas.md`: `3f88395f3594095f0fc21dca157e469252a20b112c9923ec8dc0f3f86867b1fc`
- Huella SHA-256 nueva: `8886c8b1fbccb5312412fde15e2c5ddbe1586786d5349e0cea92108e77bf15bd`
- Ningún otro archivo sellado cambió de huella (`spec.json`, `reglas.py`, `caso_conocido/contratos.csv` y `esperado.json` quedaron iguales).

## Segundo sello rehecho: invisibles literales en reglas.py (Trojan Source)

**6 de noviembre de 2026.** En la corrida `corridas/2026-11-06-pipeline-completo-secop-medellin-2025`, la compuerta de seguridad (Bandit B613), que desde ese día también revisa `reglas.py`, lo bloqueó. La lista de caracteres invisibles que la IA quería quitar traía seis de ellos pegados literales dentro del código (U+200B, U+200F, U+202A, U+202E, U+2060 y U+FEFF), que es el patrón *Trojan Source* (lección L21).

Se reemplazó cada uno por su secuencia de escape (`\u200f`). La cadena que Python obtiene al ejecutar es idéntica antes y después (se comprobó con el árbol de sintaxis), la autoprueba da el mismo resultado y ninguna otra regla cambió. Como `reglas.py` está sellado, se volvió a sellar, y queda esta constancia.

- Huella SHA-256 anterior de `reglas.py`: `5115133d21512b2c39f8abe89bd85f431f2268ea3d5297ed630a4cf58225a12c`
- Huella SHA-256 nueva: `e99fed23eab4338441c476729fe90d9b2058e3058f5288320f29203f52485c5d`

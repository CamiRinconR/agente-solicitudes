# Lector
**Etapa:** 1 · Ingesta · **Parámetros:** Máximo 3 intentos de contrato. Esfuerzo alto.

La IA escribe el lector: un **contrato de datos** que dice qué traer, con qué tipos y qué tiene que cumplir. El código lo ejecuta y prueba la carga.

## Puede leer
- La petición y el glosario del negocio.
- Los metadatos de la fuente: nombres, tipos y descripciones de las columnas (en Socrata, `/api/views/<conjunto>.json`).
- Conteos de la fuente (`$select=count(*)`) o el perfil de `herramientas/perfilar.py`.
- El formato del contrato, en `herramientas/ingesta.py`.

## No puede leer (independencia)
- Filas de datos: el primer acercamiento es con estructura y conteos, no mirando registros.

## Entrega
- `contrato_<tabla>.json`: fuente (con `filtro_legible`), tabla, llave, `columnas` con su tipo (`texto`, `entero`, `decimal` o `fecha`), `dominios` y `rangos` duros, `avisos` blandos y, si hiciera falta, `personales_justificadas`.
- La carga, `datos/<tabla>.csv`, y su procedencia, `datos/procedencia_<tabla>.json`: las escribe la herramienta, no el agente.

## Reglas
- **Minimización (D7):** solo las columnas que la petición necesita, más la llave.
- Los identificadores van como texto, aunque la fuente los declare número (R11).
- Filtrar en la fuente lo que no se necesita, y escribir el filtro en palabras.
- Si las fechas traen hora, cortar con `< inicio del período siguiente`, nunca contra `aaaa-mm-dd` como texto (lección L02).
- Rangos y dominios duros solo para lo que el filtro garantiza. Lo imposible (valor ≤ 0, valores enormes) va como aviso: se cuenta y se reporta, no se corrige (R7).

## Nunca
- Relajar una prueba para que la carga pase: si un dato real viola un rango, el rango era un supuesto equivocado y se pasa a aviso.
- Pedir columnas personales o de texto libre sin justificación.

## Prueba sin IA que lo comprueba
`python herramientas/ingesta.py contrato_<tabla>.json --salida datos --repetir`: conteo contra la fuente, llave única y sin nulos, tipos declarados (FAILFAST), rangos, dominios, minimización, columnas que existen en la fuente, y correr dos veces da el mismo archivo byte a byte. Si algo falla, la carga se rechaza.

Además, las [reglas comunes](00-reglas-comunes.md) y la bitácora de su etapa.

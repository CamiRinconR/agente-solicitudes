# Limpiador
**Etapa:** 2 · Procesamiento · **Parámetros:** Esfuerzo alto.

La IA propone la limpieza; `herramientas/limpieza.py` la ejecuta igual cada vez y la prueba. Del dato crudo sale la **capa limpia**, con las mismas filas y una marca por cada problema.

## Puede leer
- `spec.json` (tratamiento de los datos), `perfil.json`, las lecciones y el formato del plan en `herramientas/limpieza.py`.

## No puede leer (independencia)
- Las implementaciones, el caso conocido y las reglas.

## Entrega
- `plan_limpieza_<tabla>.json`: entrada cruda, salida `limpio/<tabla>.csv`, llave, operaciones (texto, invisibles y Unicode, reemplazar, nulos disfrazados, mapear, fecha, número, rango, atípicos, repetidos, comparar) y umbrales (completitud, validez, unicidad y máximo de filas marcadas).
- La actualización de `spec.json`: `datos_crudos`, `datos` (la capa limpia) y `capa_limpia` (qué significa cada marca y si excluye la fila o solo avisa).

## Reglas
- **Limpiar es marcar (R14):** nada se borra. Cada problema queda en `calidad_<marca>` y `calidad_ok` dice si la fila está limpia.
- Los mapas de variantes van completos, como lista cerrada; lo que quede fuera se marca, no se adivina.
- Los nulos disfrazados («No Definido», «N/A», «-») se vuelven vacío y se marcan.
- Se quitan los caracteres invisibles y se normaliza a Unicode NFC.
- Atípicos y valores imposibles se marcan con un método explícito (rango intercuartílico sobre log10); no se corrigen (R7).

## Nunca
- Tocar el dato crudo.
- Borrar filas.
- Ajustar un umbral sin anotar por qué: si el dato real lo incumple, el umbral era un supuesto y se escribe en la bitácora.

## Prueba sin IA que lo comprueba
`python herramientas/limpieza.py plan_limpieza_<tabla>.json`: mismas filas antes y después, dato crudo intacto (huella), llave y orden conservados, completitud y validez antes y después, y umbrales. El caso conocido pasa por el mismo plan dentro de `verificar.py`.

Además, las [reglas comunes](00-reglas-comunes.md) y la bitácora de su etapa.

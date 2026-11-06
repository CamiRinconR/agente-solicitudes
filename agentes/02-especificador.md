# Especificador
**Etapa:** 2 · Procesamiento · **Parámetros:** Esfuerzo alto.

Convierte la petición de una frase en una **solicitud precisa y comprobable**. No escribe el análisis: escribe qué debe salir, cómo se tratan los datos y cómo se comprueba.

## Puede leer
- La petición, el glosario y las lecciones.
- El perfil de los datos crudos (`perfil.json`, de `herramientas/perfilar.py`).
- Los CSV crudos, para comprobar sus cuentas.

## No puede leer (independencia)
- Ninguna implementación: todavía no existen, y no debe escribirlas.

## Entrega
- `spec.json`: interpretación; definiciones con su fuente (`glosario`, `datos` o `supuesto`); tratamiento de los datos; supuestos con su alternativa e impacto; preguntas con su valor por defecto; salida (claves, valores, tolerancia, orden); `columnas_usadas` (R1); `anticipo` (rango de magnitud escrito antes de ejecutar); `conciliacion_requerida`.
- `reglas.py`: de 4 a 8 reglas ejecutables (conservación, cobertura, unicidad, dominio, completitud), solo con la biblioteca estándar.
- `caso_conocido/`: de 8 a 25 filas hechas a mano con cada borde (fechas límite, repetidos, vacíos, variantes), `esperado.json` y la cuenta fila por fila en `cuentas.md`.

## Reglas
- Cada hallazgo del perfil que mueve la cifra termina en un tratamiento **y** en una regla o en el caso conocido.
- Lo que el perfil demuestra (por ejemplo, «día primero» porque hay fechas con barras cuyo primer número es mayor que 12) es fuente `datos`, no un supuesto.
- Solo se pregunta lo que ni el glosario ni los datos resuelven y que cambia la cifra.
- Las reglas son más simples que el análisis y no comparten su lógica: la conservación se calcula sin unir tablas (D9).
- Las reglas y el caso conocido van sobre el dato **crudo**, para que un error de limpieza también se atrape.

## Nunca
- Escribir `impl_a.py` o `impl_b.py`.
- Sellar el criterio: eso lo hace el revisor.

## Prueba sin IA que lo comprueba
`python herramientas/verificar.py <corrida> --autoprueba`: todas las reglas pasan sobre el caso conocido con su resultado esperado. Si una falla, está mal la regla o la cuenta.

Además, las [reglas comunes](00-reglas-comunes.md) y la bitácora de su etapa.

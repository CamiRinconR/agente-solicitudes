# Graficador
**Etapa:** 4 · Visualización · **Parámetros:** Máximo 3 intentos.

La IA genera el gráfico que responde la pregunta. Lo comprueba una lista sin IA, y el HTML lo escribe el verificador, no el código de la IA.

## Puede leer
- El resultado aprobado, la petición y la procedencia (fuente y fecha de consulta).

## No puede leer (independencia)
- Los datos crudos: grafica lo aprobado.

## Entrega
- `grafico.json`: pregunta, medida, categoría, período, `periodo_incompleto`, `escala` y `fuera_del_grafico`, si deja algo por fuera.
- `grafico.py`: `graficar(resultado, procedencia)`, que devuelve una figura de Plotly.

## Reglas
- Barras desde cero: factor de mentira 1.
- Título con qué, dónde y cuándo; unidades en el eje de valores.
- Fuente y fecha de consulta (dd-mm-aaaa) visibles.
- Si muestra solo los primeros N, agrega «Otras» o declara lo que quedó fuera: la cuenta de control debe cerrar.
- Período incompleto marcado; ningún dato personal.

## Nunca
- Escribir o mostrar archivos.
- Cortar el eje para «hacer ver» una diferencia.

## Prueba sin IA que lo comprueba
`python herramientas/verificar_grafico.py <corrida>`: compuertas, cuenta de control con escala, eje desde cero y factor de mentira, título con período, unidades, fuente y fecha, período incompleto y barrido de datos personales en todo el texto del gráfico.

Además, las [reglas comunes](00-reglas-comunes.md) y la bitácora de su etapa.

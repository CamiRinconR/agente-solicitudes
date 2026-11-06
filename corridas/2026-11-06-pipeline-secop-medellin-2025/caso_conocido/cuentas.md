# Caso con respuesta conocida: cuentas fila por fila

Datos inventados (NIT y nombres de prueba). 23 filas leídas. Las filas se numeran en el orden del archivo, sin contar el encabezado.

Orden de decisión por fila: 1) ¿id_contrato (sin espacios, en mayúsculas) ya apareció? → `repetido_id_contrato` (se mira ANTES de la fecha, S6); 2) ¿fecha vacía o sin formato aaaa-mm-dd ni dd/mm/aaaa? → `sin_fecha_de_firma`; 3) ¿año de firma distinto de 2025? → `fuera_de_2025`; si no, se usa.

| # | id_contrato | NIT (sin espacios) | nombre (sin espacios) | fecha_de_firma | valor | decisión | qué prueba |
|---|---|---|---|---|---|---|---|
| 1 | …0000001 | 900000001 | ALCALDIA DE PRUEBA | 2025-01-01T00:00:00.000 | 1.000.000 | usa | primer día del año (y que no se corra de zona horaria) |
| 2 | …0000002 | 900000001 | CONCEJO DE PRUEBA | 2025-04-05T10:30:00.000 | 2.500.000,75 | usa | ISO con día <= 12 (L01); decimal que no se puede truncar |
| 3 | …0000003 | 900000001 | ALCALDIA DE PRUEBA | 2025-12-31T23:59:59.999 | 3.000.000 | usa | 31-dic a las 23:59 (L02) |
| 4 | …0000004 | 900000001 | CONCEJO DE PRUEBA | 31/12/2025 18:00:00 | 0 | usa | fecha con barras, valor cero |
| 5 | …0000005 | 900000001 | CONCEJO DE PRUEBA | 2024-12-31T23:59:59.999 | 9.000.000 | fuera_de_2025 | último instante de 2024; su nombre no cuenta para elegir el nombre |
| 6 | …0000006 | 900000001 | CONCEJO DE PRUEBA | 2026-01-01T00:00:00.000 | 8.000.000 | fuera_de_2025 | primer instante de 2026; su nombre no cuenta para elegir el nombre |
| 7 | …0000007 | 900000002 | UNIVERSIDAD DE PRUEBA | 2025-03-15T08:00:00.000 | 4.000.000 | usa | primera aparición |
| 8 | …0000007 | 900000002 | UNIVERSIDAD DE PRUEBA | 2025-03-15T08:00:00.000 | 4.000.000 | repetido_id_contrato | fila idéntica |
| 9 | co1.pccntr.0000007␣ | 900000002 | UNIVERSIDAD DE PRUEBA | 2025-05-20T09:00:00.000 | 7.777.777 | repetido_id_contrato | variante en minúsculas y con espacio, otro valor (se queda el primero) |
| 10 | …0000010 | 900000002 | UNIVERSIDAD DE PRUEBA (venía con espacio al final) | 2025-06-30T12:00:00.000 | 1.500.000 | usa | nombre con espacio sobrante |
| 11 | …0000011 | 900000002 | U. DE PRUEBA | 2025-07-01T09:00:00.000 | 750.000,25 | usa | segundo nombre del NIT, menos frecuente |
| 12 | …0000012 | 900000002 | UNIVERSIDAD DE PRUEBA | (vacía) | 6.000.000 | sin_fecha_de_firma | fecha vacía |
| 13 | …0000013 | 8000000013 (venía « 8000000013») | INSTITUTO DE PRUEBA | 2025-09-09T09:09:09.000 | 10.000.000 | usa | NIT de 10 dígitos con espacio |
| 14 | …0000014 | 8000000013 | INSTITUTO DE PRUEBA | 2025-10-10T10:10:10.000 | (vacío) → 0 | usa | valor vacío = 0 (S3) |
| 15 | …0000015 | 900000004 | EMPRESA SIN 2025 | 2024-07-01T00:00:00.000 | 7.000.000 | fuera_de_2025 | entidad sin 2025 |
| 16 | …0000016 | 900000004 | EMPRESA SIN 2025 | 30/06/2026 | 2.000.000 | fuera_de_2025 | barras sin hora, 2026 |
| 17 | …0000017 | 900000005 | HOSPITAL DE PRUEBA | 2025-02-02T02:02:02.000 | 6.000.000,50 | usa | |
| 18 | …0000018 | 900000005 | HOSPITAL DE PRUEBA | 2025-11-11T11:11:11.000 | 0 | usa | valor cero |
| 19 | …0000019 | 900000006 | MUSEO DE PRUEBA | 05/02/2025 10:00:00 | 1 | usa | dd/mm/aaaa con día <= 12, valor simbólico |
| 20 | …0000020 | 900000006 | MUSEO DE PRUEBA | 2025-08-08T08:00:00.000 | 5.999.999,50 | usa | empate de valor con el NIT 900000005 |
| 21 | …0000021 | 900000004 | EMPRESA SIN 2025 | 2024-12-15T10:00:00.000 | 3.000.000 | fuera_de_2025 | primera aparición de un id fuera de 2025 |
| 22 | …0000021 | 900000004 | EMPRESA SIN 2025 | 2025-01-15T10:00:00.000 | 3.000.000 | repetido_id_contrato | repetido con fecha de 2025: se quita repetidos antes de mirar la fecha (S6), así que 900000004 sigue sin salir |
| 23 | …0000023 | 8000000013 | INSTITUTO DE PRUEBA | 2025-10-10T10:10:10.000 | (vacío) → 0 | usa | gemelo de la fila 14 con otro id_contrato: no es repetido (L08, solo se depura por la llave) |

## Conciliación

- Leídas: 23
- Usadas: 14 (filas 1, 2, 3, 4, 7, 10, 11, 13, 14, 17, 18, 19, 20, 23)
- Excluidas: repetido_id_contrato 3 (filas 8, 9, 22) · sin_fecha_de_firma 1 (fila 12) · fuera_de_2025 5 (filas 5, 6, 15, 16, 21)
- 14 + 3 + 1 + 5 = 23 ✓

## Por NIT

| NIT | filas usadas | valor_contratado | numero_contratos | nombres (conteo) | entidad |
|---|---|---|---|---|---|
| 8000000013 | 13, 14, 23 | 10.000.000 + 0 + 0 = 10.000.000 | 3 | INSTITUTO DE PRUEBA 3 | INSTITUTO DE PRUEBA |
| 900000001 | 1, 2, 3, 4 | 1.000.000 + 2.500.000,75 + 3.000.000 + 0 = 6.500.000,75 | 4 | ALCALDIA DE PRUEBA 2, CONCEJO DE PRUEBA 2 (empate; contando las filas 5 y 6, fuera de 2025, ganaría CONCEJO 4 a 2, y eso es un error) | ALCALDIA DE PRUEBA (menor en orden de texto) |
| 900000002 | 7, 10, 11 | 4.000.000 + 1.500.000 + 750.000,25 = 6.250.000,25 | 3 | UNIVERSIDAD DE PRUEBA 2, U. DE PRUEBA 1 | UNIVERSIDAD DE PRUEBA (gana por frecuencia aunque «U. DE PRUEBA» va antes en orden de texto) |
| 900000005 | 17, 18 | 6.000.000,50 + 0 = 6.000.000,50 | 2 | HOSPITAL DE PRUEBA 2 | HOSPITAL DE PRUEBA |
| 900000006 | 19, 20 | 1 + 5.999.999,50 = 6.000.000,50 | 2 | MUSEO DE PRUEBA 2 | MUSEO DE PRUEBA |
| 900000004 | ninguna | — | — | — | no sale |

Totales: valor 10.000.000 + 6.500.000,75 + 6.250.000,25 + 6.000.000,50 + 6.000.000,50 = 34.750.002 · contratos 3 + 4 + 3 + 2 + 2 = 14.

## Orden

valor_contratado de mayor a menor: 8000000013 (10.000.000) · 900000001 (6.500.000,75) · 900000002 (6.250.000,25) · empate en 6.000.000,50 entre 900000005 y 900000006, que se resuelve por NIT ascendente como texto: 900000005 antes que 900000006.

## Errores que este caso atrapa (al comparar con esperado.json)

- Perder el 31-dic con hora (fila 3) o el 1-ene por zona horaria (fila 1): 900000001 queda corto.
- Contar 2024 o 2026 (filas 5, 6, 15, 16, 21): 900000001 sube o aparece 900000004.
- No quitar repetidos (filas 8, 9) o quitarlos sin normalizar (fila 9): 900000002 sube.
- Filtrar la fecha antes de quitar repetidos (filas 21, 22): aparece 900000004 con 3.000.000.
- Depurar por (entidad, valor, fecha) (fila 23, L08): 8000000013 baja a 2 contratos.
- Excluir el valor vacío (filas 14, 23): 8000000013 baja a 1 contrato.
- Truncar decimales (fila 2): 900000001 baja 0,75 (más que la tolerancia de 0,5).
- Agrupar por codigo_entidad o nombre: 900000001 y 900000002 se parten.
- Elegir el nombre por orden de texto, sin frecuencia (900000002), contando filas fuera de 2025 (900000001) o sin quitar espacios (fila 10).
- NIT como número decimal o con espacio (fila 13): la clave no coincide.

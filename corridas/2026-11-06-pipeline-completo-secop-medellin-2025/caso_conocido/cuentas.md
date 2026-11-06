# Caso con respuesta conocida: cuenta fila por fila

Datos inventados (NIT, códigos, nombres e id ficticios). 23 filas en `contratos.csv` (las filas 22 y 23 y el U+0096 de la fila 19 los agregó la revisión del 6-nov-2026). Cada fila va a un solo motivo, el primero que aplique en este orden: sin_id_contrato, repetido, sin_fecha_de_firma, fuera_de_2025, sin_nit_entidad.

| Fila | id_contrato | NIT | Fecha | Valor | Qué pasa | Qué prueba |
|---|---|---|---|---|---|---|
| 1 | …1000001 | 900000001 | 2025-01-01T00:00:00 | 1.000.000 | usada (A) | primer día del año |
| 2 | …1000002 | 900000001 | 2025-04-05T08:30 | 2.500.000,50 | usada (A) | ISO con día <= 12 (L01); nombre con espacio final; decimales |
| 3 | …1000003 | 900000001 | 2025-12-31T23:59:59 | 3.000.000 | usada (A) | último día con hora (L02); otro código y otro nombre en el mismo NIT (L05) |
| 4 | …1000004 | 900000001 | 05/04/2025 | 4.000.000 | usada (A) | dd/mm/aaaa, día primero |
| 5 | …1000001 | 900000001 | 2025-01-01 | 1.000.000 | excluida: repetido | repetido exacto de la fila 1 |
| 6 | (vacío) | 900000001 | 2025-03-03 | 9.999.999 | excluida: sin_id_contrato | id vacío |
| 7 | …1000007 | 900000002 | 2025-06-15 | 5.000.000 | usada (B) | nombre HOSPITAL… |
| 8 | …1000008 | « 900000002 » | 31/12/2025 | 7.000.000,25 | usada (B) | NIT con espacios; 31/12 en dd/mm; nombre ESE HOSPITAL… |
| 9 | «…1000007 » | 900000002 | 2025-06-16 | 8.888.888 | excluida: repetido | id con espacio final y otro valor: vale la primera aparición (fila 7) |
| 10 | …1000010 | 900000002 | (vacía) | 1.234.567 | excluida: sin_fecha_de_firma | fecha vacía |
| 11 | …1000011 | 900000002 | 2025-02-30T10:00 | 2.222.222 | excluida: sin_fecha_de_firma | fecha que no existe |
| 12 | …1000012 | 9000000035 | 2025-07-01 | 0 | usada (C) | valor cero cuenta; NIT de 10 dígitos |
| 13 | …1000013 | 9000000035 | 2025-08-20T14:45:10.123 | 1.500.000,75 | usada (C) | decimales |
| 14 | …1000014 | 9000000035 | 2024-12-31T23:59:59.999 | 6.000.000 | excluida: fuera_de_2025 | último instante de 2024 |
| 15 | …1000015 | 900000004 | 2025-09-09 | 200.000.000.000 | usada (D) | valor atípico, se conserva |
| 16 | …1000016 | 900000004 | 2025-10-10 | 1 | usada (D) | valor de 1 peso, se conserva |
| 17 | …1000017 | 900000004 | 2026-01-01T00:00:00 | 7.000.000 | excluida: fuera_de_2025 | primer instante de 2026 |
| 18 | …1000018 | 900000004 | 15/06/2024 | 3.000.000 | excluida: fuera_de_2025 | dd/mm de otro año |
| 19 | …1000019 | 900000005 | 2025-11-11 | (vacío) | usada (E), suma 0 | valor vacío cuenta y suma 0 (S4); nombre con el control U+0096 entre espacios, que se lee como «–» |
| 20 | …1000020 | 900000006 | 2025-05-05 | 0 | usada (F) | entidad solo con valor cero; empate de valor con E |
| 21 | …1000021 | (vacío) | 2025-03-15 | 4.444.444 | excluida: sin_nit_entidad | NIT vacío |
| 22 | …1000014 | 9000000035 | 2025-03-01 | 5.000.000 | excluida: repetido | mismo id que la fila 14 (de 2024): la depuración va antes del filtro de fecha (S3); si se filtrara primero, C sumaría 5.000.000 y 3 contratos |
| 23 | co1.pccntr.1000013 | 9000000035 | 2025-09-01 | 999 | excluida: repetido | el id de la fila 13 en minúsculas: es el mismo contrato |

## Por entidad

- **A · 900000001**: filas 1, 2, 3, 4 → 1.000.000 + 2.500.000,50 + 3.000.000 + 4.000.000 = **10.500.000,50**; **4** contratos. Nombres entre las usadas: «ALCALDIA PRUEBA ALFA» 3 (la fila 2 queda igual al recortar), «CONCEJO PRUEBA ALFA» 1 → **ALCALDIA PRUEBA ALFA**. Dos codigo_entidad, una sola entidad.
- **B · 900000002**: filas 7, 8 → 5.000.000 + 7.000.000,25 = **12.000.000,25**; **2** contratos. Nombres entre las usadas: «HOSPITAL PRUEBA BETA» 1 y «ESE HOSPITAL PRUEBA BETA» 1, empate → el menor en orden de texto: **ESE HOSPITAL PRUEBA BETA** («E» < «H»). Si se contaran también las excluidas 9, 10 y 11, ganaría HOSPITAL: es la trampa.
- **C · 9000000035**: filas 12, 13 → 0 + 1.500.000,75 = **1.500.000,75**; **2** contratos; **INSTITUTO PRUEBA GAMA**. Las filas 22 y 23 no suman: son repetidos.
- **D · 900000004**: filas 15, 16 → 200.000.000.000 + 1 = **200.000.000.001**; **2** contratos; **EMPRESA PRUEBA DELTA**.
- **E · 900000005**: fila 19 → **0**; **1** contrato; **CORPORACION PRUEBA – EPSILON** (el U+0096 se cambia por «–»; si se borrara, o se dejara, el nombre no coincide).
- **F · 900000006**: fila 20 → **0**; **1** contrato; **FONDO PRUEBA ZETA**.

## Orden

D (200.000.000.001) · B (12.000.000,25) · A (10.500.000,50) · C (1.500.000,75) · E (0, 900000005) · F (0, 900000006): E y F empatan en 0 y van por NIT ascendente como texto.

## Totales y conciliación

- valor_contratado total: 200.000.000.001 + 12.000.000,25 + 10.500.000,50 + 1.500.000,75 + 0 + 0 = **200.024.000.002,50**.
- numero_contratos total: 4 + 2 + 2 + 2 + 1 + 1 = **12**.
- Conciliación: 23 leídas = 12 usadas + 11 excluidas (sin_id_contrato 1, repetido 4, sin_fecha_de_firma 2, fuera_de_2025 3, sin_nit_entidad 1).

## Comprobación aparte

Un script en pandas que no usa reglas.py (lee todo como texto, depura por id recortado con la primera aparición, lee aaaa-mm-dd y dd/mm/aaaa por separado con errors='coerce', suma con Decimal) dio exactamente esperado.json, con su orden, y la misma conciliación. `verificar.py --autoprueba`: 8/8 reglas pasan.

Revisión (6-nov-2026): dos recuentos propios del revisor, uno desde la capa limpia del caso con sus marcas y otro desde el crudo en pandas (id recortado y en mayúsculas, formatos de fecha por separado, Decimal), dieron exactamente esperado.json con su orden y la conciliación 23 = 12 + 11.

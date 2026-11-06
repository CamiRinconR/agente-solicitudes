# Cuentas a mano del caso conocido

Archivo: `caso_conocido/contratos.csv` (18 filas de datos). Reglas: contrato único por `id_contrato` (primera aparición), firmado en 2025 según los 10 primeros caracteres de `fecha_de_firma` (bordes incluidos), `ciudad` = Medellín tras quitar espacios, mayúsculas y tildes, `valor_del_contrato` tal cual (los de valor 0 cuentan), sin filtrar por estado; agrupar por `nit_entidad`; nombre = el `nombre_entidad` más frecuente entre los contratos que cuentan del NIT, con empate resuelto por orden alfabético.

| Fila | NIT | nombre_entidad | id_contrato | fecha_de_firma | ciudad | estado | valor | ¿Cuenta? | Por qué |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 800000001 | ENTIDAD ALFA | …9000001 | 2025-03-10T09:15 | Medellín | En ejecución | 1.000.000 | Sí | 2025; facturado 500.000 y pagado 400.000 no se usan |
| 2 | 800000001 | ENTIDAD ALFA | …9000002 | 2025-06-20T14:00 | Medellín | Modificado | 2.500.000,50 | Sí | decimales |
| 3 | 800000001 | ENTIDAD ALFA | …9000003 | 2025-11-05T08:30 | Medellín | terminado | 750.000 | Sí | estado en minúscula, cuenta |
| 4 | 800000001 | ENTIDAD ALFA | …9000001 | 2025-03-10T09:15 | Medellín | En ejecución | 1.000.000 | No | id repetido (igual a la fila 1) |
| 5 | 800000001 | ALFA SEDE NORTE | …9000004 | 2025-08-01T10:00 | Medellín | cedido | 300.000 | Sí | otro nombre y otro codigo_entidad, mismo NIT |
| 6 | 800000001 | ALFA SEDE NORTE | …9000005 | 2024-09-01T10:00 | Medellín | Cerrado | 9.000.000 | No | 2024 |
| 7 | 800000001 | ALFA SEDE NORTE | …9000006 | 2024-10-01T11:00 | Medellín | Cerrado | 8.000.000 | No | 2024 |
| 8 | 800000001 | ALFA SEDE NORTE | …9000007 | 2026-02-01T10:00 | Medellín | En ejecución | 7.000.000 | No | 2026 |
| 9 | 8000000025 | BETA COMPRADOR | …9000008 | 2025-02-14T11:00 | Medellín | Aprobado | 0 | Sí | valor cero: cuenta 1 contrato, suma 0 |
| 10 | 8000000025 | B BETA | …9000009 | 2025-07-07T16:45 | Medellín | Suspendido | 1.200.000 | Sí | suspendido cuenta |
| 11 | 8000000025 | BETA COMPRADOR | …9000010 | 2024-12-31T23:59:59.999 | Medellín | Cerrado | 5.000.000 | No | último instante de 2024 |
| 12 | 900000003 | ENTIDAD GAMA | …9000011 | 2026-01-01T00:00 | Medellín | En ejecución | 4.000.000 | No | primer instante de 2026 |
| 13 | 900000003 | ENTIDAD GAMA | …9000012 | 2024-07-15T09:00 | Medellín | Cerrado | 600.000 | No | 2024 |
| 14 | 900000004 | DELTA DISTRITAL* | …9000013 | 2025-01-01T00:00 | Medellín | En ejecución | 123.456,78 | Sí | primer día de 2025 |
| 15 | 900000004 | DELTA DISTRITAL* | …9000014 | 2025-12-31T18:51:58.966 | Medellín | Modificado | 2.000.000,22 | Sí | último día con hora: comparar el texto completo contra «2025-12-31» lo dejaría fuera |
| 16 | 900000004 | DELTA DISTRITAL* | …9000015 | 2025-12-31T23:59:59.999 | Medellín | terminado | 100.000 | Sí | último instante de 2025 |
| 17 | 900000004 | DELTA DISTRITAL* | …9000016 | 2025-09-09T09:09 | MEDELLIN | Cerrado | 0 | Sí | ciudad sin tilde y en mayúsculas = Medellín; valor cero |
| 18 | 900000005 | MUNICIPIO EPSILON | …9000017 | 2025-05-05T10:00 | Envigado | En ejecución | 999.999 | No | ciudad distinta de Medellín |

## Por entidad

**NIT 800000001** — filas 1, 2, 3, 5.
- valor = 1.000.000 + 2.500.000,50 + 750.000 + 300.000 = **4.550.000,50**
- contratos = **4** (la fila 4 es la misma 1)
- nombre: entre los 4 que cuentan, ENTIDAD ALFA 3 · ALFA SEDE NORTE 1 → **ENTIDAD ALFA**. (Trampa: contando todo el archivo sin quitar repetidos queda 4 a 4 y el desempate daría ALFA SEDE NORTE; contando todo el archivo quitando repetidos gana ALFA SEDE NORTE 4 a 3.)

**NIT 900000004** — filas 14, 15, 16, 17.
- valor = 123.456,78 + 2.000.000,22 + 100.000 + 0 = **2.223.457,00**
- contratos = **4**
- nombre: **DELTA DISTRITAL*** (único, se conserva el asterisco).

**NIT 8000000025** — filas 9, 10.
- valor = 0 + 1.200.000 = **1.200.000,00**
- contratos = **2**
- nombre: BETA COMPRADOR 1 · B BETA 1 → empate; en orden alfabético «B BETA» < «BETA COMPRADOR» (el espacio va antes de la E) → **B BETA**. (Trampa: contando todo el archivo gana BETA COMPRADOR 2 a 1.)

**NIT 900000003** (GAMA): ningún contrato de 2025 → **no sale**.
**NIT 900000005** (EPSILON): su único contrato no es de Medellín → **no sale**.

## Totales y orden

- valor total = 4.550.000,50 + 2.223.457,00 + 1.200.000,00 = **7.973.457,50**
- contratos = 4 + 4 + 2 = **10**
- orden por valor de mayor a menor: 800000001, 900000004, 8000000025.

## Segunda comprobación

Script aparte con `datetime.fromisoformat` y `Decimal` (otra forma de leer fechas y sumar):
un script de comprobación aparte (fuera del repositorio) → resultado idéntico a `esperado.json` («IGUAL»).

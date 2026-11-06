# Cuentas del caso conocido (hechas a mano)

Regla aplicada a cada fila: fecha dd/mm/aaaa (día primero) o aaaa-mm-dd; entra si 2026-01-01 ≤ fecha ≤ 2026-06-30; cada `numero_documento` una sola vez; FV suma `subtotal`, NC resta `subtotal`; IVA no cuenta; `cliente_id` sin espacios y en mayúsculas; región = la del registro más reciente del cliente en el maestro, normalizada a la lista oficial; sin código o código fuera del maestro → «Sin región».

## Región vigente de cada cliente (maestro)

| cliente | registros | vigente (fecha más reciente) | región normalizada |
|---|---|---|---|
| C001 | «CALDAS » 2025-06-30 | 2025-06-30 | Caldas |
| C002 | Antioquia 2026-04-30 (1.º en el archivo) · Bogotá D.C. 2024-05-29 | 2026-04-30 | Antioquia |
| C003 | Risaralda 2023-11-16 (1.º en el archivo) · «Bogota D.C.» 2026-04-30 | 2026-04-30 | Bogotá D.C. |
| C004 | « Antioquia» | 2024-08-13 | Antioquia |
| C005 | «Valle» | 2025-01-10 | Valle del Cauca |
| C006 | «Valle del cauca» | 2025-02-11 | Valle del Cauca |
| C007 | «BOGOTA DC» | 2025-04-05 | Bogotá D.C. |
| C008 | «risaralda» | 2024-03-01 | Risaralda |
| C009 | «ANTIOQUIA» | 2023-05-05 | Antioquia |
| C010 | «Bogotá» | 2024-07-07 | Bogotá D.C. |
| C011 | Caldas | 2025-09-09 | Caldas |

## Documento por documento

| # | documento | tipo | fecha leída | ¿entra? | cliente normalizado | región | aporte |
|---|---|---|---|---|---|---|---|
| 1 | FV-000001 | FV | 2026-01-01 | sí (borde) | C001 | Caldas | +1.000.000 |
| 2 | FV-000002 | FV | 15/02/2026 → 15-feb | sí | c002 → C002 | Antioquia (vigente; la vieja era Bogotá) | +2.000.000 |
| 3 | FV-000003 | FV | 03/07/2026 → 3-jul | no (leído mes primero sería 7-mar y entraría) | C004 | — | 0 |
| 4 | FV-000004 | FV | 05/03/2026 → 5-mar | sí | « C003» → C003 | Bogotá D.C. (vigente; la vieja era Risaralda) | +1.500.000 |
| 5 | FV-000005 | FV | 30/06/2026 → 30-jun | sí (borde) | «C005 » → C005 | Valle del Cauca | +800.000 (IVA 0) |
| 6 | FV-000006 | FV | 2026-07-01 | no | C006 | — | 0 |
| 7 | FV-000007 | FV | 2025-12-31 | no | C007 | — | 0 |
| 8 | FV-000008 | FV | 2026-03-20 | sí | C006 | Valle del Cauca | +1.200.000 |
| 9 | FV-000009 | FV | 2026-04-10 | sí | C007 | Bogotá D.C. | +600.000 |
| 10 | FV-000009 | FV | repetida idéntica | no (ya contado) | — | — | 0 |
| 11 | NC-000001 | NC | 2026-05-15 | sí | C002 | Antioquia | −300.000 |
| 12 | NC-000002 | NC | 12/06/2026 → 12-jun | sí (leído mes primero sería 6-dic y saldría) | C001 | Caldas | −100.000 |
| 13 | FV-000010 | FV | 2026-02-02 | sí | (vacío) | Sin región | +400.000 |
| 14 | FV-000011 | FV | 2026-05-05 | sí | C901 (no está en el maestro) | Sin región | +250.000 |
| 15 | NC-000003 | NC | 2026-06-01 | sí | c901 → C901 | Sin región | −50.000 |
| 16 | FV-000012 | FV | 2025-12-15 | no | C008 | — | 0 |
| 17 | FV-000013 | FV | 2026-02-28 | sí | C009 | Antioquia | +450.000 |
| 18 | FV-000014 | FV | 2026-06-15 | sí | C010 | Bogotá D.C. | +550.000 |
| 19 | FV-000015 | FV | 10/01/2026 → 10-ene | sí (leído mes primero sería 1-oct y saldría) | C011 | Caldas | +650.000 |
| 20 | FV-000016 | FV | 2026-03-03 | sí | « c004» → C004 | Antioquia | +700.000 |
| 21 | FV-000017 | FV | 2026-04-04 | sí | «c003 » → C003 | Bogotá D.C. | +1.000.000 |
| 22 | FV-000018 | FV | 2026-05-05 | sí | C005 | Valle del Cauca | +300.000 (IVA 0) |

## Sumas por región

- Antioquia: 2.000.000 − 300.000 + 450.000 + 700.000 = **2.850.000**
- Bogotá D.C.: 1.500.000 + 600.000 + 550.000 + 1.000.000 = **3.650.000** (FV-000009 una sola vez)
- Caldas: 1.000.000 − 100.000 + 650.000 = **1.550.000**
- Risaralda: su único cliente vigente (C008) solo tiene una venta de diciembre de 2025 → **0** (la fila sale igual)
- Valle del Cauca: 800.000 + 1.200.000 + 300.000 = **2.300.000**
- Sin región: 400.000 + 250.000 − 50.000 = **600.000**
- Total: **10.950.000** (17 documentos del semestre)

## Trampas que este caso detecta

- Contar FV-000009 dos veces: Bogotá 4.250.000.
- Leer fechas mes primero: sale NC-000002 y FV-000015, entra FV-000003.
- Usar el registro más antiguo o el primero del archivo para C003: Risaralda ≠ 0 y Bogotá baja.
- Unir sin normalizar `cliente_id`: c002, « C003», «C005 », «c003 », « c004» caerían en «Sin región» (están las cuatro formas del perfil: a999, ␣A999, A999␣, ␣a999).
- Sumar NC en vez de restarlas, o usar `total` (con IVA) en vez de `subtotal`.
- Descartar las ventas sin cliente: falta la fila «Sin región».

- Mandar «Valle» o «Bogotá» a otra fila (o a «Sin región»): Valle del Cauca o Bogotá D.C. bajan.
- Ordenar mal la salida o no dejar «Sin región» al final: lo atrapa R7.

## Segunda comprobación

Script aparte con pandas (`drop_duplicates`, `merge` con `validate="many_to_one"`, `groupby`), independiente de reglas.py: dio exactamente Antioquia 2.850.000 · Bogotá D.C. 3.650.000 · Caldas 1.550.000 · Risaralda 0 · Valle del Cauca 2.300.000 · Sin región 600.000 · total 10.950.000, 17 documentos.


Revisión independiente (6-nov): FV-000016 pasó a « c004» para cubrir la forma ␣a999 del perfil; las sumas no cambian. Recalculado con un script aparte (pandas, `drop_duplicates`, `merge`, `groupby`): mismas seis cifras y total 10.950.000.

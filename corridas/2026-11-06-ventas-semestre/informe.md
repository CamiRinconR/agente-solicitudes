# Ventas totales por región del primer semestre de 2026

**Estado: ✅ aprobado.** Las dos implementaciones pasan todas las reglas, aciertan el caso con respuesta conocida y dan exactamente lo mismo.

## Resultado
| region | ventas_netas |
|---|---|
| Antioquia | 1.047.887.700 |
| Bogotá D.C. | 500.740.800 |
| Caldas | 406.930.100 |
| Valle del Cauca | 275.593.500 |
| Risaralda | 112.992.600 |
| Sin región | 42.052.800 |
| **Total** | **2.386.197.500** |

_Fuente: implementación A._

## Lo que se entendió
Sale una cifra por región: las ventas netas sin IVA del 1 de enero al 30 de junio de 2026, ambos días incluidos. Ventas netas = suma del subtotal de las facturas de venta (FV) menos la suma del subtotal de las notas crédito (NC) cuya fecha cae en el semestre. Cada documento cuenta una sola vez aunque esté repetido en el archivo. La región de cada documento es la región vigente de su cliente (la del registro más reciente del maestro), aunque la venta sea anterior al cambio. Las regiones son las cinco oficiales (Antioquia, Bogotá D.C., Caldas, Risaralda, Valle del Cauca), con sus variantes de escritura unificadas; los documentos sin cliente o con un código que no está en el maestro no se descartan: van a una sexta fila «Sin región». Queda fuera el IVA, la columna total y todo documento con fecha de diciembre de 2025 o de julio de 2026.

## Definiciones y de dónde sale cada una
| termino | definicion | fuente |
|---|---|---|
| Ventas (ventas_netas) | Suma de subtotal de los documentos FV menos suma de subtotal de los documentos NC. El subtotal de las NC viene en positivo y se resta. Nunca se usan las columnas iva ni total. | glosario |
| Primer semestre de 2026 | Documentos con fecha entre 2026-01-01 y 2026-06-30, ambos incluidos. Cada documento (FV o NC) cuenta en su propia fecha. | glosario |
| Documento | Lo identifica numero_documento; cada uno cuenta una sola vez. | glosario |
| Cliente | Código C seguido de tres dígitos (C017). Para cruzar ventas con el maestro, el código se compara después de quitar espacios al inicio y al final y pasar a mayúsculas (ver tratamiento de datos). | glosario |
| Región de una venta | Región del registro del cliente con la fecha_actualizacion más reciente en clientes.csv, sin importar la fecha de la venta ni el orden de las filas en el archivo. | glosario |
| Regiones oficiales | Antioquia, Bogotá D.C., Caldas, Risaralda y Valle del Cauca, escritas exactamente así en la salida. | glosario |
| Sin región | Etiqueta exacta «Sin región» solo para los documentos sin cliente identificado: sin cliente_id, o con un cliente_id que, tras quitar espacios y pasar a mayúsculas, no está en el maestro. Un cliente que sí está en el maestro nunca va a «Sin región». | glosario |
| Formato de fecha con barras | dd/mm/aaaa (día primero): 258 de las 424 fechas con barras tienen el primer número mayor que 12 y ninguna tiene el segundo mayor que 12. | datos |

## Tratamiento de los datos
- **ventas.fecha mezcla formatos: 1.096 filas aaaa-mm-dd y 424 dd/mm/aaaa; 258 con barras tienen el primer número > 12 y 0 tienen el segundo > 12 (150 son ambiguas a simple vista)** → Leer aaaa-mm-dd como ISO y toda fecha con barras como día/mes/año (también las ambiguas como 03/07/2026 = 3 de julio). Nunca dejar que la librería adivine el formato. _(fuente: datos)_
- **ventas trae fechas fuera del período: rango 2025-12-01 a 2026-07-31; de los 1.490 documentos únicos, 203 son de diciembre de 2025 y 171 de julio de 2026 (374 fuera)** → Quedarse solo con 2026-01-01 ≤ fecha ≤ 2026-06-30, bordes incluidos (quedan 1.116 documentos). _(fuente: glosario)_
- **ventas tiene 30 filas idénticas a otra anterior; numero_documento tiene 1.490 valores distintos en 1.520 filas (30 repetidos, siempre en filas idénticas); contarlas sumaría 76.333.800 netos de más en todo el archivo** → Quitar repetidos por numero_documento (sin espacios, en mayúsculas) quedándose con la primera aparición, antes de filtrar y sumar. _(fuente: glosario)_
- **ventas.tipo_documento tiene solo FV (1.430) y NC (90); las NC traen subtotal positivo (0 negativos en subtotal); 65 NC caen en el semestre por 58.350.500** → FV suma subtotal; NC resta subtotal. Cualquier otro tipo (tras quitar espacios y pasar a mayúsculas) no cuenta. _(fuente: glosario)_
- **ventas.iva tiene 222 ceros y 1.298 filas con 19 %; total = subtotal + iva en las 1.520 filas** → Usar solo subtotal; ignorar iva y total. _(fuente: glosario)_
- **ventas.cliente_id tiene 28 valores con espacios sobrantes y escrituras en minúscula (formas a999×12, A999␣×11, ␣a999×9): 31 grupos de variantes de un mismo código; 40 filas cruzan con el maestro solo tras quitar espacios y pasar a mayúsculas** → Quitar espacios al inicio y al final y pasar a mayúsculas en ventas.cliente_id y en clientes.cliente_id antes de cruzar. _(fuente: datos)_
- **ventas.cliente_id tiene 6 vacíos y 16 filas con códigos que no están en el maestro (C901, C902, C903, C904, C905); en el semestre son 17 documentos por 42.052.800 netos** → No descartarlos: sumarlos en la fila «Sin región». _(fuente: glosario)_
- **clientes.cliente_id tiene 5 códigos repetidos (C002, C019, C023, C035, C037), 65 filas para 60 clientes; en C035 y C037 el registro más reciente es el segundo del archivo; no hay empates de fecha_actualizacion** → Por cada cliente (código normalizado) quedarse con el registro de fecha_actualizacion más reciente (aaaa-mm-dd en todas las filas) antes de cruzar, para que la unión no duplique ventas. Si hubiera empate, el último en el archivo (supuesto S3). _(fuente: glosario)_
- **clientes.region tiene 14 escrituras para 5 regiones (7 con espacios sobrantes): «Antioquia», « Antioquia», «ANTIOQUIA»; «Bogotá D.C.», «Bogota D.C.», «BOGOTA DC», «Bogotá»; «Caldas», «CALDAS »; «Risaralda», «risaralda»; «Valle del Cauca», «Valle del cauca», «Valle»** → Normalizar: quitar espacios sobrantes, minúsculas, sin tildes, sin puntos. Luego antioquia → Antioquia; bogota dc y bogota → Bogotá D.C.; caldas → Caldas; risaralda → Risaralda; valle del cauca y valle → Valle del Cauca. Si la región vigente de un cliente no encaja en ninguna, el análisis se detiene con un error que nombre el cliente y la región (no se manda a «Sin región», que es solo para clientes no identificados; supuesto S2). En estos datos no pasa. _(fuente: datos)_
- **Una región oficial podría quedar sin ventas en el semestre (en los datos reales todas tienen ventas)** → La salida tiene siempre las seis filas (cinco oficiales + «Sin región»), con 0 donde no haya ventas (supuesto S1). _(fuente: supuesto)_

## Supuestos (confírmalos)
| id | decision | alternativa | impacto |
|---|---|---|---|
| S1 | La salida tiene siempre seis filas: las cinco regiones oficiales y «Sin región», aunque alguna valga 0. | Mostrar solo las regiones con ventas. | No cambia ninguna cifra; solo si aparece o no una fila con 0. En los datos reales todas tienen ventas. |
| S2 | «Valle» se lee como Valle del Cauca y «Bogotá» como Bogotá D.C. Si apareciera una región que no encaja en la lista oficial, el análisis se detiene con un error que la nombra, en vez de asignarla a alguna fila. | Dejar «Valle» y «Bogotá» como regiones aparte, o sumar la región desconocida a «Sin región» (el glosario reserva «Sin región» para ventas sin cliente identificado). | En los datos reales «Valle» y «Bogotá» son un cliente cada uno; si quedaran aparte, partirían Valle del Cauca y Bogotá D.C. No hay regiones desconocidas en los datos, así que la detención no ocurre. |
| S3 | Si dos registros del mismo cliente tuvieran la misma fecha_actualizacion, manda el último del archivo. | El primero del archivo. | Ninguno con estos datos: no hay empates. |

## Preguntas abiertas
Ninguna: el glosario y los datos resuelven todo lo que cambia la cifra.

## Comprobaciones
| Comprobación | Tipo | Qué verifica | A | B |
|---|---|---|---|---|
| R1 | conservacion | La suma de ventas_netas de todas las filas es igual a las ventas netas del semestre calculadas directo de ventas (FV menos NC sobre subtotal, cada documento una vez, fechas dd/mm/aaaa o aaaa-mm-dd), sin unir con clientes | ✅ | ✅ |
| R2 | cobertura | La fila «Sin región» vale exactamente las ventas netas del semestre de los documentos sin cliente_id o con un cliente_id que, tras quitar espacios y pasar a mayúsculas, no está en el maestro de clientes | ✅ | ✅ |
| R3 | unicidad | Cada región aparece una sola vez en el resultado (ninguna fila repetida) | ✅ | ✅ |
| R4 | dominio | El resultado tiene exactamente seis filas, una por cada etiqueta de la lista cerrada (Antioquia, Bogotá D.C., Caldas, Risaralda, Valle del Cauca, Sin región), escritas tal cual, aunque valgan 0; ninguna región queda partida por variantes de escritura | ✅ | ✅ |
| R5 | completitud | Las cinco regiones oficiales juntas valen las ventas netas del semestre de los documentos cuyo cliente está en el maestro (lo identificado no se pierde ni se va a «Sin región») | ✅ | ✅ |
| R6 | rango | Cada ventas_netas es un número finito y ninguna fila supera en valor absoluto la suma del subtotal de todas las FV del semestre (cota bruta); el IVA no entra | ✅ | ✅ |
| R7 | orden | Las filas salen en el orden de la spec: las cinco regiones oficiales de mayor a menor ventas_netas (los empates, en cualquier orden) y «Sin región» de última | ✅ | ✅ |
| Caso conocido | respuesta conocida | Con datos pequeños hechos a mano, el resultado es el esperado | ✅ | ✅ |
| A = B | doble implementación | Las dos implementaciones independientes dan lo mismo | ✅ | |
| Compuertas | seguridad y librerías | Sin código peligroso ni librerías fuera de la lista, antes de ejecutar (corre en caja de arena: sin red ni escritura) | ✅ | ✅ |
| Repetible | correr dos veces da lo mismo | La segunda corrida da exactamente el mismo resultado | ✅ | ✅ |
| Conciliación | todo conteo cierra | Filas leídas = usadas + excluidas por motivo; nada se borra en silencio | — | — |
| Tiempo | medir | Segundos de una corrida con los datos reales | 0.3 s | 0.18 s |

## Cifras de cada regla (implementación A)
- **R1**: resultado 2,386,197,500 · fuente 2,386,197,500 (1116 documentos del semestre)
- **R2**: «Sin región» en el resultado 42,052,800 · fuente 42,052,800 (17 documentos sin cliente identificado)
- **R3**: 6 filas, 6 regiones distintas; repetidas: ninguna
- **R4**: 6 filas de 6; faltan: ninguna; fuera de la lista: ninguna
- **R5**: regiones oficiales en el resultado 2,344,144,700 · fuente 2,344,144,700 (1099 documentos con cliente identificado)
- **R6**: cota bruta FV del semestre 2,444,548,000; filas fuera de rango: ninguna
- **R7**: orden: ['Antioquia', 'Bogotá D.C.', 'Caldas', 'Valle del Cauca', 'Risaralda', 'Sin región']; pares fuera de orden: ninguno

_Criterio sellado: sí, sin cambios._

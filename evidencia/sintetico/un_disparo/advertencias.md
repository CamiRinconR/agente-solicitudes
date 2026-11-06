# Ejemplo sintético · advertencias de los tres generadores de un solo disparo

Lo que cada generador de un solo disparo le dijo a quien pidió el análisis, tal cual.

## Generador 1

Las cifras están en pesos. Son ventas netas sin IVA del 1-ene al 30-jun-2026, con los dos días incluidos, según el glosario del negocio. El total es $2.386.197.500: el subtotal de 1.051 facturas (FV, $2.444.548.000) menos 65 notas crédito (NC, $58.350.500). El IVA no cuenta; con IVA serían $2.766.790.034. Un cálculo independiente en Python puro, sin pandas, da las mismas cifras.

1. «Sin región» suma $42.052.800 (1,8 % del total):
   - 5 facturas sin código de cliente, por $9.596.100: FV-000194, FV-000252, FV-000330, FV-000872 y FV-001154.
   - 12 facturas de los códigos C901, C902, C904 y C905, que no están en el maestro de clientes, por $32.456.700.
   Si son clientes reales, al registrarlos en el maestro y asignar cliente a esas 5 facturas, esas ventas pasan a su región.

2. Dos clientes cambiaron de región en pleno semestre, con actualización del 30-abr-2026: C002 pasó de Bogotá D.C. a Antioquia, y C037 de Risaralda a Bogotá D.C. Según el glosario, todo su semestre cuenta en la región actual, también lo vendido antes del cambio ($29.414.600 de C002 y $24.806.000 de C037). Si se quisiera la región que tenía el cliente el día de cada venta, cambiarían tres regiones:
   - Antioquia bajaría $29.414.600.
   - Bogotá D.C. subiría $4.608.600.
   - Risaralda subiría $24.806.000.

3. Dos nombres de región del maestro son abreviaturas que asigné por deducción y conviene confirmar: «Valle» (C027, $45.550.800) quedó en Valle del Cauca, y «Bogotá» (C036, $36.413.700) en Bogotá D.C. El maestro escribe las 5 regiones de 14 formas («CALDAS », « Antioquia», «BOGOTA DC», «risaralda»…); las demás variantes solo cambian en mayúsculas, tildes, puntos o espacios.

4. Limpié los datos sin cambiar la definición de venta:
   - Duplicados: 30 documentos venían repetidos con datos idénticos (23 dentro del semestre) y se contaron una vez. Contados dos veces, el total subiría $56.944.800.
   - Fechas: 424 venían como DD/MM/AAAA y el resto como AAAA-MM-DD. Las leí con el día primero, porque 258 tienen el primer número mayor que 12 y ninguna el segundo, así que el formato es el mismo en todo el archivo.
   - Códigos de cliente: 33 del semestre traían espacios o minúscula y se corrigieron (« c023» → C023).
   - Periodo: quedaron fuera 203 documentos de diciembre de 2025 y 171 de julio de 2026.

5. Cada nota crédito resta en su propia fecha. El archivo no dice a qué factura corresponde, así que una NC de este semestre puede devolver una venta de diciembre.

6. El script evidencia/sintetico/un_disparo/base_1/analisis.py se detiene con un error claro, en vez de adivinar, si aparece algo que el glosario no resuelve: un documento repetido con datos distintos, una fecha que no se pueda leer, una región que no sea oficial, un subtotal negativo o un cliente con dos regiones en la misma fecha. Los duplicados, los formatos de fecha y la forma de escribir códigos y regiones conviene corregirlos en los sistemas de donde salen los datos.

## Generador 2

Las cifras están en pesos. Son ventas netas sin IVA: el subtotal de las facturas (FV) menos el subtotal de las notas crédito (NC). Entran los documentos fechados entre el 1 de enero y el 30 de junio de 2026, cada uno con la región que hoy tiene su cliente, como dice el glosario. El total del semestre es $2.386.197.500: 1.051 facturas por $2.444.548.000 menos 65 notas crédito por $58.350.500. Las seis filas suman ese total, y un segundo cálculo hecho por otra vía dio las mismas cifras.

1. «Sin región» suma $42.052.800 (1,8 %). Son 5 facturas sin código de cliente ($9.596.100) y 12 facturas con códigos que no están en el maestro: C901, C902, C904 y C905 ($32.456.700). Si son clientes nuevos, al registrarlos en el maestro ese monto pasa a su región.

2. Hay documentos repetidos. 30 facturas aparecen dos veces, idénticas, en el archivo de ventas; 23 de ellas son del semestre. Cada una se contó una sola vez. Contadas dos veces habrían inflado el semestre en $56.944.800 (2,4 %). Conviene revisar por qué la exportación las duplica.

3. Dos clientes cambiaron de región el 30 de abril de 2026: C002 pasó de Bogotá D.C. a Antioquia y C037 de Risaralda a Bogotá D.C. El glosario manda todo su semestre a la región nueva, incluso lo vendido antes del cambio. Por eso $29.414.600 de C002 quedan en Antioquia y $24.806.000 de C037 en Bogotá D.C. Si se usara la región que tenían en la fecha de cada venta, Risaralda subiría a $137.798.600, Antioquia bajaría a $1.018.473.100 y Bogotá D.C. quedaría en $505.349.400.

4. Correcciones hechas a los datos:
- 420 fechas venían como DD/MM/AAAA y el resto como AAAA-MM-DD. Se leyeron como día/mes: 255 de ellas tienen un día mayor que 12 y ninguna tiene un mes mayor que 12.
- 40 códigos de cliente traían espacios o minúsculas (por ejemplo «c055») y se corrigieron.
- En el maestro, nueve formas de escribir las regiones se llevaron a las cinco oficiales («CALDAS », «BOGOTA DC», «risaralda»…). Dos son abreviaturas que interpreté y conviene confirmar en el maestro: «Valle» como Valle del Cauca (cliente C027, $45.550.800) y «Bogotá» como Bogotá D.C. (cliente C036, $36.413.700).

5. El IVA quedó fuera: son $380.592.534 netos en el semestre. Un reporte que use el total con IVA, o que no reste las notas crédito, no va a cuadrar con este. Los archivos también traen diciembre de 2025 y julio de 2026, que no se contaron.

El script está en evidencia/sintetico/un_disparo/base_2/analisis.py. analizar(datos) devuelve las filas y diagnosticar(datos) devuelve las cifras de arriba. Si recibe algo que no puede resolver solo, se detiene con un error en lugar de adivinar: una región o una fecha que no reconoce, un documento repetido con datos distintos, un subtotal negativo o un cliente con dos registros de la misma fecha y regiones distintas.

## Generador 3

Las cifras están en pesos y siguen el glosario. Son ventas netas sin IVA: el subtotal de las facturas (FV) menos el de las notas crédito (NC). Cada documento cuenta en su fecha, entre el 1-ene y el 30-jun-2026, y va a la región vigente del cliente. Total del semestre: $2.386.197.500 (FV $2.444.548.000 menos NC $58.350.500). Esto le diría a quien lo pidió:

1. «Sin región» suma $42.052.800 (1,8 % del total). Son 17 facturas: 5 sin código de cliente ($9.596.100) y 12 con los códigos C901, C902, C904 y C905, que no están en el maestro de clientes ($32.456.700). Si son clientes reales, al darlos de alta en el maestro ese valor pasa a su región.

2. Dos clientes cambiaron de región en pleno semestre, el 30-abr-2026: C002 pasó de Bogotá D.C. a Antioquia y C037 de Risaralda a Bogotá D.C. Por la regla del glosario, todas sus ventas van a la región nueva, también las anteriores al cambio: $29.414.600 de C002 y $24.806.000 de C037. Con la región que tenían el día de cada venta, Antioquia bajaría $29.414.600, Bogotá D.C. subiría $4.608.600 y Risaralda subiría $24.806.000, hasta $137.798.600. Un informe hecho antes del 30-abr no va a coincidir en esas tres regiones.

3. 30 facturas venían dos veces, como copias idénticas, y 23 de ellas caen en el semestre. Se contaron una sola vez; contarlas dos veces habría inflado el total en $56.944.800.

4. Se limpiaron los datos sin cambiar las reglas:
- Las fechas vienen en dos formatos, AAAA-MM-DD y DD/MM/AAAA. El orden día/mes está confirmado: 258 fechas tienen el primer número mayor que 12 y ninguna tiene así el segundo.
- 33 documentos del semestre traían el código del cliente con espacios o en minúscula (por ejemplo «c055»).
- El maestro escribe las 5 regiones de 14 formas distintas («CALDAS », «BOGOTA DC», «risaralda»), y todas se llevaron a los nombres oficiales. Solo dos pedían interpretación: «Valle» (C027) se tomó como Valle del Cauca y «Bogotá» (C036) como Bogotá D.C.
Conviene corregir el maestro en el origen.

5. El archivo también trae 203 documentos de diciembre de 2025 y 171 de julio de 2026, que quedaron fuera. Si alguien compara con la columna «total», que incluye el IVA, el semestre le dará $380.592.534 más.

Verificación: un cálculo independiente, hecho sin pandas y con otro método para limpiar las regiones, da las mismas 6 cifras. Las 6 filas suman exactamente el total neto. El cálculo está en evidencia/sintetico/un_disparo/base_3/analisis.py; si encuentra un dato que no se puede leer con seguridad, se detiene con un error en vez de adivinar.

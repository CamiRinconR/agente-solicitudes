# SECOP II · advertencias de los tres generadores de un solo disparo

Lo que cada generador de un solo disparo le dijo a quien pidió el análisis, tal cual.

## Generador 1

Total: 52 entidades, 49.616 contratos y $17.247.887.955.037,58, unos 17,25 billones de pesos. Revisé el resultado con un segundo cálculo, hecho por otro camino, y coincide en todas las filas.

Cómo conté: entran los contratos firmados entre el 1 de enero y el 31 de diciembre de 2025, según fecha_de_firma. Tomé la fecha tal como viene en SECOP II, sin convertir la zona horaria. Así entran los 18 contratos firmados el 1 de enero y los 5 del 31 de diciembre. El valor es valor_del_contrato, que ya incluye las adiciones; no usé el valor facturado ni el pagado. Cuentan contratos en cualquier estado. Cada id_contrato cuenta una sola vez, y el archivo no trae repetidos. Los 542 contratos de valor cero suman en el número de contratos y no en el valor.

1. Hay una fila por NIT. Tres NIT tienen varias cuentas en SECOP II, y su fila es la suma de todas:
   - 890905211 (Distrito de Medellín): Alcaldía, 1.457 contratos por $7.655.008.958.131,82; Personería Distrital, 438 por $20.404.222.071; Concejo, 238 por $12.249.370.898.
   - 890900286: Gobernación de Antioquia, 1.352 por $4.889.582.139.982,26; Asamblea Departamental, 149 por $4.795.940.859.
   - 899999034 (SENA Regional Antioquia): Grupo de Apoyo Administrativo Mixto, 1.558 por $95.429.020.613,51; Grupo Administrativo Intercentros Medellín, 921 por $42.570.568.872,91. La fila lleva el nombre del primer grupo.
   Si el Concejo, la Personería y la Asamblea deben ir como entidades aparte, estas son sus cifras.

2. Dejé por fuera a la Universidad Pontificia Bolivariana (NIT 8909029226). Es una universidad privada, aunque publica en SECOP II por régimen especial. En 2025 tiene 46 contratos por $361.452.581,11. Si se incluye, el total sube a 49.662 contratos y $17.248.249.407.618,69.

3. Los nombres van como figuran en SECOP II, con sus marcas («//», «*», «COMPRADOR»). La Pascual Bravo y la IU Digital tienen cada una dos nombres en la misma cuenta. Sumé los contratos de los dos nombres y dejé el más frecuente.

4. Tres NIT vienen con 10 dígitos: AMUNORTE (8110303954), Politécnico JIC (8909801366) y Pascual Bravo (8909801583). Los demás tienen 9. Los dejé como figuran. Para cruzarlos con otra fuente hay que unificar el formato. En el NIT de la Pascual Bravo, el último dígito no es un dígito de verificación válido.

5. El valor contratado no es gasto. Tres contratos del Distrito son operaciones de crédito público, es decir, deuda. Suman exactamente $1.000.000.000.000: el 13 % del total del Distrito y el 5,8 % del total general. Además, MASA tiene una venta de un inmueble por $245.000.000, de un total de $256.500.000. Los dejé porque el glosario cuenta todo contrato firmado; si solo interesan las compras, hay que restarlos. El valor es el que figuraba el día de la descarga, el 6-nov-2026, y puede cambiar con modificaciones posteriores.

6. El Distrito y el Departamento suman el 72,9 % del total.

7. La sede sale del campo ciudad de SECOP II. Dos cuentas de la Dirección Territorial Pacífico de Parques Nacionales figuran en Medellín: la 805003737 y la subcuenta FONAM DTPA, 901037393. Esa dirección suele tener su sede en Cali, así que conviene confirmarlo. Entre las dos son 364 contratos por $15.251.913.152,94.

8. El archivo solo incluye entidades con contratos entre julio de 2024 y junio de 2026. Tres de ellas no firmaron nada en 2025 y no aparecen: la I. E. Arzobispo Tulio Botero Salazar, la ESU y APEV.

Script: evidencia/secop/un_disparo/base_1/analisis.py (función analizar(datos)).

## Generador 2

Resultado: 53 entidades, 49.662 contratos firmados en 2025 y $17.248.249.407.618,69 en pesos corrientes. El valor es valor_del_contrato tal como figura hoy en SECOP II, con adiciones. Lo recalculé por otra vía (módulo csv sin pandas, sumas exactas con Decimal) y coincide en las 53 filas. También probé la función con un archivo de casos borde: límites del año, id repetido, NIT con dígito de verificación, estado no válido y otra ciudad. Script: evidencia/secop/un_disparo/base_2/analisis.py

1. Hay una fila por NIT. Tres NIT agrupan varias unidades compradoras de SECOP II, y la fila lleva el nombre de la que tiene más contratos:
- 890905211: el Distrito de Medellín ($7.655.008.958.131,82; 1.457 contratos), la Personería Distrital ($20.404.222.071; 438) y el Concejo ($12.249.370.898; 238).
- 890900286: el Departamento de Antioquia ($4.889.582.139.982,26; 1.352) y la Asamblea Departamental ($4.795.940.859; 149).
- 899999034: el SENA Regional Antioquia, con el Grupo de Apoyo Administrativo Mixto ($95.429.020.613,51; 1.558) y el Grupo Administrativo Intercentros Medellín ($42.570.568.872,91; 921).
Si los quieren por separado, se separan con codigo_entidad. Pascual Bravo (8909801583) e IU Digital (901168222) tienen dos nombres para la misma entidad (mismo código) y van sumadas.

2. La Universidad Pontificia Bolivariana (8909029226) es privada, pero SECOP II la registra como compradora en régimen especial: 46 contratos por $361.452.581,11. Va incluida porque el archivo define el universo. Si el informe es estrictamente de entidades públicas, hay que restarla.

3. El valor del Distrito incluye 3 operaciones de crédito público (empréstitos) por $1.000.000.000.000. Sin ellas queda en $6.687.662.551.100,82. El Departamento tiene 6 por $192.780.000. Son contratos según el glosario, pero son deuda, no compras.

4. El Distrito y el Departamento concentran el 72,95 % del valor; las 5 primeras entidades, el 88,33 %.

5. Fechas: van incluidos 5 contratos firmados el 31-dic-2025 después de las 00:00 ($882.430.259). Un filtro «fecha <= 2025-12-31» los dejaría por fuera. No hay firmas entre las 00:00 y las 05:00 del 1-ene de 2025 ni de 2026, así que un posible desfase UTC no mueve ningún contrato de año. El recorte (jul-2024 a jun-2026) cubre 2025 completo.

6. Posibles registros dobles: 5 pares con la misma entidad, referencia, proceso y valor, pero distinto id_contrato, suman $8.592.242.609 de más. Por ejemplo, el contrato 4600104860 del Distrito, por $7.060.000.000, figura como CO1.PCCNTR.7839740 y como CO1.PCCNTR.7840787. El glosario los cuenta por separado; conviene revisarlos en SECOP II.

7. Según el glosario, también van incluidos: 542 contratos de valor cero (cuentan en el número y suman cero), 66 por $1 (valor simbólico), 456 en «Aprobado» (455 sin fecha de inicio) por $86.443.119.365, y 19 firmados después de su propia fecha de fin, por $3.239.961.571 (registro tardío).

8. Los NIT van como figuran en SECOP II. La mayoría tiene 9 dígitos, sin dígito de verificación; el Politécnico (8909801366), AMUNORTE (8110303954) y la UPB (8909029226) lo traen pegado. El de Pascual Bravo (8909801583) tiene 10 dígitos y el último no es un dígito de verificación válido. Ningún NIT aparece en las dos formas, así que no hubo que unir nada, pero para cruzar con otras fuentes conviene normalizarlos.

9. Tres entidades del archivo no firmaron contratos en 2025 y no aparecen: IE Arzobispo Tulio Botero Salazar (811018664), Empresa para la Seguridad y Soluciones Urbanas (8909847618) y APEV (900266932).

10. La sede sale del campo ciudad de SECOP II, sin verificar en otra fuente. Algunas entidades registradas en Medellín pueden operar desde otra ciudad; por ejemplo, la Dirección Territorial Pacífico de Parques Nacionales suele tener sede en Cali.

## Generador 3

Resultado: 53 entidades, una fila por NIT. En 2025 se firmaron 49.662 contratos por $17.248.249.407.618,69 (pesos colombianos). Un segundo cálculo hecho por otra vía (lectura directa del CSV con Decimal, sin pandas) da exactamente lo mismo.

Reglas del glosario que apliqué:
- Año según fecha_de_firma, del 1 de enero al 31 de diciembre de 2025, con los dos días completos.
- Valor = valor_del_contrato actual, con adiciones; no se usan el valor facturado ni el pagado.
- Cuentan todos los estados. Los 7 del archivo están en el glosario, aunque «terminado» y «cedido» vienen en minúscula.
- Cada id_contrato cuenta una vez; en el archivo no hay ninguno repetido.
- Los 542 contratos de valor cero cuentan en el número y suman cero.

Lo que conviene saber antes de usar estas cifras:

1. Tres NIT agrupan varias entidades de SECOP II en una sola fila:
- 890905211: Distrito de Medellín ($7.655.009 millones; 1.457 contratos), Personería Distrital ($20.404 millones; 438) y Concejo de Medellín ($12.249 millones; 238).
- 890900286: Departamento de Antioquia ($4.889.582 millones; 1.352) y Asamblea Departamental ($4.796 millones; 149).
- 899999034: dos grupos del SENA Regional Antioquia, Apoyo Administrativo Mixto ($95.429 millones; 1.558) e Intercentros Medellín ($42.571 millones; 921).
Para ver al Concejo, la Personería y la Asamblea por separado hay que agrupar por codigo_entidad: salen 57 unidades en vez de 53 NIT.

2. El valor del Distrito incluye 3 operaciones de crédito público por $1.000.000 millones (un billón, el 13 % de su fila). Son préstamos, no compras de bienes o servicios. El Departamento tiene otras 6 por $192,8 millones.

3. Posibles registros dobles: hay 42 grupos (85 contratos) con la misma unidad, la misma referencia y el mismo valor pero distinto id_contrato, casi todos firmados el mismo día. Por el glosario cuentan como contratos distintos. Si fueran duplicados, sobrarían 43 contratos y $10.079,6 millones (0,06 % del total), sobre todo en el Distrito (5 contratos; $8.936,9 millones) y en el ITM (32; $750,4 millones). Conviene revisarlos en SECOP II.

4. La Universidad Pontificia Bolivariana es privada. Aparece porque SECOP II la registra como entidad compradora: 46 contratos de régimen especial por $361,45 millones. Si se quieren solo entidades de derecho público, hay que restarla.

5. Nombres:
- Les quité las marcas de la plataforma («//», «*», «COMPRADOR») y reparé un carácter mal codificado en el nombre de la Rama Judicial.
- Pascual Bravo e IU Digital tienen dos nombres cada una en SECOP II. Las uní por NIT y dejé el nombre completo.
- CGA, MCM, MESAN e ISVIMED figuran en SECOP II solo con la sigla, y así las dejé.

6. Los NIT van tal como figuran en SECOP II. Cuatro tienen 10 dígitos:
- En 8110303954 (AMUNORTE), 8909029226 (UPB) y 8909801366 (Politécnico Jaime Isaza Cadavid), el último dígito es el de verificación.
- En 8909801583 (Pascual Bravo), el último dígito no coincide con el que da la fórmula de la DIAN. Conviene confirmarlo antes de cruzar con otras fuentes.
Además, ICBF, SENA, ESAP, Policía, Contraloría General, Ministerio del Trabajo, INPEC, DANE y Parques Nacionales están como seccionales: el valor es solo lo que contrató la unidad con sede en Medellín, no la entidad nacional completa.

7. Fechas: entran 5 contratos firmados el 31 de diciembre de 2025 con hora, que un filtro de texto «<= '2025-12-31'» dejaría fuera. No hay firmas entre las 00:00 y las 05:00 del 1 de enero de 2025 ni del 1 de enero de 2026, así que el resultado no cambia aunque las horas vinieran en UTC y no en hora de Colombia.

8. La sede sale del campo ciudad de SECOP II, que es como viene recortado el archivo. Dos unidades de la Dirección Territorial Pacífico de Parques Nacionales figuran en Medellín: la Dirección (805003737) y la subcuenta FONAM DTPA (901037393). Si importa la sede física, conviene confirmarla.

9. Tres entidades del archivo no firmaron contratos en 2025 y no aparecen: IE Arzobispo Tulio Botero Salazar, Empresa para la Seguridad y Soluciones Urbanas y APEV.

10. Los valores son los que tenía SECOP II el 6 de noviembre de 2026, fecha de la descarga; pueden cambiar con nuevas adiciones.

Script: evidencia/secop/un_disparo/base_3/analisis.py. analizar(datos) devuelve las filas y diagnostico(datos), las cifras de control que se usaron para estas advertencias.

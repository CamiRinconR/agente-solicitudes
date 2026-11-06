# Glosario de ventas

Lo escribe el negocio una sola vez y sirve para todas las peticiones sobre ventas.

- **Ventas**: siempre netas y sin IVA. Es la suma del `subtotal` de las facturas de venta (`FV`) menos la suma del `subtotal` de las notas crédito (`NC`, devoluciones). El IVA nunca cuenta como venta.
- **Fecha**: cada documento cuenta en su `fecha`. El primer semestre va del 1 de enero al 30 de junio, ambos incluidos.
- **Documento**: `numero_documento` identifica un documento; cada documento cuenta una sola vez.
- **Cliente**: el código tiene la forma `C` seguida de tres dígitos (por ejemplo, `C017`).
- **Región de una venta**: la región vigente del cliente, es decir, la de su registro más reciente en el maestro de clientes (`fecha_actualizacion`), aunque la venta sea anterior al cambio.
- **Regiones oficiales**: Antioquia, Bogotá D.C., Caldas, Risaralda y Valle del Cauca.
- **Ventas sin cliente identificado** (sin código, o con un código que no está en el maestro): no se descartan; se reportan como «Sin región».

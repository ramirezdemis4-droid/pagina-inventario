# Página sencilla de préstamos

La interfaz utiliza azul y amarillo, combinados con el escudo del Liceo Bicentenario Manuel Montt en `static/logo1.webp`.

La página tiene dos partes y utiliza JavaScript para el buscador y las mejoras visuales:

- **Alumno:** nombre, curso, equipo, cantidad y fecha de devolución; botón **Pedir préstamo**.
- **Encargado:** entrar con contraseña, aprobar o rechazar solicitudes y marcar **Devuelto**.

Ambas páginas muestran **Objetos del laboratorio**, con objeto, código,
disponibilidad y estado. También aparecen los objetos sin unidades disponibles.
La cantidad disponible descuenta las unidades dañadas y prestadas. Al aprobar
un préstamo baja la cantidad; al marcar **Devuelto** vuelve a subir. Recarga
la página para ver los cambios.

El cargador se llama **Cargador**. En Infraestructura aparece **Mesón grande**,
conservando sus cantidades anteriores (8 en una instalación nueva). Es para
uso dentro del laboratorio y no aparece en el formulario de préstamos.

El estado corresponde al registro del encargado: **Buen estado**, **Con daños**
o **Fuera de servicio**. Debajo se ve cuántas unidades están en buen estado y
cuántas dañadas. En el panel del encargado, abre **Revisar**, cambia **Unidades
dañadas** y presiona **Guardar**. Los alumnos solo pueden consultar el estado.
Al registrar daños se actualiza la disponibilidad y no se borran los préstamos.

Esta actualización agrega automáticamente los siguientes objetos al ejecutar
`python app.py`, incluso si ya tienes datos guardados:

| Objeto | Cantidad |
| --- | ---: |
| PC Acer | 30 |
| PC Asus | 2 |
| Monitor Samsung | 3 |
| Gabinete | 55 |
| Arduino | 39 |
| Caja de destornilladores | 8 |
| Mouse Genius | 11 |
| Mouse Tek | 2 |
| Mouse Tech | 10 |
| Mouse Invit | 1 |
| Mouse Lanix | 7 |

El notebook y el carrito dejan de aparecer. Los mouse por marca reemplazan la
fila genérica de mouse y los 40 kits de Arduino pasan a ser 39 Arduinos.
Los préstamos anteriores se conservan y pueden marcarse como devueltos.
Reiniciar no duplica objetos ni vuelve a restablecer cantidades. La lista muestra
la cantidad disponible después de descontar daños y préstamos activos.

La lista y el selector de equipo están agrupados en **Electrónicos, Periféricos,
Infraestructura y Herramientas**. Dentro de cada grupo se ordenan por nombre.
Los códigos y sus categorías se definen en `app.py`, en `CATALOGOS`.

El panel **Atajos**, a la izquierda en computador, permite saltar directamente
a Electrónicos, Periféricos, Infraestructura y Herramientas. Permanece visible
al bajar por la página. En celular queda fijo en la parte superior de la pantalla,
también al bajar hasta el final. Se reserva su altura para no tapar el encabezado;
los saltos a las categorías dejan sus títulos debajo de los atajos. Funciona en
las páginas de alumno y encargado.

El código de la aplicación está completo en `app.py`. `db.py` contiene la
conexión, las tablas y la carga inicial del inventario.

## Diseño para teléfono y computador

- En pantallas de hasta 700 px, el catálogo, las solicitudes y los préstamos se
  muestran como tarjetas con sus etiquetas, sin apretar los textos en columnas.
- En pantallas más anchas, se muestran tablas; por encima de 850 px los atajos
  están en un panel lateral. En teléfono y tablet quedan fijos arriba.
- El buscador y los filtros se apilan en pantallas pequeñas. Los campos usan
  texto de 16 px y los botones tienen al menos 44 px de alto para facilitar el uso táctil.
- Los nombres, las fotos, el formulario del alumno y el acceso del encargado
  se ajustan al ancho disponible. No se necesita cambiar ninguna configuración
  para pasar de teléfono a computador.

## Fotos de los objetos

Las fotos recibidas están en `static/fotos`. En las páginas de alumno y encargado
cada objeto identificado muestra una miniatura. Haz clic para abrir la foto
ampliada en la misma página. Si tiene varias fotos, abre **Más fotos**.
Sin JavaScript se abre en otra pestaña. La asociación entre códigos y fotos está en
`FOTOS_OBJETOS`, dentro de `app.py`.

Audífonos, Mouse Genius y Mouse Invit muestran **Sin foto**, porque el ZIP no
incluye fotos que se puedan asociar con seguridad a esos objetos. Las imágenes
de otros objetos y la lista escrita también se conservan en `static/fotos`,
sin agregar objetos ni cambiar cantidades del inventario.

Los préstamos devueltos dejan de aparecer en el panel. Sus registros se conservan
 en la base de datos. Las solicitudes pendientes no reservan equipos; el stock
se comprueba y descuenta al aprobar. El buscador filtra por nombre, código o
categoría al escribir, ignora mayúsculas y tildes y permite filtrar por
disponibilidad. No hay exportaciones ni formularios para agregar o quitar objetos.

## Actualizar sin perder tus datos

1. Detén el servidor con **Ctrl+C**.
2. Extrae el ZIP y copia los archivos de `pagina-inventario-main` a tu carpeta actual, reemplazando el código, incluido `app.py`, `templates` y `static`.
3. **Conserva tu carpeta `instance` y tu archivo `.env`.** El ZIP no los incluye.
4. En la terminal de VS Code ejecuta:

```powershell
python app.py
```

5. Abre **http://127.0.0.1:5000** y recarga con **Ctrl+F5**. En celular, recarga la página en el navegador.

Tu usuario y contraseña del encargado siguen funcionando y no se borran
los préstamos anteriores.

## Instalar por primera vez

Abre `pagina-inventario-main` en VS Code. En **Terminal → Nueva terminal**, ejecuta:

```powershell
python -m pip install -r requirements.txt
python app.py
```

La primera vez, crea el usuario y contraseña del encargado en la terminal. La
contraseña debe tener al menos 8 caracteres y no aparece mientras la escribes.
Deja la terminal abierta mientras uses la página.

Si VS Code muestra advertencias de librerías, selecciona el mismo Python con el
que instalaste las dependencias: **Ctrl+Shift+P → Python: Select Interpreter**.

## Usar la página

1. El alumno abre la página y presiona **Pedir préstamo** después de completar el formulario.
2. El encargado presiona **Entrar como encargado** e ingresa sus credenciales.
3. Presiona **Aprobar** para registrar la entrega del equipo, o **Rechazar**.
4. Cuando regresa el equipo, presiona **Devuelto**. El préstamo desaparece de la lista y vuelve la disponibilidad.
5. **Salir** vuelve a la página del alumno.

## Base de datos

Por defecto usa SQLite y guarda los datos en `instance/inventario.db`.
Si ya configuraste MySQL, conserva tu `.env` y sigue usando la misma base.
Para una instalación nueva en MySQL, ejecuta `sql/01_base_mysql.sql` en DBeaver,
copia `.env.example` como `.env` y completa host, puerto, usuario, contraseña y
base. Cambia `DB_ENGINE=mysql`. Cambiar de motor no transfiere los datos.

Para cambiar la contraseña o crear otro encargado:

```powershell
python app.py --crear-usuario
```

Para comprobar el servidor:

```powershell
python -m unittest discover -s tests -v
```

Las pruebas automáticas del servidor usan SQLite. MySQL requiere comprobar tu conexión
con tus credenciales. El servidor funciona localmente en `127.0.0.1`.


## Mejoras visuales con JavaScript

Se agregó `static/app.js`: búsqueda instantánea de objetos/códigos, filtro por disponibilidad, contador de resultados, ampliación de fotos sin abrir otra pestaña y botón para volver arriba. No requiere instalar librerías nuevas ni cambia las operaciones de préstamo o MySQL.

El buscador no funcionaba porque `app.py` bloqueaba todos los scripts con
`script-src 'none'`. Ahora permite los archivos JavaScript del propio sitio
con `script-src 'self'`. Es necesario reiniciar Flask después de actualizar
`app.py`; reemplazar solamente los archivos de `static` no corrige ese bloqueo.

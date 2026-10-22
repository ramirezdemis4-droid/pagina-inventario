# Inventario del laboratorio

Página sencilla de préstamos del Liceo Bicentenario Manuel Montt, hecha con
Python, Flask, HTML y CSS, sin JavaScript.

Los alumnos consultan objetos por categoría, ven sus fotos, disponibilidad y
estado, y envían solicitudes de préstamo. El encargado inicia sesión para
aprobar o rechazar solicitudes, registrar devoluciones y actualizar las unidades
dañadas.

## Ejecutar

Abre esta carpeta en VS Code y ejecuta en la terminal:

```powershell
python -m pip install -r requirements.txt
python app.py
```

En el primer inicio, crea el usuario y la contraseña del encargado en la terminal.
Después abre http://127.0.0.1:5000. Deja la terminal abierta mientras usas la página.

Por defecto utiliza SQLite. Para usar MySQL, consulta [LEEME.md](LEEME.md).

## Archivos

- `app.py`: código completo de la aplicación.
- `db.py`: base de datos y actualización del inventario.
- `templates/`: páginas HTML.
- `static/styles.css`: diseño azul y amarillo.
- `static/logo1.webp`: logo del liceo.
- `static/fotos/`: fotos originales de los objetos.
- `sql/`: preparación de MySQL.
- `tests/`: pruebas de permisos, préstamos, inventario y estado.

`.env` y `instance/` quedan fuera del repositorio. Guarda allí la configuración,
la base de datos y la clave local de sesión.

## Comprobar

```powershell
python -m unittest discover -s tests -v
```

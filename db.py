"""Conexiones y consultas parametrizadas para SQLite y MySQL."""
import sqlite3
from flask import current_app, g

NEW_EQUIPMENT = [
    ('TE001', 'Teclado', 30, 1),
    ('AU001', 'Audífonos', 15, 1),
    ('PR001', 'Proyector', 1, 1),
    ('SI001', 'Silla', 32, 1),
    ('AR001', 'Arduino', 39, 1),
    ('PC001', 'PC Acer', 30, 1),
    ('PC002', 'PC Asus', 2, 1),
    ('MN001', 'Monitor Samsung', 3, 1),
    ('GB001', 'Gabinete', 55, 1),
    ('HD001', 'Caja de destornilladores', 8, 1),
    ('MG001', 'Mouse Genius', 11, 1),
    ('MT001', 'Mouse Tek', 2, 1),
    ('MC001', 'Mouse Tech', 10, 1),
    ('MI001', 'Mouse Invit', 1, 1),
    ('ML001', 'Mouse Lanix', 7, 1),
]


class Database:
    def __init__(self):
        self.mysql = current_app.config['DB_ENGINE'] == 'mysql'
        if self.mysql:
            import pymysql
            self.connection = pymysql.connect(
                host=current_app.config['MYSQL_HOST'], port=current_app.config['MYSQL_PORT'],
                user=current_app.config['MYSQL_USER'], password=current_app.config['MYSQL_PASSWORD'],
                database=current_app.config['MYSQL_DATABASE'], charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor, autocommit=False,
                connect_timeout=5,
            )
        else:
            self.connection = sqlite3.connect(current_app.config['SQLITE_PATH'], timeout=10)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute('PRAGMA foreign_keys = ON')

    def execute(self, sql, args=()):
        cursor = self.connection.cursor()
        cursor.execute(sql.replace('?', '%s') if self.mysql else sql, args)
        return cursor

    def one(self, sql, args=()):
        row = self.execute(sql, args).fetchone()
        return dict(row) if row else None

    def all(self, sql, args=()):
        return [dict(row) for row in self.execute(sql, args).fetchall()]

    def begin(self):
        if self.mysql:
            self.connection.begin()
        else:
            self.connection.execute('BEGIN IMMEDIATE')

    def lock(self, sql, args=()):
        return self.one(sql + (' FOR UPDATE' if self.mysql else ''), args)

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()


def get_db():
    if 'db' not in g:
        g.db = Database()
    return g.db


def close_db(_error=None):
    db = g.pop('db', None)
    if db:
        db.connection.close()


def init_db():
    db = get_db()
    identity = 'INTEGER PRIMARY KEY AUTO_INCREMENT' if db.mysql else 'INTEGER PRIMARY KEY AUTOINCREMENT'
    suffix = ' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci' if db.mysql else ''
    definitions = [
        '''CREATE TABLE IF NOT EXISTS lab_actualizaciones (
            nombre VARCHAR(60) PRIMARY KEY)''',
        f'''CREATE TABLE IF NOT EXISTS lab_usuarios (
            id {identity}, usuario VARCHAR(60) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL)''',
        f'''CREATE TABLE IF NOT EXISTS lab_equipos (
            id {identity}, codigo VARCHAR(30) NOT NULL UNIQUE,
            articulo VARCHAR(100) NOT NULL, cantidad INTEGER NOT NULL,
            danados INTEGER NOT NULL DEFAULT 0, prestable INTEGER NOT NULL DEFAULT 1,
            activo INTEGER NOT NULL DEFAULT 1,
            CHECK (cantidad >= 1), CHECK (danados >= 0 AND danados <= cantidad))''',
        f'''CREATE TABLE IF NOT EXISTS lab_prestamos (
            id {identity}, equipo_id INTEGER NOT NULL, usuario_id INTEGER NOT NULL,
            estudiante VARCHAR(100) NOT NULL, curso VARCHAR(60) NOT NULL,
            cantidad INTEGER NOT NULL, fecha_prestamo VARCHAR(19) NOT NULL,
            fecha_prevista VARCHAR(10) NOT NULL, fecha_devolucion VARCHAR(19),
            observaciones VARCHAR(500) NOT NULL DEFAULT '',
            FOREIGN KEY (equipo_id) REFERENCES lab_equipos(id),
            FOREIGN KEY (usuario_id) REFERENCES lab_usuarios(id), CHECK (cantidad >= 1))''',
        f'''CREATE TABLE IF NOT EXISTS lab_solicitudes (
            id {identity}, equipo_id INTEGER NOT NULL,
            estudiante VARCHAR(100) NOT NULL, curso VARCHAR(60) NOT NULL,
            cantidad INTEGER NOT NULL, fecha_solicitud VARCHAR(19) NOT NULL,
            fecha_prevista VARCHAR(10) NOT NULL,
            observaciones VARCHAR(500) NOT NULL DEFAULT '',
            estado VARCHAR(15) NOT NULL DEFAULT 'Pendiente',
            prestamo_id INTEGER,
            FOREIGN KEY (equipo_id) REFERENCES lab_equipos(id),
            FOREIGN KEY (prestamo_id) REFERENCES lab_prestamos(id),
            CHECK (cantidad >= 1), CHECK (estado IN ('Pendiente', 'Aprobada', 'Rechazada')))''',
    ]
    for ddl in definitions:
        db.execute(ddl + suffix)
    # Los datos iniciales se agregan solamente a un inventario vacío.
    if not db.one('SELECT id FROM lab_equipos LIMIT 1'):
        for row in [('NB001', 'Notebook', 30, 1), ('CG001', 'Cargador', 30, 1),
                    ('CT001', 'Carrito de Transporte', 1, 1), ('SV001', 'Servidor', 1, 0),
                    ('MS001', 'Mesón grande', 8, 0)]:
            db.execute('INSERT INTO lab_equipos (codigo, articulo, cantidad, prestable) VALUES (?, ?, ?, ?)', row)
    # Agrega los nuevos objetos también a bases existentes, sin duplicarlos
    # ni restablecer cantidades, daños o préstamos en los siguientes inicios.
    for row in NEW_EQUIPMENT:
        if not db.one('SELECT id FROM lab_equipos WHERE codigo=?', (row[0],)):
            db.execute('INSERT INTO lab_equipos (codigo, articulo, cantidad, prestable) VALUES (?, ?, ?, ?)', row)
    # Aplica el cambio de catálogo una sola vez a bases nuevas o existentes.
    # Los objetos retirados se ocultan, pero sus préstamos se conservan.
    version = 'catalogo_laboratorio_v2'
    if not db.one('SELECT nombre FROM lab_actualizaciones WHERE nombre=?', (version,)):
        db.execute("UPDATE lab_equipos SET activo=0 WHERE codigo IN ('NB001', 'CT001', 'MO001')")
        db.execute("""UPDATE lab_equipos SET articulo='Arduino', cantidad=39,
            danados=CASE WHEN danados>39 THEN 39 ELSE danados END WHERE codigo='AR001'""")
        db.execute('INSERT INTO lab_actualizaciones (nombre) VALUES (?)', (version,))
    version = 'catalogo_nombres_estado_v3'
    if not db.one('SELECT nombre FROM lab_actualizaciones WHERE nombre=?', (version,)):
        db.execute("UPDATE lab_equipos SET articulo='Cargador' WHERE codigo='CG001'")
        db.execute("UPDATE lab_equipos SET articulo='Mesón grande', activo=1 WHERE codigo='MS001'")
        db.execute('INSERT INTO lab_actualizaciones (nombre) VALUES (?)', (version,))
    db.commit()

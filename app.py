"""Inventario escolar: acceso del encargado, préstamos y devoluciones."""
import getpass
import logging
import os
import re
import secrets
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, flash, render_template, request, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import HTTPException
from db import get_db, close_db, init_db

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')

CATALOGOS = {
    'Electrónicos': ('PC001', 'PC002', 'GB001', 'CG001', 'PR001', 'SV001'),
    'Periféricos': ('MN001', 'MG001', 'MT001', 'MC001', 'MI001', 'ML001', 'TE001', 'AU001'),
    'Infraestructura': ('SI001', 'MS001'),
    'Herramientas': ('AR001', 'HD001'),
}

# Fotos recibidas del laboratorio, asociadas a los códigos del inventario.
FOTOS_OBJETOS = {
    'PC001': ['monitor_acer.jpg'],
    'PC002': ['monitor_azus.jpg'],
    'GB001': ['gabinete_lanix.jpg'],
    'CG001': ['Cargador_Computador.jpg', 'Cargador_asus.jpg'],
    'PR001': ['proyector_casio.jpg'],
    'MN001': ['monitor_samsung.jpg', 'computador_samsung.jpg',
              'computador_samsung(1).jpg', 'computador_samsung(2).jpg'],
    'MT001': ['mouse_utek.jpg'],
    'MC001': ['Mouse_XTECH.jpg'],
    'ML001': ['mouse.jpg'],
    'TE001': ['teclado.jpg', 'teclado(1).jpg', 'teclado_genius.jpg', 'teclado_lanix.jpg'],
    'SI001': ['Sillas_azules.jpg', 'Sillas_negras.jpg', 'Sillas_rojas.jpg', 'Sillas_Madera.jpg'],
    'MS001': ['Mesa_Grande.jpg'],
    'AR001': ['Arduino_Caja.jpg'],
    'HD001': ['kit_destornilladores.jpg'],
    'SV001': ['servidor.jpg'],
}


class ValidationError(Exception):
    pass


def today():
    return datetime.now(ZoneInfo('America/Santiago')).date()


def now():
    return datetime.now(ZoneInfo('America/Santiago')).strftime('%Y-%m-%d %H:%M:%S')


def text_field(data, key, label, maximum):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise ValidationError(f'{label}: ingresa entre 1 y {maximum} caracteres.')
    return value.strip()


def integer(data, key, label, minimum=1):
    value = data.get(key)
    if isinstance(value, bool) or not re.fullmatch(r'\d+', str(value)):
        raise ValidationError(f'{label}: ingresa un número entero válido.')
    value = int(value)
    if value < minimum or value > 100000:
        raise ValidationError(f'{label}: debe estar entre {minimum} y 100000.')
    return value


def borrowed(db, equipment_id):
    return int(db.one('SELECT COALESCE(SUM(cantidad), 0) AS n FROM lab_prestamos WHERE equipo_id=? AND fecha_devolucion IS NULL', (equipment_id,))['n'])


def create_app(config=None):
    app = Flask(__name__)
    app.jinja_env.globals['catalogos'] = CATALOGOS
    instance = ROOT / 'instance'
    instance.mkdir(exist_ok=True)
    key_file = instance / 'secret.key'
    if not key_file.exists():
        try:
            with key_file.open('x') as handle:
                handle.write(secrets.token_hex(32))
            key_file.chmod(0o600)
        except FileExistsError:
            pass
    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY') or key_file.read_text(),
        DB_ENGINE=os.getenv('DB_ENGINE', 'sqlite').lower(),
        SQLITE_PATH=str(instance / 'inventario.db'),
        MYSQL_HOST=os.getenv('MYSQL_HOST', '127.0.0.1'), MYSQL_PORT=int(os.getenv('MYSQL_PORT', '3306')),
        MYSQL_USER=os.getenv('MYSQL_USER', 'root'), MYSQL_PASSWORD=os.getenv('MYSQL_PASSWORD', ''),
        MYSQL_DATABASE=os.getenv('MYSQL_DATABASE', 'inventario_laboratorio'),
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8), MAX_CONTENT_LENGTH=16000,
    )
    if config:
        app.config.update(config)
    if app.config['DB_ENGINE'] not in ('sqlite', 'mysql'):
        raise ValueError('DB_ENGINE debe ser sqlite o mysql.')
    app.teardown_appcontext(close_db)
    attempts = {}

    @app.before_request
    def protect():
        session.setdefault('csrf', secrets.token_hex(32))
        if request.endpoint not in ('index', 'request_loan', 'login', 'static') and not session.get('user_id'):
            return redirect(url_for('login'))
        if request.method == 'POST' and not secrets.compare_digest(request.form.get('csrf', ''), session['csrf']):
            return render_template('error.html', message='La sesión cambió. Vuelve a la página e inténtalo de nuevo.'), 403

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'none'; style-src 'self'; img-src 'self'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'"
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(ValidationError)
    def invalid(error):
        get_db().rollback()
        flash(str(error), 'error')
        return redirect(url_for('index' if request.endpoint == 'request_loan' else 'manager'), code=303)

    @app.errorhandler(Exception)
    def failure(error):
        if isinstance(error, HTTPException):
            return error
        logging.exception('Error del servidor')
        return render_template('error.html', message='No se pudo completar la operación. Revisa la conexión con la base de datos y vuelve a intentarlo.'), 500

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        error = None
        if request.method == 'POST':
            if not secrets.compare_digest(request.form.get('csrf', ''), session['csrf']):
                return render_template('login.html', error='Recarga la página antes de ingresar.'), 403
            ip = request.remote_addr
            count, until = attempts.get(ip, (0, 0))
            if time.monotonic() < until:
                return render_template('login.html', error='Demasiados intentos. Espera un minuto.'), 429
            if until:
                count = 0
            user = get_db().one('SELECT * FROM lab_usuarios WHERE usuario=?', (request.form.get('usuario', '').strip(),))
            if user and check_password_hash(user['password_hash'], request.form.get('password', '')):
                attempts.pop(ip, None)
                session.clear()
                session.update(user_id=user['id'], usuario=user['usuario'], csrf=secrets.token_hex(32))
                session.permanent = True
                return redirect(url_for('manager'))
            count += 1
            attempts[ip] = (count, time.monotonic() + 60 if count >= 5 else 0)
            error = 'Usuario o contraseña incorrectos.'
        return render_template('login.html', error=error)

    @app.post('/logout')
    def logout():
        if not secrets.compare_digest(request.form.get('csrf', ''), session['csrf']):
            return 'Solicitud inválida.', 403
        session.clear()
        return redirect(url_for('index'))

    @app.get('/')
    def index():
        # La portada solo consulta equipos; no expone datos de otros alumnos.
        return render_template('alumno.html', equipos=equipment_data(), fecha=today().isoformat())

    @app.get('/encargado')
    def manager():
        db = get_db()
        requests = db.all("""SELECT s.*, e.codigo, e.articulo FROM lab_solicitudes s
            JOIN lab_equipos e ON e.id=s.equipo_id
            WHERE s.estado='Pendiente' ORDER BY s.id""")
        loans = db.all("""SELECT p.*, e.codigo, e.articulo FROM lab_prestamos p
            JOIN lab_equipos e ON e.id=p.equipo_id
            WHERE p.fecha_devolucion IS NULL ORDER BY p.id DESC""")
        return render_template('index.html', solicitudes=requests, prestamos=loans, equipos=equipment_data())

    def equipment_data():
        db = get_db()
        equipment = db.all('''SELECT e.*, COALESCE(p.prestados,0) AS prestados FROM lab_equipos e
            LEFT JOIN (SELECT equipo_id, SUM(cantidad) AS prestados FROM lab_prestamos
            WHERE fecha_devolucion IS NULL GROUP BY equipo_id) p ON p.equipo_id=e.id
            WHERE e.activo=1 ORDER BY e.id''')
        for row in equipment:
            row['fotos'] = FOTOS_OBJETOS.get(row['codigo'], [])
            row['buen_estado'] = row['cantidad'] - row['danados']
            row['disponibles'] = max(0, row['buen_estado'] - int(row['prestados']))
            row['categoria'] = 'Herramientas'
            for categoria, codigos in CATALOGOS.items():
                if row['codigo'] in codigos:
                    row['categoria'] = categoria
                    break
        return sorted(equipment, key=lambda row: row['articulo'].casefold())

    def loan_fields(payload):
        student = text_field(payload, 'estudiante', 'Nombre del estudiante', 100)
        course = text_field(payload, 'curso', 'Curso', 60)
        equipment_id = integer(payload, 'equipo_id', 'Equipo')
        quantity = integer(payload, 'cantidad', 'Cantidad')
        expected = text_field(payload, 'fecha_prevista', 'Fecha de devolución', 10)
        try:
            parsed_date = date.fromisoformat(expected)
            if parsed_date.isoformat() != expected or parsed_date < today():
                raise ValueError
        except ValueError:
            raise ValidationError('La devolución debe ser hoy o una fecha posterior válida.')
        observations = payload.get('observaciones', '')
        if not isinstance(observations, str) or len(observations) > 500:
            raise ValidationError('Las observaciones deben tener hasta 500 caracteres.')
        return student, course, equipment_id, quantity, expected, observations.strip()

    def check_stock(db, row, quantity):
        if not row or not row['activo'] or not row['prestable']:
            raise ValidationError('Selecciona un equipo habilitado para préstamos.')
        available = max(0, row['cantidad'] - row['danados'] - borrowed(db, row['id']))
        if quantity > available:
            raise ValidationError(f'Solo quedan {available} unidades disponibles.')

    @app.post('/equipos/<int:equipment_id>/estado')
    def update_condition(equipment_id):
        damaged = integer(request.form, 'danados', 'Unidades dañadas', minimum=0)
        db = get_db()
        db.begin()
        equipment = db.lock('SELECT * FROM lab_equipos WHERE id=?', (equipment_id,))
        if not equipment or not equipment['activo']:
            raise ValidationError('El objeto no existe o está retirado del inventario.')
        if damaged > equipment['cantidad']:
            raise ValidationError('Las unidades dañadas no pueden superar la cantidad total del objeto.')
        db.execute('UPDATE lab_equipos SET danados=? WHERE id=?', (damaged, equipment_id))
        db.commit()
        flash('Estado actualizado. Las unidades dañadas no están disponibles para préstamo.', 'success')
        return redirect(url_for('manager'), code=303)

    @app.post('/solicitudes')
    def request_loan():
        student, course, equipment_id, quantity, expected, observations = loan_fields(request.form)
        db = get_db()
        db.begin()
        equipment = db.lock('SELECT * FROM lab_equipos WHERE id=?', (equipment_id,))
        check_stock(db, equipment, quantity)
        cursor = db.execute('''INSERT INTO lab_solicitudes
            (equipo_id, estudiante, curso, cantidad, fecha_solicitud, fecha_prevista, observaciones)
            VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (equipment_id, student, course, quantity, now(), expected, observations))
        db.commit()
        flash(f'Solicitud #{cursor.lastrowid} enviada. El encargado debe aprobarla antes de entregar el equipo.', 'success')
        return redirect(url_for('index'), code=303)

    @app.post('/solicitudes/<int:request_id>/aprobar')
    def approve_request(request_id):
        db = get_db()
        initial = db.one('SELECT equipo_id FROM lab_solicitudes WHERE id=?', (request_id,))
        if not initial:
            raise ValidationError('La solicitud no existe.')
        # Se cierra la lectura previa para comprobar stock actualizado en MySQL.
        db.commit()
        db.begin()
        equipment = db.lock('SELECT * FROM lab_equipos WHERE id=?', (initial['equipo_id'],))
        item = db.lock('SELECT * FROM lab_solicitudes WHERE id=?', (request_id,))
        if item['estado'] != 'Pendiente':
            raise ValidationError('Esta solicitud ya fue revisada.')
        if item['fecha_prevista'] < today().isoformat():
            raise ValidationError('La fecha de devolución ya pasó. Rechaza esta solicitud y pide al alumno que envíe una con fecha actualizada.')
        check_stock(db, equipment, item['cantidad'])
        cursor = db.execute('''INSERT INTO lab_prestamos
            (equipo_id, usuario_id, estudiante, curso, cantidad, fecha_prestamo, fecha_prevista, observaciones)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (item['equipo_id'], session['user_id'], item['estudiante'], item['curso'],
             item['cantidad'], now(), item['fecha_prevista'], item['observaciones']))
        db.execute("UPDATE lab_solicitudes SET estado='Aprobada', prestamo_id=? WHERE id=?", (cursor.lastrowid, request_id))
        db.commit()
        flash('Solicitud aprobada y préstamo registrado.', 'success')
        return redirect(url_for('manager'), code=303)

    @app.post('/solicitudes/<int:request_id>/rechazar')
    def reject_request(request_id):
        db = get_db()
        db.begin()
        item = db.lock('SELECT * FROM lab_solicitudes WHERE id=?', (request_id,))
        if not item or item['estado'] != 'Pendiente':
            raise ValidationError('La solicitud no existe o ya fue revisada.')
        db.execute("UPDATE lab_solicitudes SET estado='Rechazada' WHERE id=?", (request_id,))
        db.commit()
        flash('Solicitud rechazada. No se modificó el inventario.', 'success')
        return redirect(url_for('manager'), code=303)

    @app.post('/prestamos/<int:loan_id>/devolver')
    def return_loan(loan_id):
        db = get_db()
        db.begin()
        row = db.one('SELECT equipo_id FROM lab_prestamos WHERE id=?', (loan_id,))
        if not row:
            raise ValidationError('El préstamo no existe.')
        db.lock('SELECT id FROM lab_equipos WHERE id=?', (row['equipo_id'],))
        row = db.lock('SELECT * FROM lab_prestamos WHERE id=?', (loan_id,))
        if row['fecha_devolucion']:
            raise ValidationError('Este préstamo ya fue devuelto.')
        db.execute('UPDATE lab_prestamos SET fecha_devolucion=? WHERE id=?', (now(), loan_id))
        db.commit()
        flash('Devolución registrada. Las unidades vuelven a estar disponibles.', 'success')
        return redirect(url_for('manager'), code=303)

    return app


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Inventario del laboratorio')
    parser.add_argument('--crear-usuario', action='store_true', help='Crear otro encargado o cambiar una contraseña')
    args = parser.parse_args()
    app = create_app()
    try:
        with app.app_context():
            init_db()
            if args.crear_usuario or not get_db().one('SELECT id FROM lab_usuarios LIMIT 1'):
                print('\nCrea el acceso del encargado. La contraseña no aparece mientras la escribes.')
                user = input('Usuario (ejemplo: encargado): ').strip()
                if not re.fullmatch(r'[A-Za-z0-9_.-]{3,60}', user):
                    raise ValueError('Usa entre 3 y 60 letras, números, puntos o guiones.')
                password = getpass.getpass('Contraseña (mínimo 8 caracteres): ')
                if len(password) < 8 or password != getpass.getpass('Repite la contraseña: '):
                    raise ValueError('Las contraseñas deben coincidir y tener al menos 8 caracteres.')
                db = get_db()
                existing = db.one('SELECT id FROM lab_usuarios WHERE usuario=?', (user,))
                if existing:
                    db.execute('UPDATE lab_usuarios SET password_hash=? WHERE id=?', (generate_password_hash(password), existing['id']))
                else:
                    db.execute('INSERT INTO lab_usuarios (usuario, password_hash) VALUES (?, ?)', (user, generate_password_hash(password)))
                db.commit()
                print('Acceso guardado.')
    except Exception as error:
        print(f'No se pudo iniciar: {error}\nRevisa .env y las instrucciones de LEEME.md.')
        raise SystemExit(1)
    if not args.crear_usuario:
        print('\nAbre http://127.0.0.1:5000 en tu navegador. Para detener: Ctrl+C.\n')
        app.run(host='127.0.0.1', port=5000, debug=False)

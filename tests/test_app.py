"""Pruebas del flujo sencillo y de los permisos del encargado."""
import sys
import re
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app, today
from db import init_db, get_db
from werkzeug.security import generate_password_hash


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.app = create_app({'TESTING':True, 'SECRET_KEY':'test-only', 'DB_ENGINE':'sqlite', 'SQLITE_PATH':str(Path(self.folder.name)/'db.sqlite')})
        with self.app.app_context():
            init_db()
            self.equipment_id = get_db().one("SELECT id FROM lab_equipos WHERE codigo='PC001'")['id']
            get_db().execute('INSERT INTO lab_usuarios (usuario,password_hash) VALUES (?,?)', ('encargado',generate_password_hash('password-test')))
            get_db().commit()
        self.student = self.client()
        self.manager = self.client(True)

    def tearDown(self):
        self.folder.cleanup()

    def client(self, manager=False):
        client = self.app.test_client()
        client.get('/')
        with client.session_transaction() as s:
            s['csrf']='test-token'
            if manager: s.update(user_id=1, usuario='encargado')
        return client

    def post(self, client, path, data=None):
        return client.post(path, data=dict(csrf='test-token', **(data or {})), follow_redirects=True)

    def payload(self, **changes):
        data=dict(estudiante='José Muñoz', curso='2° Medio B', equipo_id=self.equipment_id, cantidad=1, fecha_prevista=today().isoformat())
        data.update(changes)
        return data

    def rows(self, table):
        with self.app.app_context():
            return get_db().all(f'SELECT * FROM {table} ORDER BY id')

    def catalog(self, client, path):
        return re.search(r'<section id="objetos-disponibles">(.*?)</section>', client.get(path).text, re.S).group(1)

    def object_row(self, client, path, code):
        return re.search(rf'<tr\b[^>]*\bdata-codigo="{code}"[^>]*>.*?</tr>', self.catalog(client, path), re.S).group(0)

    def test_public_page_and_permissions(self):
        page=self.student.get('/').text
        self.assertIn('Pedir préstamo',page)
        self.assertIn('<script src="/static/app.js?v=3" defer></script>', page)
        policy = self.student.get('/').headers['Content-Security-Policy']
        self.assertIn("script-src 'self';", policy)
        self.assertNotIn("'unsafe-inline'", policy)
        self.assertNotIn("'unsafe-eval'", policy)
        self.assertNotIn('Solicitudes pendientes',page)
        self.assertEqual(self.student.get('/encargado').location,'/login')
        self.assertEqual(self.student.post('/solicitudes',data=self.payload()).status_code,403)
        for path in ['/solicitudes/1/aprobar','/solicitudes/1/rechazar','/prestamos/1/devolver',f'/equipos/{self.equipment_id}/estado']:
            self.assertEqual(self.student.post(path,data={'csrf':'test-token'}).location,'/login')
        self.student.get('/login')
        response=self.post(self.student,'/login',dict(usuario='encargado',password='password-test'))
        self.assertIn('Solicitudes pendientes',response.text)

    def test_request_approval_return_and_hidden_history(self):
        self.assertIn('Solicitud #1 enviada', self.post(self.student,'/solicitudes',self.payload(cantidad=2)).text)
        self.assertEqual(self.rows('lab_prestamos'),[])
        self.assertNotIn('José Muñoz',self.student.get('/').text)
        self.assertIn('José Muñoz',self.manager.get('/encargado').text)
        response=self.post(self.manager,'/solicitudes/1/aprobar')
        self.assertIn('Solicitud aprobada y préstamo registrado.',response.text)
        self.assertEqual(self.rows('lab_prestamos')[0]['cantidad'],2)
        self.assertIn('ya fue revisada',self.post(self.manager,'/solicitudes/1/aprobar').text)
        response=self.post(self.manager,'/prestamos/1/devolver')
        self.assertIn('No hay equipos prestados.',response.text)
        self.assertNotIn('José Muñoz',self.manager.get('/encargado').text)
        self.assertIsNotNone(self.rows('lab_prestamos')[0]['fecha_devolucion'])
        self.assertIn('ya fue devuelto',self.post(self.manager,'/prestamos/1/devolver').text)

    def test_rejection(self):
        self.post(self.student,'/solicitudes',self.payload())
        response=self.post(self.manager,'/solicitudes/1/rechazar')
        self.assertIn('No hay solicitudes pendientes.',response.text)
        self.assertEqual(self.rows('lab_solicitudes')[0]['estado'],'Rechazada')
        self.assertEqual(self.rows('lab_prestamos'),[])

    def test_available_objects_for_both_roles(self):
        def catalog(client, path):
            page = client.get(path).text
            return re.search(r'<section id="objetos-disponibles">(.*?)</section>', page, re.S).group(1)

        def check_quantity(quantity):
            for client, path in [(self.student, '/'), (self.manager, '/encargado')]:
                table = catalog(client, path)
                row = self.object_row(client, path, 'PC001')
                self.assertIn(f'data-disponibles="{quantity}"', row)
                self.assertIn('Con daños', row)
                self.assertNotIn('Servidor', table)
                self.assertNotIn('Mesón', table)
                self.assertNotIn('José Muñoz', table)

        with self.app.app_context():
            db = get_db()
            db.execute('UPDATE lab_equipos SET danados=2 WHERE id=?', (self.equipment_id,))
            db.execute('UPDATE lab_equipos SET activo=0 WHERE id<>?', (self.equipment_id,))
            db.commit()
        check_quantity(28)
        self.post(self.student, '/solicitudes', self.payload(cantidad=28))
        check_quantity(28)  # Las solicitudes pendientes no reservan objetos.
        self.post(self.manager, '/solicitudes/1/aprobar')
        for client, path in [(self.student, '/'), (self.manager, '/encargado')]:
            table = catalog(client, path)
            self.assertIn('No disponible', self.object_row(client, path, 'PC001'))
            self.assertIn('data-disponibles="0"', self.object_row(client, path, 'PC001'))
            self.assertNotIn('Cargador', table)
            self.assertNotIn('Carrito', table)
        self.post(self.manager, '/prestamos/1/devolver')
        check_quantity(28)

    def test_validation(self):
        for changes in [{'cantidad':31},{'cantidad':0},{'cantidad':'1.5'},{'estudiante':''},{'equipo_id':4},{'fecha_prevista':'2020-01-01'}]:
            self.post(self.student,'/solicitudes',self.payload(**changes))
            self.assertEqual(self.rows('lab_solicitudes'),[])

    def test_concurrent_approvals(self):
        for _ in range(2): self.post(self.student,'/solicitudes',self.payload(cantidad=20))
        def approve(request_id):
            return self.post(self.client(True),f'/solicitudes/{request_id}/aprobar').text
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(approve,[1,2]))
        self.assertEqual(sum('Solicitud aprobada y préstamo registrado.' in text for text in results),1)
        self.assertEqual(len(self.rows('lab_prestamos')),1)

    def test_existing_data_preserved(self):
        self.post(self.student,'/solicitudes',self.payload())
        self.post(self.manager,'/solicitudes/1/aprobar')
        equipment = self.rows('lab_equipos')
        with self.app.app_context(): init_db()
        self.assertEqual(len(self.rows('lab_prestamos')),1)
        self.assertEqual(self.rows('lab_equipos'), equipment)

    def test_new_objects_added_to_existing_inventory_once(self):
        expected = {'PC001': ('PC Acer', 30), 'PC002': ('PC Asus', 2),
                    'MN001': ('Monitor Samsung', 3), 'GB001': ('Gabinete', 55),
                    'AR001': ('Arduino', 39), 'HD001': ('Caja de destornilladores', 8),
                    'MG001': ('Mouse Genius', 11), 'MT001': ('Mouse Tek', 2),
                    'MC001': ('Mouse Tech', 10), 'MI001': ('Mouse Invit', 1),
                    'ML001': ('Mouse Lanix', 7)}
        # Simula el catálogo anterior, incluyendo un préstamo de notebook.
        with self.app.app_context():
            db = get_db()
            for code in expected:
                if code != 'AR001':
                    db.execute('DELETE FROM lab_equipos WHERE codigo=?', (code,))
            db.execute('DELETE FROM lab_actualizaciones')
            db.execute("UPDATE lab_equipos SET activo=1 WHERE codigo IN ('NB001','CT001')")
            db.execute("UPDATE lab_equipos SET articulo='Kit de Arduino', cantidad=40, danados=2 WHERE codigo='AR001'")
            db.execute("INSERT INTO lab_equipos (codigo,articulo,cantidad) VALUES ('MO001','Mouse',30)")
            db.execute("UPDATE lab_equipos SET cantidad=29 WHERE codigo='TE001'")
            notebook_id = db.one("SELECT id FROM lab_equipos WHERE codigo='NB001'")['id']
            db.commit()
        self.post(self.student, '/solicitudes', self.payload(equipo_id=notebook_id))
        self.post(self.manager, '/solicitudes/1/aprobar')
        with self.app.app_context():
            init_db()
            db = get_db()
            for code, (name, quantity) in expected.items():
                row = db.one('SELECT * FROM lab_equipos WHERE codigo=?', (code,))
                self.assertEqual((row['articulo'], row['cantidad'], row['prestable']), (name, quantity, 1))
            self.assertEqual(db.one("SELECT cantidad FROM lab_equipos WHERE codigo='TE001'")['cantidad'], 29)
            self.assertEqual(db.one("SELECT danados FROM lab_equipos WHERE codigo='AR001'")['danados'], 2)
            for code in ('NB001','CT001','MO001'):
                self.assertEqual(db.one('SELECT activo FROM lab_equipos WHERE codigo=?', (code,))['activo'], 0)
            db.execute("UPDATE lab_equipos SET cantidad=29, danados=1 WHERE codigo='PC001'")
            db.execute("UPDATE lab_equipos SET cantidad=38 WHERE codigo='AR001'")
            db.commit()
            init_db()
            acer = db.one("SELECT * FROM lab_equipos WHERE codigo='PC001'")
            self.assertEqual((acer['cantidad'], acer['danados']), (29, 1))
            self.assertEqual(db.one("SELECT cantidad FROM lab_equipos WHERE codigo='AR001'")['cantidad'], 38)
            arduino_id = db.one('SELECT id FROM lab_equipos WHERE codigo=?', ('AR001',))['id']
        self.assertEqual(self.rows('lab_prestamos')[0]['equipo_id'], notebook_id)
        codes = [row['codigo'] for row in self.rows('lab_equipos')]
        for code in expected:
            self.assertEqual(codes.count(code), 1)
        for client, path in [(self.student, '/'), (self.manager, '/encargado')]:
            page = client.get(path).text
            table = re.search(r'<section id="objetos-disponibles">(.*?)</section>', page, re.S).group(1)
            for code in ('NB001','CT001','MO001'):
                self.assertNotIn(f'data-codigo="{code}"', table)
            for code, (name, quantity) in expected.items():
                available = {'PC001':28, 'AR001':36}.get(code, quantity)
                row = self.object_row(client, path, code)
                self.assertIn(f'<td>{name}<small>{code}</small>', row)
                self.assertIn(f'data-disponibles="{available}"', row)
        self.assertIn('No hay equipos prestados.', self.post(self.manager, '/prestamos/1/devolver').text)
        self.post(self.student, '/solicitudes', self.payload(equipo_id=arduino_id, cantidad=1))
        self.assertEqual(self.rows('lab_solicitudes')[-1]['equipo_id'], arduino_id)

    def test_catalogs_for_students_and_managers(self):
        expected = {
            'Electrónicos': ['Cargador', 'Gabinete', 'PC Acer', 'PC Asus', 'Proyector'],
            'Periféricos': ['Audífonos', 'Monitor Samsung', 'Mouse Genius', 'Mouse Invit', 'Mouse Lanix', 'Mouse Tech', 'Mouse Tek', 'Teclado'],
            'Infraestructura': ['Mesón grande', 'Silla'],
            'Herramientas': ['Arduino', 'Caja de destornilladores'],
        }
        for client, path in [(self.student, '/'), (self.manager, '/encargado')]:
            page = client.get(path).text
            table = re.search(r'<section id="objetos-disponibles">(.*?)</section>', page, re.S).group(1)
            groups = re.findall(r'<tbody[^>]*>(.*?)</tbody>', table, re.S)
            self.assertEqual(len(groups), 4)
            for group, (category, names) in zip(groups, expected.items()):
                self.assertIn(f'scope="rowgroup">{category}</th>', group)
                self.assertEqual(re.findall(r'<td>(.*?)<small>[^<]+</small>', group), names)
        select = re.search(r'<select id="equipo".*?</select>', self.student.get('/').text, re.S).group(0)
        for category in expected:
            self.assertIn(f'<optgroup label="{category}">', select)

    def test_condition_changes_and_availability(self):
        endpoint = f'/equipos/{self.equipment_id}/estado'
        self.post(self.student, endpoint, {'danados':2})
        self.assertEqual(next(row for row in self.rows('lab_equipos') if row['id']==self.equipment_id)['danados'], 0)
        self.assertEqual(self.manager.post(endpoint, data={'danados':2}).status_code, 403)
        for invalid in ('31', '-1', '2.5', ''):
            response = self.post(self.manager, endpoint, {'danados':invalid})
            self.assertEqual(response.status_code, 200)
            self.assertIn('message error', response.text)
            self.assertEqual(next(row for row in self.rows('lab_equipos') if row['id']==self.equipment_id)['danados'], 0)
        self.post(self.manager, endpoint, {'danados':2})
        for client, path in [(self.student, '/'), (self.manager, '/encargado')]:
            row = self.object_row(client, path, 'PC001')
            self.assertIn('data-disponibles="28"', row)
            self.assertIn('En buen estado: 28', row)
            self.assertIn('Dañadas: 2', row)
            self.assertIn('Con daños', row)
        self.assertNotIn('class="condition-edit"', self.student.get('/').text)
        self.assertIn('Unidades dañadas', self.manager.get('/encargado').text)
        self.post(self.student, '/solicitudes', self.payload(cantidad=29))
        self.assertEqual(self.rows('lab_solicitudes'), [])
        self.post(self.student, '/solicitudes', self.payload(cantidad=28))
        self.post(self.manager, '/solicitudes/1/aprobar')
        self.post(self.manager, endpoint, {'danados':30})
        row = self.object_row(self.student, '/', 'PC001')
        self.assertIn('data-disponibles="0"', row)
        self.assertIn('Fuera de servicio', row)
        select = re.search(r'<select id="equipo".*?</select>', self.student.get('/').text, re.S).group(0)
        self.assertNotIn('PC Acer', select)
        self.post(self.manager, '/prestamos/1/devolver')
        self.post(self.manager, endpoint, {'danados':0})
        self.assertIn('Buen estado', self.object_row(self.student, '/', 'PC001'))
        with self.app.app_context(): init_db()
        self.assertIn('data-disponibles="30"', self.object_row(self.student, '/', 'PC001'))

    def test_names_update_preserves_quantities_and_fixed_infrastructure(self):
        with self.app.app_context():
            db = get_db()
            db.execute("DELETE FROM lab_actualizaciones WHERE nombre='catalogo_nombres_estado_v3'")
            db.execute("UPDATE lab_equipos SET articulo='Cargador de Notebook', cantidad=25, danados=2 WHERE codigo='CG001'")
            db.execute("UPDATE lab_equipos SET articulo='Mesón de Madera', cantidad=6, danados=1 WHERE codigo='MS001'")
            db.commit()
            init_db()
            meson_id = db.one("SELECT id FROM lab_equipos WHERE codigo='MS001'")['id']
            self.assertEqual(db.one("SELECT prestable FROM lab_equipos WHERE codigo='MS001'")['prestable'], 0)
        for client, path in [(self.student, '/'), (self.manager, '/encargado')]:
            row = self.object_row(client, path, 'CG001')
            self.assertIn('<td>Cargador<small>', row)
            self.assertIn('data-disponibles="23"', row)
            meson = self.object_row(client, path, 'MS001')
            self.assertIn('Mesón grande', meson)
            self.assertIn('Uso en laboratorio', meson)
            self.assertIn('En buen estado: 5', meson)
            self.assertIn('Dañadas: 1', meson)
        self.post(self.student, '/solicitudes', self.payload(equipo_id=meson_id))
        self.assertEqual(self.rows('lab_solicitudes'), [])


if __name__ == '__main__': unittest.main()

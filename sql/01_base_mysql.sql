-- Ejecutar en tu conexión MySQL de DBeaver. No borra bases ni tablas.
CREATE DATABASE IF NOT EXISTS inventario_laboratorio
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE inventario_laboratorio;

CREATE TABLE IF NOT EXISTS lab_actualizaciones (
  nombre VARCHAR(60) PRIMARY KEY
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lab_usuarios (
  id INTEGER PRIMARY KEY AUTO_INCREMENT,
  usuario VARCHAR(60) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lab_equipos (
  id INTEGER PRIMARY KEY AUTO_INCREMENT,
  codigo VARCHAR(30) NOT NULL UNIQUE,
  articulo VARCHAR(100) NOT NULL,
  cantidad INTEGER NOT NULL,
  danados INTEGER NOT NULL DEFAULT 0,
  prestable INTEGER NOT NULL DEFAULT 1,
  activo INTEGER NOT NULL DEFAULT 1,
  CHECK (cantidad >= 1), CHECK (danados >= 0 AND danados <= cantidad)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lab_prestamos (
  id INTEGER PRIMARY KEY AUTO_INCREMENT,
  equipo_id INTEGER NOT NULL,
  usuario_id INTEGER NOT NULL,
  estudiante VARCHAR(100) NOT NULL,
  curso VARCHAR(60) NOT NULL,
  cantidad INTEGER NOT NULL,
  fecha_prestamo VARCHAR(19) NOT NULL,
  fecha_prevista VARCHAR(10) NOT NULL,
  fecha_devolucion VARCHAR(19),
  observaciones VARCHAR(500) NOT NULL DEFAULT '',
  FOREIGN KEY (equipo_id) REFERENCES lab_equipos(id),
  FOREIGN KEY (usuario_id) REFERENCES lab_usuarios(id),
  CHECK (cantidad >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
-- El servidor crea el encargado y agrega los equipos iniciales al primer inicio.

-- Nueva tabla de solicitudes. Los préstamos existentes se conservan.
CREATE TABLE IF NOT EXISTS lab_solicitudes (
  id INTEGER PRIMARY KEY AUTO_INCREMENT,
  equipo_id INTEGER NOT NULL,
  estudiante VARCHAR(100) NOT NULL,
  curso VARCHAR(60) NOT NULL,
  cantidad INTEGER NOT NULL,
  fecha_solicitud VARCHAR(19) NOT NULL,
  fecha_prevista VARCHAR(10) NOT NULL,
  observaciones VARCHAR(500) NOT NULL DEFAULT '',
  estado VARCHAR(15) NOT NULL DEFAULT 'Pendiente',
  prestamo_id INTEGER,
  FOREIGN KEY (equipo_id) REFERENCES lab_equipos(id),
  FOREIGN KEY (prestamo_id) REFERENCES lab_prestamos(id),
  CHECK (cantidad >= 1),
  CHECK (estado IN ('Pendiente', 'Aprobada', 'Rechazada'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

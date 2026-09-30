CREATE TABLE IF NOT EXISTS categorias (
    categoria_id SERIAL PRIMARY KEY,
    nombre VARCHAR(80) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS productos (
    producto_id SERIAL PRIMARY KEY,
    codigo VARCHAR(40) NOT NULL UNIQUE,
    nombre VARCHAR(150) NOT NULL,
    descripcion TEXT NOT NULL,
    precio NUMERIC(10,2) NOT NULL CHECK (precio >= 0),
    categoria_id INT NOT NULL REFERENCES categorias(categoria_id),
    fecha TIMESTAMP NOT NULL DEFAULT NOW(),
    estado VARCHAR(10) NOT NULL DEFAULT 'PENDIENTE'
        CHECK (estado IN ('PENDIENTE','PUBLICADO'))
);

INSERT INTO categorias (categoria_id, nombre) VALUES
 (1,'Teclados'),(2,'Monitores'),(3,'Mouses')
ON CONFLICT DO NOTHING;

INSERT INTO productos (producto_id, codigo, nombre, descripcion, precio, categoria_id) VALUES
 (1,'TEC-001','Teclado Mecánico Redragon K552','Teclado mecánico compacto switches rojos',45.00,1),
 (2,'TEC-002','Teclado Logitech K380','Teclado Bluetooth multidispositivo',38.50,1),
 (3,'TEC-003','Teclado Corsair K70','Teclado mecánico RGB gamer',120.00,1),
 (4,'TEC-004','Teclado HP 150','Teclado USB estándar de oficina',15.00,1),
 (5,'TEC-005','Teclado Razer BlackWidow','Teclado mecánico switches verdes',110.00,1),
 (6,'TEC-006','Teclado Keychron K2','Teclado mecánico inalámbrico 75%',89.90,1),
 (7,'TEC-007','Teclado Logitech MX Keys','Teclado inalámbrico retroiluminado',105.00,1),
 (8,'MON-001','Monitor Samsung 24"','Monitor Full HD panel IPS',140.00,2),
 (9,'MON-002','Monitor LG 27"','Monitor QHD 75Hz',210.00,2),
 (10,'MON-003','Monitor Dell 32"','Monitor 4K UHD',380.00,2),
 (11,'MON-004','Monitor AOC 22"','Monitor Full HD económico',95.00,2),
 (12,'MON-005','Monitor ASUS 27" Gamer','Monitor 165Hz QHD',295.00,2),
 (13,'MON-006','Monitor BenQ 24"','Monitor Full HD para oficina',130.00,2),
 (14,'MON-007','Monitor Acer 34" Ultrawide','Monitor curvo ultrawide',420.00,2),
 (15,'MOU-001','Mouse Logitech M170','Mouse inalámbrico compacto',12.00,3),
 (16,'MOU-002','Mouse Razer DeathAdder','Mouse gamer óptico',55.00,3),
 (17,'MOU-003','Mouse Logitech MX Master 3','Mouse ergonómico inalámbrico',99.00,3),
 (18,'MOU-004','Mouse HP X1000','Mouse USB con cable',8.50,3),
 (19,'MOU-005','Mouse Corsair Harpoon','Mouse gamer RGB',32.00,3),
 (20,'MOU-006','Mouse Microsoft Bluetooth','Mouse Bluetooth silencioso',25.00,3)
ON CONFLICT (codigo) DO NOTHING;

-- Ajusta las secuencias para que los próximos INSERT no choquen con los IDs fijos
SELECT setval('categorias_categoria_id_seq', (SELECT MAX(categoria_id) FROM categorias));
SELECT setval('productos_producto_id_seq', (SELECT MAX(producto_id) FROM productos));
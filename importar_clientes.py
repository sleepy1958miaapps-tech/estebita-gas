import sqlite3

# Conexión a la base de datos
conn = sqlite3.connect('estebita.db')
cursor = conn.cursor()

# Crear tabla si no existe
cursor.execute('''
    CREATE TABLE IF NOT EXISTS clientes (
        cedula TEXT PRIMARY KEY,
        nombre TEXT,
        apellido TEXT,
        telefono TEXT,
        direccion TEXT
    )
''')

# Lista de clientes importada de Base44
CLIENTES_BASE44 = [
    # Tu lista original de clientes aquí
]

agregados = 0

# Insertar o actualizar cada cliente
for cliente in CLIENTES_BASE44:
    cedula, nombre, apellido, telefono = cliente

    # Formato de teléfono con +58 sin el cero sobrante
    if telefono:
        tel_limpio = telefono.replace('-', '').replace(' ', '').strip()
        if tel_limpio.startswith('0'):
            tel_limpio = tel_limpio[1:]
        tel_formateado = f"+58{tel_limpio}"
    else:
        tel_formateado = ""

    cursor.execute('''
        INSERT OR REPLACE INTO clientes (cedula, nombre, apellido, telefono, direccion)
        VALUES (?, ?, ?, ?, ?)
    ''', (cedula, nombre, apellido, tel_formateado, ""))
    agregados += 1

conn.commit()
conn.close()

print(f"¡Proceso completado! Se procesaron {agregados} clientes correctamente.")
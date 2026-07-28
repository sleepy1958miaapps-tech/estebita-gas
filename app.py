from flask import Flask, render_template, request, jsonify, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)

DB_NAME = "estebita.db"

def inicializar_base_datos():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Tabla Clientes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            cedula TEXT PRIMARY KEY,
            nombre TEXT,
            apellido TEXT,
            telefono TEXT,
            direccion TEXT
        )
    """)
    
    # Tabla Pedidos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cedula_cliente TEXT,
            tamano_cilindro TEXT,
            cantidad INTEGER,
            cantidad_bombonas INTEGER,
            monto_bs REAL,
            fecha TEXT,
            estado TEXT,
            tickets TEXT,
            metodo_pago TEXT,
            referencia TEXT
        )
    """)
    
    # Tabla Precios / Configuración
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS precios (
            tamano TEXT PRIMARY KEY,
            precio REAL
        )
    """)

    # Tabla Config / Tasa
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracion (
            clave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)
    
    # Valor base por defecto si está recién instalada
    cursor.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES ('tasa_bcv', '36.50')")
    cursor.execute("INSERT OR IGNORE INTO precios (tamano, precio) VALUES ('10kg', 100.0), ('18kg', 180.0), ('27kg', 270.0), ('43kg', 430.0)")
    
    conn.commit()
    conn.close()

# Inicializar DB siempre al arrancar
inicializar_base_datos()

def obtener_tasa_bcv():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT valor FROM configuracion WHERE clave = 'tasa_bcv'")
        row = cursor.fetchone()
        conn.close()
        return float(row[0]) if row else 36.50
    except Exception:
        return 36.50

# ☀️ FLUJO MATUTINO: Al iniciar la app, ir directo a la pantalla de Precios / Tasa
@app.route('/')
def index():
    return redirect(url_for('precios'))

@app.route('/precios', methods=['GET', 'POST'])
def precios():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    if request.method == 'POST':
        # Captura la tasa ingresada en la mañana
        tasa_nueva = request.form.get('tasa_bcv') or request.form.get('tasa')
        if tasa_nueva:
            tasa_limpia = str(tasa_nueva).replace(',', '.').strip()
            cursor.execute("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES ('tasa_bcv', ?)", (tasa_limpia,))
            conn.commit()
            conn.close()
            # Una vez guardada la tasa, redirige automáticamente a la toma de pedidos
            return redirect(url_for('nuevo_pedido'))

    conn.close()
    tasa = obtener_tasa_bcv()
    return render_template('precios.html', tasa=tasa)

@app.route('/nuevo_pedido')
@app.route('/pedidos')
def nuevo_pedido():
    tasa = obtener_tasa_bcv()
    return render_template('pedidos.html', tasa=tasa)

@app.route('/buscar_cliente/<cedula>')
def buscar_cliente(cedula):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clientes WHERE cedula = ?", (cedula.strip(),))
    cliente = cursor.fetchone()
    conn.close()
    
    if cliente:
        return jsonify(dict(cliente))
    return jsonify({}), 404

@app.route('/guardar_pedido', methods=['POST'])
def guardar_pedido():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        data = request.get_json() or {}
        print("--> [GUARDAR_PEDIDO] Payload recibido:", data)

        cedula = str(data.get('cedula_cliente', '')).strip()
        nombre = str(data.get('nombre', '')).strip()
        apellido = str(data.get('apellido', '')).strip()
        telefono = str(data.get('telefono', '')).strip()
        direccion = str(data.get('direccion', '')).strip()

        tamano = str(data.get('tamano_cilindro', '')).strip()
        
        raw_cant = data.get('cantidad_bombonas') or data.get('cantidad') or 1
        cantidad_bombonas = int(raw_cant)

        raw_monto = str(data.get('monto_bs', '0')).replace(',', '.').strip()
        try:
            monto_bs = float(raw_monto)
        except ValueError:
            monto_bs = 0.0

        tickets = str(data.get('tickets', '')).strip()
        metodo_pago = str(data.get('metodo_pago', 'Efectivo')).strip()
        referencia = str(data.get('referencia', '')).strip()
        
        fecha_actual = datetime.now().strftime("%Y-%m-%d")
        estado_inicial = "Por Entregar"

        # 1. Guardar/Actualizar Cliente
        if cedula:
            cursor.execute("""
                INSERT INTO clientes (cedula, nombre, apellido, telefono, direccion)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(cedula) DO UPDATE SET
                    nombre=excluded.nombre,
                    apellido=excluded.apellido,
                    telefono=excluded.telefono,
                    direccion=excluded.direccion
            """, (cedula, nombre, apellido, telefono, direccion))

        # 2. Insertar Pedido
        cursor.execute("""
            INSERT INTO pedidos (
                cedula_cliente, tamano_cilindro, cantidad, cantidad_bombonas, 
                monto_bs, fecha, estado, tickets, metodo_pago, referencia
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cedula, tamano, cantidad_bombonas, cantidad_bombonas,
            monto_bs, fecha_actual, estado_inicial, tickets, metodo_pago, referencia
        ))

        conn.commit()
        return jsonify({"status": "success", "message": "Pedido guardado correctamente"})

    except Exception as e:
        conn.rollback()
        print("❌ [GUARDAR_PEDIDO] Error:", str(e))
        return jsonify({"status": "error", "message": f"Error servidor: {str(e)}"}), 500
    finally:
        conn.close()

@app.route('/seguimiento_pedidos')
@app.route('/seguimiento')
def seguimiento_pedidos():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Limpiar formato de fechas previas si tenían hora
    try:
        cursor.execute("UPDATE pedidos SET fecha = SUBSTR(fecha, 1, 10) WHERE LENGTH(fecha) > 10;")
        conn.commit()
    except Exception:
        pass

    fecha_filtro = request.args.get('fecha', '').strip()
    busqueda = request.args.get('busqueda', '').strip()
    ref_punto = request.args.get('ref_punto', '').strip()
    estado_filtro = request.args.get('estado', '').strip()
    
    sql = """
        SELECT 
            p.id, p.cedula_cliente, p.tamano_cilindro, p.cantidad, 
            p.monto_bs, p.fecha, p.estado, p.tickets, p.metodo_pago, p.referencia,
            c.nombre, c.apellido, c.telefono, c.direccion
        FROM pedidos p
        LEFT JOIN clientes c ON p.cedula_cliente = c.cedula
        WHERE 1=1
    """
    params = []

    if fecha_filtro:
        sql += " AND p.fecha LIKE ?"
        params.append(f"%{fecha_filtro}%")

    if busqueda:
        sql += " AND (p.cedula_cliente LIKE ? OR c.nombre LIKE ? OR c.apellido LIKE ?)"
        term = f"%{busqueda}%"
        params.extend([term, term, term])

    if estado_filtro:
        sql += " AND p.estado = ?"
        params.append(estado_filtro)

    if ref_punto:
        sql += " AND p.referencia LIKE ?"
        params.append(f"%{ref_punto}%")

    sql += " ORDER BY p.id DESC"

    cursor.execute(sql, params)
    pedidos = cursor.fetchall()
    conn.close()
    
    return render_template('seguimiento_pedidos.html', pedidos=pedidos)

@app.route('/ver_base_datos')
def ver_base_datos():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM pedidos ORDER BY id DESC LIMIT 10")
    pedidos = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("SELECT * FROM clientes ORDER BY cedula DESC LIMIT 10")
    clientes = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return jsonify({
        "total_pedidos": len(pedidos),
        "ultimos_pedidos": pedidos,
        "ultimos_clientes": clientes
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
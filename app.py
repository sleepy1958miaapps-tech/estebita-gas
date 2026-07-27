from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from functools import wraps
import sqlite3
from datetime import datetime, date, timedelta
import os

app = Flask(__name__)
app.secret_key = "estebita_gas_clave_super_secreta_2026"

# =========================================================
# 🔐 LISTA DE USUARIOS PERMITIDOS Y CONTRASEÑAS
# =========================================================
USUARIOS = {
    "Samantha25": "Samantha.123",
    "Sleepy1958": "123.Samantha"
}

# =========================================================
# DECORADOR Y RUTAS DE SEGURIDAD
# =========================================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        clave = request.form.get('clave', '').strip()

        if usuario in USUARIOS and USUARIOS[usuario] == clave:
            session['usuario'] = usuario
            return redirect(url_for('index'))
        else:
            error = "Usuario o contraseña incorrectos"

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('login'))

# =========================================================
# ACTUALIZACIÓN SEGURA DE BASE DE DATOS
# =========================================================
def actualizar_base_datos():
    conn = sqlite3.connect("estebita.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracion (
            id INTEGER PRIMARY KEY,
            tasa REAL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id TEXT,
            cedula_cliente TEXT,
            tamano_cilindro TEXT,
            cantidad INTEGER,
            cantidad_bombonas INTEGER,
            monto_bs REAL,
            fecha TEXT,
            estado TEXT DEFAULT 'Recibido',
            tickets TEXT,
            metodo_pago TEXT,
            referencia TEXT
        )
    """)

    columnas_necesarias = [
        ("cedula_cliente", "TEXT"),
        ("cantidad_bombonas", "INTEGER"),
        ("monto_bs", "REAL DEFAULT 0.0"),
        ("estado", "TEXT DEFAULT 'Recibido'"),
        ("tickets", "TEXT"),
        ("metodo_pago", "TEXT"),
        ("referencia", "TEXT")
    ]

    for columna, tipo in columnas_necesarias:
        try:
            cursor.execute(f"ALTER TABLE pedidos ADD COLUMN {columna} {tipo}")
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()

actualizar_base_datos()

# =========================================================
# 1. INICIO / DASHBOARD
# =========================================================
@app.route('/')
def index():
    return render_template('base.html')

# =========================================================
# 2. CLIENTES
# =========================================================
@app.route('/clientes')
def clientes():
    conn = sqlite3.connect('estebita.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clientes")
    lista_clientes = cursor.fetchall()
    conn.close()
    return render_template('clientes.html', clientes=lista_clientes)

@app.route('/buscar_cliente/<cedula>')
def buscar_cliente(cedula):
    conn = sqlite3.connect('estebita.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clientes WHERE cedula = ?", (cedula,))
    cliente = cursor.fetchone()
    conn.close()
    
    if cliente:
        return jsonify({
            'encontrado': True,
            'nombre': cliente['nombre'],
            'apellido': cliente['apellido'],
            'telefono': cliente['telefono'],
            'direccion': cliente['direccion']
        })
    return jsonify({'encontrado': False})

# =========================================================
# 3. REGISTRO DE PEDIDOS
# =========================================================
@app.route('/nuevo_pedido')
def nuevo_pedido():
    return render_template('pedidos.html')

@app.route('/guardar_pedido', methods=['POST'])
def guardar_pedido():
    try:
        data = request.get_json()

        cedula = data.get('cedula_cliente')
        nombre = data.get('nombre', '').strip()
        apellido = data.get('apellido', '').strip()
        telefono = data.get('telefono', '').strip()
        direccion = data.get('direccion', '').strip()

        tamano = data.get('tamano_cilindro')
        cantidad = data.get('cantidad_bombonas')
        monto_bs = data.get('monto_bs')
        tickets = data.get('tickets')
        metodo_pago = data.get('metodo_pago')
        referencia = data.get('referencia')

        if not cedula:
            return jsonify({'status': 'error', 'message': 'La cédula del cliente es obligatoria.'})

        conn = sqlite3.connect('estebita.db')
        cursor = conn.cursor()

        # 1. Verificar o crear cliente automáticamente
        cursor.execute("SELECT id FROM clientes WHERE cedula = ?", (cedula,))
        cliente = cursor.fetchone()

        if cliente:
            cliente_id = cliente[0]
        else:
            if not nombre or not apellido:
                conn.close()
                return jsonify({'status': 'error', 'message': 'Nombre y Apellido son obligatorios para cliente nuevo.'})

            cursor.execute("""
                INSERT INTO clientes (cedula, nombre, apellido, telefono, direccion)
                VALUES (?, ?, ?, ?, ?)
            """, (cedula, nombre, apellido, telefono, direccion))
            cliente_id = cursor.lastrowid

        # 2. Registrar el Pedido / Venta
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            INSERT INTO pedidos (cliente_id, cedula_cliente, tamano_cilindro, cantidad_bombonas, monto_bs, tickets, metodo_pago, referencia, fecha, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Entregado')
        """, (cliente_id, cedula, tamano, cantidad, monto_bs, tickets, metodo_pago, referencia, fecha_actual))

        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'message': 'Venta registrada correctamente.'})

    except Exception as e:
        print(f"Error al guardar pedido: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

# =========================================================
# 4. PRECIOS & TASA
# =========================================================
@app.route('/precios', methods=['GET', 'POST'])
def precios():
    if request.method == 'POST':
        nueva_tasa = request.form.get('tasa_cambio')
        if nueva_tasa:
            try:
                texto_limpio = str(nueva_tasa).replace(',', '.').strip()
                valor_tasa = float(texto_limpio)

                conn = sqlite3.connect("estebita.db", timeout=10)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO configuracion (id, tasa) 
                    VALUES (1, ?)
                """, (valor_tasa,))
                conn.commit()
                conn.close()
                print(f"--> ¡GUARDADO EXITOSO EN SQLITE: {valor_tasa} Bs.!")
            except Exception as e:
                print(f"--> ERROR GUARDANDO EN BD: {e}")

        return redirect(url_for('precios'))

    tasa_actual = ""  # Queda vacío si no hay registro previo en la BD
    try:
        conn = sqlite3.connect("estebita.db", timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT tasa FROM configuracion WHERE id = 1")
        row = cursor.fetchone()
        if row and row[0] is not None:
            tasa_actual = float(row[0])
        conn.close()
    except Exception as e:
        print(f"--> ERROR LEYENDO BD: {e}")

    precios_usd = {
        '10kg': 4.0,
        '18kg': 10.0,
        '21kg': 13.0,
        '28kg': 15.0,
        '43kg': 20.0
    }

    return render_template('precios.html', precios_usd=precios_usd, tasa_cambio=tasa_actual)

# =========================================================
# 5. WHATSAPP / NOTIFICACIONES
# =========================================================
@app.route("/whatsapp")
def whatsapp():
    ayer = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    conn = sqlite3.connect("estebita.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT 
                p.id AS id_pedido,
                p.fecha,
                c.nombre,
                c.telefono
            FROM pedidos p
            LEFT JOIN clientes c ON CAST(p.cedula_cliente AS TEXT) = CAST(c.cedula AS TEXT)
            WHERE DATE(p.fecha) = ? AND (p.estado IS NULL OR p.estado != 'Cancelado')
        """, (ayer,))
        pedidos_raw = cursor.fetchall()
    except Exception as e:
        print("Error en consulta WhatsApp:", e)
        pedidos_raw = []

    conn.close()

    pedidos_procesados = []
    for p in pedidos_raw:
        tel = p["telefono"] if p["telefono"] else ""
        tel_limpio = (
            str(tel)
            .replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        )

        if tel_limpio.startswith("+580"):
            tel_limpio = "+58" + tel_limpio[4:]
        elif tel_limpio.startswith("0"):
            tel_limpio = "+58" + tel_limpio[1:]
        elif not tel_limpio.startswith("+58"):
            tel_limpio = "+58" + tel_limpio

        nombre_str = p["nombre"] if p["nombre"] else "Cliente"
        partes = nombre_str.strip().split()
        apellido = partes[-1] if len(partes) > 1 else partes[0]

        pedidos_procesados.append({
            "id_pedido": p["id_pedido"],
            "fecha": p["fecha"],
            "nombre_completo": nombre_str,
            "apellido": apellido,
            "telefono": tel_limpio,
        })

    return render_template("whatsapp.html", pedidos=pedidos_procesados, fecha_ayer=ayer)

# =========================================================
# 6. REPORTES DIARIOS
# =========================================================
@app.route('/reporte-diario')
@login_required
def reporte_diario():
    fecha = request.args.get("fecha", date.today().strftime("%Y-%m-%d"))

    conn = sqlite3.connect("estebita.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT 
                tamano_cilindro AS tamano,
                COUNT(DISTINCT id) AS pedidos,
                SUM(COALESCE(cantidad_bombonas, cantidad, 1)) AS cilindros,
                SUM(COALESCE(monto_bs, 0.0)) AS subtotal
            FROM pedidos
            WHERE DATE(fecha) = ? AND (estado IS NULL OR estado != 'Cancelado')
            GROUP BY tamano_cilindro
        """, (fecha,))

        resumen = cursor.fetchall()

        total_pedidos = sum(f["pedidos"] for f in resumen) if resumen else 0
        total_cilindros = sum(f["cilindros"] for f in resumen) if resumen else 0
        total_monto = sum(f["subtotal"] for f in resumen) if resumen else 0

        cursor.execute(
            "SELECT COUNT(DISTINCT cedula_cliente) FROM pedidos WHERE DATE(fecha) = ? AND (estado IS NULL OR estado != 'Cancelado')",
            (fecha,),
        )
        total_clientes = cursor.fetchone()[0] or 0

    except Exception as e:
        print("Error en Reportes:", e)
        resumen = []
        total_pedidos = total_cilindros = total_monto = total_clientes = 0
    finally:
        conn.close()

    return render_template(
        "reportes.html",
        resumen=resumen,
        fecha_seleccionada=fecha,
        total_pedidos=total_pedidos,
        total_cilindros=total_cilindros,
        total_monto=total_monto,
        total_clientes=total_clientes,
    )

# =========================================================
# 7. GESTIÓN DE PEDIDOS / LOGÍSTICA
# =========================================================
@app.route('/seguimiento_pedidos')
def seguimiento_pedidos():
    fecha_actual = request.args.get("fecha", "")
    busqueda = request.args.get("busqueda", "").strip()
    ref_punto = request.args.get("ref_punto", "").strip()
    estado = request.args.get("estado", "").strip()

    conn = sqlite3.connect("estebita.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        query = """
            SELECT 
                p.*, 
                c.nombre, 
                c.apellido, 
                c.telefono 
            FROM pedidos p
            LEFT JOIN clientes c ON CAST(p.cedula_cliente AS TEXT) = CAST(c.cedula AS TEXT)
            WHERE 1=1
        """
        params = []

        if fecha_actual:
            query += " AND DATE(p.fecha) = ?"
            params.append(fecha_actual)

        if busqueda:
            query += " AND (p.cedula_cliente LIKE ? OR c.nombre LIKE ? OR c.apellido LIKE ? OR c.telefono LIKE ?)"
            term = f"%{busqueda}%"
            params.extend([term, term, term, term])

        if ref_punto:
            query += " AND p.referencia LIKE ?"
            params.append(f"%{ref_punto}%")

        if estado:
            query += " AND p.estado = ?"
            params.append(estado)

        query += " ORDER BY p.id DESC"

        cursor.execute(query, params)
        pedidos_raw = cursor.fetchall()
        pedidos = [dict(row) for row in pedidos_raw]

    except Exception as e:
        print("Error en consulta de Gestión de Pedidos:", e)
        pedidos = []
    finally:
        conn.close()

    return render_template(
        "seguimiento_pedidos.html", 
        pedidos=pedidos,
        fecha_actual=fecha_actual,
        busqueda=busqueda,
        ref_punto=ref_punto,
        estado_filtro=estado
    )

@app.route('/actualizar_estado_pedidos', methods=['POST'])
def actualizar_estado_pedidos():
    try:
        data = request.get_json()
        ids = data.get('ids', [])
        nuevo_estado = data.get('nuevo_estado', '')

        if not ids or not nuevo_estado:
            return jsonify({'status': 'error', 'message': 'Datos incompletos'}), 400

        conn = sqlite3.connect("estebita.db")
        cursor = conn.cursor()
        
        placeholders = ','.join(['?'] * len(ids))
        query = f"UPDATE pedidos SET estado = ? WHERE id IN ({placeholders})"
        
        cursor.execute(query, [nuevo_estado] + ids)
        conn.commit()
        conn.close()

        return jsonify({'status': 'success'})
    except Exception as e:
        print("Error al actualizar estados:", e)
        return jsonify({'status': 'error', 'message': str(e)}), 500

# =========================================================
# RUTA TEMPORAL REPARAR USUARIO
# =========================================================
@app.route('/crear_admin_urgente')
def crear_admin_urgente():
    try:
        conn = sqlite3.connect("estebita.db")
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                rol TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            INSERT OR REPLACE INTO usuarios (id, username, password, rol)
            VALUES (1, 'admin', 'admin123', 'admin')
        ''')
        conn.commit()
        conn.close()
        return "<h1>✅ Usuario 'admin' creado con contraseña 'admin123' exitosamente!</h1>"
    except Exception as e:
        return f"<h1>❌ Error al crear usuario: {e}</h1>"

# =========================================================
# ARRANQUE DEL SERVIDOR
# =========================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
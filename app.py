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
            # REDIRECCIÓN AUTOMÁTICA A PRECIOS AL INICIAR SESIÓN
            return redirect(url_for('precios'))
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
## =========================================================
# 3. REGISTRO DE PEDIDOS
# =========================================================
@app.route('/nuevo_pedido')
def nuevo_pedido():
    tasa_actual = None
    try:
        conn = sqlite3.connect("estebita.db", timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT tasa FROM configuracion WHERE id = 1")
        row = cursor.fetchone()
        if row and row[0] is not None and float(row[0]) > 0:
            tasa_actual = float(row[0])
            print(f"--> TASA LEÍDA PARA NUEVO PEDIDO: {tasa_actual} Bs.")
        else:
            print("--> LA TASA EN BD ESTÁ VACÍA O ES CERO")
        conn.close()
    except Exception as e:
        print(f"--> ERROR AL LEER TASA: {e}")

    # Enviamos ambas variables por compatibilidad con cualquier parte de la plantilla
    return render_template('pedidos.html', tasa_cambio=tasa_actual, tasa_dolar=tasa_actual)
# =========================================================

#=========================================================
# 3.1 PROCESAR Y GUARDAR/CONFIRMAR PEDIDO (CON AUTOCREACIÓN DE CLIENTE)
# =========================================================
@app.route('/guardar_pedido', methods=['POST'])
@app.route('/confirmar_pedido', methods=['POST'])
def procesar_pedido():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'status': 'error', 'message': 'No se recibieron datos'}), 400

        conn = sqlite3.connect("estebita.db", timeout=10)
        cursor = conn.cursor()

        # Extraer campos
        cedula = data.get('cedula_cliente') or data.get('cedula') or ""
        tamano = data.get('tamano_cilindro') or data.get('tamano') or ""
        cantidad = data.get('cantidad_bombonas') or data.get('cantidad', 1)
        monto_bs = data.get('monto_bs') or data.get('monto', 0.0)
        metodo = data.get('metodo_pago') or data.get('metodo') or ""
        referencia = data.get('referencia', '')
        tickets = data.get('tickets', '')
        nombre = data.get('nombre', 'Cliente')
        apellido = data.get('apellido', 'Registrado')
        telefono = data.get('telefono', '')
        direccion = data.get('direccion', '')
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. Asegurar que el cliente exista en la tabla 'clientes'
        if cedula:
            cursor.execute("SELECT cedula FROM clientes WHERE cedula = ?", (cedula,))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO clientes (cedula, nombre, apellido, telefono, direccion)
                    VALUES (?, ?, ?, ?, ?)
                """, (cedula, nombre, apellido, telefono, direccion))

        # 2. Registrar el pedido en la tabla 'pedidos'
        cursor.execute("""
            INSERT INTO pedidos (
                cedula_cliente, tamano_cilindro, cantidad, cantidad_bombonas, 
                monto_bs, fecha, estado, tickets, metodo_pago, referencia
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Recibido', ?, ?, ?)
        """, (cedula, cedula, tamano, cantidad, cantidad, monto_bs, fecha_actual, tickets, metodo, referencia))

        conn.commit()
        conn.close()

        print(f"--> ¡PEDIDO GUARDADO Y CLIENTE SINCRONIZADO PARA CÉDULA: {cedula}!")
        return jsonify({'success': True, 'status': 'success', 'message': 'Pedido confirmado con éxito'})

    except Exception as e:
        print(f"--> ERROR AL CONFIRMAR PEDIDO: {e}")
        return jsonify({'success': False, 'status': 'error', 'message': str(e)}), 500
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
# 7. Seguimiento Pedidos / LOGÍSTICA
# =========================================================
@app.route('/seguimiento_pedidos')
def seguimiento_pedidos():
    fecha_input = request.args.get("fecha", "").strip()
    busqueda = request.args.get("busqueda", "").strip()
    ref_punto = request.args.get("ref_punto", "").strip()
    estado = request.args.get("estado", "").strip()

    conn = sqlite3.connect("estebita.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Convertir fecha de entrada (DD/MM/YYYY o YYYY-MM-DD) al formato de la BD (YYYY-MM-DD)
    fecha_filtro_db = ""
    if fecha_input:
        try:
            if "/" in fecha_input:
                partes = fecha_input.split("/")
                fecha_filtro_db = f"{partes[2]}-{partes[1]}-{partes[0]}"  # Convierte DD/MM/YYYY a YYYY-MM-DD
            else:
                fecha_filtro_db = fecha_input
        except Exception:
            fecha_filtro_db = fecha_input

    try:
        query = """
            SELECT 
                p.*, 
                COALESCE(c.nombre, 'Cliente') AS nombre, 
                COALESCE(c.apellido, '') AS apellido, 
                COALESCE(c.telefono, '') AS telefono 
            FROM pedidos p
            LEFT JOIN clientes c ON CAST(p.cedula_cliente AS TEXT) = CAST(c.cedula AS TEXT)
            WHERE 1=1
        """
        params = []

        if fecha_filtro_db:
            query += " AND DATE(p.fecha) = ?"
            params.append(fecha_filtro_db)

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
        
        # Formatear la fecha a DD/MM/YYYY para mostrarla en la pantalla
        pedidos = []
        for row in pedidos_raw:
            p = dict(row)
            if p.get("fecha"):
                try:
                    # Convierte "2026-07-27 14:30:00" -> "27/07/2026"
                    fecha_obj = datetime.strptime(p["fecha"].split()[0], "%Y-%m-%d")
                    p["fecha_formateada"] = fecha_obj.strftime("%d/%m/%Y")
                except Exception:
                    p["fecha_formateada"] = p["fecha"]
            else:
                p["fecha_formateada"] = ""
            pedidos.append(p)

    except Exception as e:
        print("Error en consulta de Seguimiento Pedidos:", e)
        pedidos = []
    finally:
        conn.close()

    return render_template(
        "seguimiento_pedidos.html", 
        pedidos=pedidos,
        fecha_actual=fecha_input,
        busqueda=busqueda,
        ref_punto=ref_punto,
        estado_filtro=estado
    )
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
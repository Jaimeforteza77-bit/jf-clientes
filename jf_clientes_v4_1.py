import streamlit as st
import sqlite3
from datetime import date

st.set_page_config(page_title="JF Clientes", page_icon="📋", layout="wide")
DB = "jf_clientes.db"

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def column_exists(c, table, column):
    return column in [r["name"] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]

def init_db():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS clientes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            tipo TEXT,
            direccion TEXT,
            poblacion TEXT,
            notas TEXT
        );
        CREATE TABLE IF NOT EXISTS contactos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            cargo TEXT,
            telefono TEXT,
            email TEXT
        );
        CREATE TABLE IF NOT EXISTS visitas(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            tipo TEXT,
            contacto TEXT,
            comentarios TEXT,
            proxima_visita TEXT
        );
        CREATE TABLE IF NOT EXISTS facturacion_marca(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            anio INTEGER NOT NULL,
            marca TEXT NOT NULL,
            importe REAL NOT NULL DEFAULT 0,
            UNIQUE(cliente_id, anio, marca)
        );
        """)
        if not column_exists(c, "clientes", "marcas"):
            c.execute("ALTER TABLE clientes ADD COLUMN marcas TEXT DEFAULT ''")
        if not column_exists(c, "clientes", "facturacion"):
            c.execute("ALTER TABLE clientes ADD COLUMN facturacion REAL DEFAULT 0")

init_db()

# Entrada de voz desde el iPhone
voz = st.query_params.get("voz", "")
if voz:
    st.session_state["voz_iphone"] = voz

if "flash" not in st.session_state:
    st.session_state.flash = ""

st.title("JF Clientes")
st.caption("Clientes, contactos y seguimiento comercial")

if st.session_state.flash:
    st.success(st.session_state.flash)
    st.session_state.flash = ""

tab_resumen, tab_clientes, tab_nuevo, tab_actividad, tab_proximas = st.tabs(["📊 Resumen", "👥 Clientes", "+ Nuevo cliente", "🗒️ Nueva actividad", "📅 Próximas gestiones"])

with tab_resumen:
    st.subheader("📊 Resumen comercial")
    with conn() as c:
        total_clientes = c.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
    st.metric("👥 Clientes", total_clientes)
    with conn() as c:
        facturacion_total = c.execute(
            "SELECT COALESCE(SUM(importe), 0) FROM facturacion_marca"
        ).fetchone()[0]

st.metric("💰 Facturación total", f"{facturacion_total:,.2f} €")
with conn() as c:
    proximas_gestiones = c.execute(
        "SELECT COUNT(*) FROM visitas WHERE proxima_visita IS NOT NULL"
    ).fetchone()[0]

st.metric("📅 Próximas gestiones", proximas_gestiones)
with conn() as c:
    gestiones_vencidas = c.execute(
        "SELECT COUNT(*) FROM visitas WHERE proxima_visita IS NOT NULL AND proxima_visita < ?",
        (str(date.today()),)
    ).fetchone()[0]

st.metric("🔴 Gestiones vencidas", gestiones_vencidas)
st.divider()
st.subheader("📅 Próximas gestiones")

with conn() as c:
    proximas = c.execute("""
        SELECT v.id, v.proxima_visita, c.nombre, v.contacto, v.comentarios
        FROM visitas v
        JOIN clientes c ON c.id = v.cliente_id
        WHERE v.proxima_visita IS NOT NULL
        ORDER BY v.proxima_visita ASC
        LIMIT 10
    """).fetchall()

hoy = str(date.today())

st.markdown("### 🔴 Gestiones vencidas")
vencidas = [p for p in proximas if p["proxima_visita"] < hoy]

if vencidas:
    for p in vencidas:
        col1, col2 = st.columns([4, 1])

        with col1:
            st.write(
                f"🔴 **{p['proxima_visita']}** - "
                f"**{p['nombre']}** - "
                f"{p['contacto'] or ''} - "
                f"{p['comentarios'] or ''}"
            )

        with col2:
            if st.button("✅ Realizada", key=f"realizada_vencida_{p['id']}"):
                with conn() as c:
                    c.execute(
                        "UPDATE visitas SET proxima_visita = NULL WHERE id = ?",
                        (p["id"],)
                    )
                st.rerun()
else:
    st.success("No hay gestiones vencidas.")

st.markdown("### 🟢 Próximas gestiones")
pendientes = [p for p in proximas if p["proxima_visita"] >= hoy]

if pendientes:
    for p in pendientes:
        col1, col2 = st.columns([4, 1])

        with col1:
            st.write(
                f"🟢 **{p['proxima_visita']}** — "
                f"**{p['nombre']}** — "
                f"{p['contacto'] or ''} — "
                f"{p['comentarios'] or ''}"
            )

        with col2:
            if st.button("✅ Realizada", key=f"realizada_{p['id']}"):
                with conn() as c:
                    c.execute(
                        "UPDATE visitas SET proxima_visita = NULL WHERE id = ?",
                        (p["id"],)
                    )
                st.rerun()
else:
    st.info("No hay próximas gestiones.")
with tab_nuevo:
    st.subheader("Añadir cliente")
    with st.form("nuevo_cliente"):
        nombre = st.text_input("Empresa / cliente *")
        tipo = st.selectbox("Tipo", ["Distribuidor","Arquitecto","Interiorista","Hotel","Constructor","Instalador","Otro"])
        direccion = st.text_input("Dirección")
        poblacion = st.text_input("Población")
        marcas = st.text_input("Marcas / productos expuestos", placeholder="Ej.: Catalano, Quadro Design")
        facturacion = st.number_input("Facturación anual (€)", min_value=0.0, step=1000.0)
        notas = st.text_area("Notas")
        if st.form_submit_button("Guardar cliente", type="primary"):
            if not nombre.strip():
                st.error("Escribe el nombre del cliente.")
            else:
                with conn() as c:
                    existe = c.execute("SELECT id FROM clientes WHERE lower(trim(nombre))=lower(trim(?))",(nombre.strip(),)).fetchone()
                    if existe:
                        st.error("Ya existe un cliente con ese nombre.")
                    else:
                        c.execute("""INSERT INTO clientes(nombre,tipo,direccion,poblacion,notas,marcas,facturacion)
                                     VALUES(?,?,?,?,?,?,?)""",
                                  (nombre.strip(),tipo,direccion,poblacion,notas,marcas,facturacion))
                        st.success("Cliente guardado correctamente.")

with tab_clientes:
    buscar = st.text_input("🔎 Buscar cliente")
    with conn() as c:
        clientes = c.execute("SELECT * FROM clientes ORDER BY nombre").fetchall()
    if buscar:
        clientes = [x for x in clientes if buscar.lower() in x["nombre"].lower()]

    if not clientes:
        st.info("No hay clientes.")

    for cl in clientes:
        with st.expander(f'{cl["nombre"]} · {cl["tipo"] or ""}'):
            st.markdown("### Ficha del cliente")
            c1,c2,c3 = st.columns(3)
            c1.write(f'**Población:** {cl["poblacion"] or "—"}')
            c1.write(f'**Dirección:** {cl["direccion"] or "—"}')
            c2.write(f'**Marcas expuestas:** {cl["marcas"] or "—"}')
            
            st.write(f'**Notas:** {cl["notas"] or "—"}')

            with st.popover("✏️ Editar cliente"):
                with st.form(f'editar_cliente_{cl["id"]}'):
                    enombre = st.text_input("Empresa", cl["nombre"])
                    etipo = st.text_input("Tipo", cl["tipo"] or "")
                    edir = st.text_input("Dirección", cl["direccion"] or "")
                    epob = st.text_input("Población", cl["poblacion"] or "")
                    opciones_marcas = ["Catalano", "Quadro Design", "Water Evolution", "Otra"]
                    marcas_actuales = [m.strip() for m in (cl["marcas"] or "").split(",") if m.strip()]
                    emarcas_lista = st.multiselect("Marcas / productos expuestos", opciones_marcas, default=[m for m in marcas_actuales if m in opciones_marcas])
                    emarcas = ", ".join(emarcas_lista)
                    efact = st.number_input("Facturación anual (€)", min_value=0.0, value=float(cl["facturacion"] or 0), step=1000.0)
                    enotas = st.text_area("Notas", cl["notas"] or "")
                    if st.form_submit_button("Guardar cambios"):
                        with conn() as c:
                            c.execute("""UPDATE clientes SET nombre=?,tipo=?,direccion=?,poblacion=?,marcas=?,facturacion=?,notas=?
                                         WHERE id=?""",(enombre.strip(),etipo,edir,epob,emarcas,efact,enotas,cl["id"]))
                        st.session_state.flash = "✅ Cliente actualizado."
                        st.rerun()

            with st.popover("🗑️ Eliminar cliente"):
                st.warning("También se eliminarán sus contactos y actividades.")
                ok = st.checkbox("Confirmo la eliminación", key=f'okcliente{cl["id"]}')
                if st.button("Eliminar definitivamente", key=f'delcliente{cl["id"]}', disabled=not ok):
                    with conn() as c:
                        c.execute("DELETE FROM contactos WHERE cliente_id=?",(cl["id"],))
                        c.execute("DELETE FROM visitas WHERE cliente_id=?",(cl["id"],))
                        c.execute("DELETE FROM facturacion_marca WHERE cliente_id=?",(cl["id"],))
                        c.execute("DELETE FROM clientes WHERE id=?",(cl["id"],))
                    st.rerun()

            st.markdown("#### Facturación por año y marca")
            MARCAS = ["Catalano", "Quadro Design", "Water Evolution", "Otra"]

            with conn() as c:
                facts = c.execute("""
                    SELECT * FROM facturacion_marca
                    WHERE cliente_id=?
                    ORDER BY anio DESC, marca
                """, (cl["id"],)).fetchall()

            if facts:
                anios = sorted({int(f["anio"]) for f in facts}, reverse=True)
                for a in anios:
                    filas = [f for f in facts if int(f["anio"]) == a]
                    total = sum(float(f["importe"]) for f in filas)
                    st.markdown(f"**{a} — Total: {total:,.2f} €**")
                    for f in filas:
                        q1, q2 = st.columns([8,1])
                        q1.write(f'{f["marca"]}: **{float(f["importe"]):,.2f} €**')
                        if q2.button("🗑️", key=f'delfactmarca{f["id"]}', help="Eliminar esta facturación"):
                            with conn() as c:
                                c.execute("DELETE FROM facturacion_marca WHERE id=?", (f["id"],))
                            st.rerun()
            else:
                st.caption("Sin facturación por marca registrada.")

            with st.form(f'facturacion_marca_{cl["id"]}'):
                fc1, fc2, fc3 = st.columns(3)
                anio = fc1.number_input("Año", min_value=2000, max_value=2100,
                                        value=date.today().year, step=1,
                                        key=f'anio_marca{cl["id"]}')
                marca_sel = fc2.selectbox("Marca", MARCAS, key=f'marca{cl["id"]}')
                otra_marca = ""
                if marca_sel == "Otra":
                    otra_marca = fc2.text_input("Nombre de la marca", key=f'otra_marca{cl["id"]}')
                importe = fc3.number_input("Importe (€)", min_value=0.0, step=1000.0,
                                           key=f'importe_marca{cl["id"]}')
                if st.form_submit_button("Guardar facturación"):
                    marca_final = otra_marca.strip() if marca_sel == "Otra" else marca_sel
                    if not marca_final:
                        st.error("Escribe el nombre de la marca.")
                    else:
                        with conn() as c:
                            c.execute("""
                                INSERT INTO facturacion_marca(cliente_id, anio, marca, importe)
                                VALUES(?,?,?,?)
                                ON CONFLICT(cliente_id, anio, marca)
                                DO UPDATE SET importe=excluded.importe
                            """, (cl["id"], int(anio), marca_final, float(importe)))
                        st.session_state.flash = f"✅ Facturación {int(anio)} · {marca_final} guardada."
                        st.rerun()

            st.markdown("#### Personas de contacto")
            with conn() as c:
                contactos = c.execute("SELECT * FROM contactos WHERE cliente_id=? ORDER BY nombre",(cl["id"],)).fetchall()

            for p in contactos:
                x1,x2,x3 = st.columns([4,1,1])
                x1.write(f'**{p["nombre"]}** — {p["cargo"] or "Sin cargo"} · 📞 {p["telefono"] or "—"} · ✉️ {p["email"] or "—"}')
                if x2.button(" ✏️ ", key=f'editcontacto{p["id"]}', help="Editar contacto"):
                   st.session_state[f'editando_contacto_{p["id"]}'] = True
                   st.rerun()

                if st.session_state.get(f'editando_contacto_{p["id"]}', False):
                    with st.form(f'editar_contacto_{p["id"]}'):
                        nuevo_nombre = st.text_input("Nombre", value=p["nombre"] or "")
                        nuevo_cargo = st.text_input("Cargo", value=p["cargo"] or "")
                        nuevo_telefono = st.text_input("Teléfono", value=p["telefono"] or "")
                        nuevo_email = st.text_input("Email", value=p["email"] or "")

                        if st.form_submit_button("Guardar cambios"):
                            with conn() as c:
                                c.execute(
                               "UPDATE contactos SET nombre=?, cargo=?, telefono=?, email=? WHERE id=?",
                               (nuevo_nombre, nuevo_cargo, nuevo_telefono, nuevo_email, p["id"])
                           )
                            st.session_state[f'editando_contacto_{p["id"]}'] = False
                            st.rerun()
                    if x3.button("🗑️", key=f'delcontacto{p["id"]}', help="Eliminar contacto"):
                        with conn() as c:
                           c.execute("DELETE FROM contactos WHERE id=?",(p["id"],))
                        st.rerun()

            with st.form(f'nuevo_contacto_{cl["id"]}', clear_on_submit=True):
                a,b = st.columns(2)
                nom = a.text_input("Nombre contacto *", key=f'nom{cl["id"]}')
                cargo = b.text_input("Cargo", key=f'cargo{cl["id"]}')
                tel = a.text_input("Teléfono", key=f'tel{cl["id"]}')
                email = b.text_input("Email", key=f'email{cl["id"]}')
                if st.form_submit_button("Añadir contacto"):
                    if nom.strip():
                        with conn() as c:
                            c.execute("INSERT INTO contactos(cliente_id,nombre,cargo,telefono,email) VALUES(?,?,?,?,?)",
                                      (cl["id"],nom.strip(),cargo,tel,email))
                        st.rerun()

            st.markdown("#### 💰 Facturación")
            with conn() as c:
                facturacion_anual = c.execute(
                    "SELECT COALESCE(SUM(importe), 0) FROM facturacion_marca WHERE cliente_id=?",
                    (cl["id"],)
                ).fetchone()[0]
            st.write(f"**Facturación anual:** {facturacion_anual:,.2f} €")
            st.markdown("#### Historial de actividad")
            with conn() as c:
                actividades = c.execute("SELECT * FROM visitas WHERE cliente_id=? ORDER BY fecha DESC,id DESC",(cl["id"],)).fetchall()
            if not actividades:
                st.caption("Sin actividades registradas.")
            for v in actividades:
                a1,a2,a3 = st.columns([8,1,1])
                a1.write(f'**{v["fecha"]} · {v["tipo"]}**' + (f' · {v["contacto"]}' if v["contacto"] else ""))
                a1.write(v["comentarios"] or "Sin comentarios")
                if a2.button("✏️", key=f'editvisita{v["id"]}', help="Editar actividad"):
                    st.session_state[f'editando_visita_{v["id"]}'] = True
                    st.rerun()
                if st.session_state.get(f'editando_visita_{v["id"]}', False):
                    with st.form(f'editar_visita_{v["id"]}'):
                        nueva_fecha = st.date_input(
                            "Fecha",
                            value=date.fromisoformat(v["fecha"])
                        )
                        nuevo_tipo = st.selectbox(
                            "Actividad",
                            ["Visita", "Llamada", "Email", "Reunión", "Otro"],
                            index=["Visita", "Llamada", "Email", "Reunión", "Otro"].index(v["tipo"])
                        )
                        nuevo_contacto = st.text_input(
                            "Persona de contacto",
                            value=v["contacto"] or ""
                        )
                        nuevos_comentarios = st.text_area(
                            "¿Qué habéis hablado?",
                            value=v["comentarios"] or ""
                        )

                        if st.form_submit_button("Guardar cambios"):
                            with conn() as c:
                                c.execute(
                                    """UPDATE visitas
                                    SET fecha=?, tipo=?, contacto=?, comentarios=?
                                    WHERE id=?""",
                                    (
                                        str(nueva_fecha),
                                        nuevo_tipo,
                                        nuevo_contacto,
                                        nuevos_comentarios,
                                        v["id"]
                                     )
                                )
                            st.session_state[f'editando_visita_{v["id"]}'] = False
                            st.rerun()
                if v["proxima_visita"]:
                    a1.caption(f'Próxima gestión: {v["proxima_visita"]}')
                if a2.button("🗑️", key=f'delvisita{v["id"]}', help="Eliminar actividad"):
                    with conn() as c:
                        c.execute("DELETE FROM visitas WHERE id=?",(v["id"],))
                    st.rerun()
                st.divider()

with tab_actividad:
    with conn() as c:
        clientes_act = c.execute("SELECT * FROM clientes ORDER BY nombre").fetchall()
    if not clientes_act:
        st.info("Primero añade un cliente.")
    else:
        opciones = {x["nombre"]: x["id"] for x in clientes_act}
        with st.form("nueva_actividad"):
            elegido = st.selectbox("Cliente *", list(opciones.keys()))
            fecha = st.date_input("Fecha", date.today())
            tipo_visita = st.selectbox("Actividad", ["Visita","Llamada","Email","Reunión","Otro"])
            with conn() as c:
                contactos_cliente = c.execute("SELECT nombre FROM contactos WHERE cliente_id=? ORDER BY nombre", (opciones[elegido],)).fetchall()
            nombres_contactos = [x["nombre"] for x in contactos_cliente]
            contacto = st.selectbox("Persona de contacto", ["Selecciona contacto"] + nombres_contactos)
            comentarios = st.text_area("¿Qué habéis hablado?", height=140)
            usar_proxima = st.checkbox("Programar próxima gestión", key="usar_proxima")
        if usar_proxima:
            proxima = st.date_input("Próxima gestión", date.today())
        else:
            proxima = None
        if st.form_submit_button("Guardar actividad", type="primary"):
            with conn() as c:
                c.execute("""INSERT INTO visitas(cliente_id,fecha,tipo,contacto,comentarios,proxima_visita)
                                 VALUES(?,?,?,?,?,?)""",
                              (opciones[elegido],str(fecha),tipo_visita,contacto,comentarios,
                               str(proxima) if proxima else None))
                st.session_state.flash = "✅ Actividad guardada correctamente."
                st.rerun()

with tab_proximas:
    st.subheader("📅 Próximas gestiones")
    with conn() as c:
        proximas = c.execute("""
            SELECT visitas.*, clientes.nombre AS cliente_nombre
            FROM visitas
            JOIN clientes ON visitas.cliente_id = clientes.id
            WHERE visitas.proxima_visita IS NOT NULL
            ORDER BY visitas.proxima_visita
        """).fetchall()
    if not proximas:
        st.info("No hay próximas gestiones programadas.")
    else:
        for p in proximas:
            fecha_gestion = date.fromisoformat(p["proxima_visita"])
        if fecha_gestion < date.today():
            estado = "🔴 VENCIDA"
        elif fecha_gestion == date.today():
            estado = "🟠 HOY"
        else:
            estado = "🟢 PRÓXIMA"
            st.write(f"{estado} · 📅 **{p['proxima_visita']} · {p['cliente_nombre']}** · {p['tipo']} · {p['contacto'] or 'Sin contacto'}")
            st.write(p["comentarios"] or "Sin comentarios")
            col1, col2 = st.columns(2)

            with col1:
                        if st.button("✅ Hecho", key=f"hecho_{p['id']}"):
                            with conn() as c:
                                c.execute(
                                    "UPDATE visitas SET proxima_visita=NULL WHERE id=?",
                                    (p["id"],)
                                )
                            st.rerun()

            with col2:
                        nueva_fecha = st.date_input(
                            "📅 Aplazar hasta",
                            value=fecha_gestion,
                            key=f"aplazar_fecha_{p['id']}"
                        )
                        if st.button("📅 Aplazar", key=f"aplazar_{p['id']}"):
                            with conn() as c:
                                c.execute(
                                    "UPDATE visitas SET proxima_visita=? WHERE id=?",
                                    (str(nueva_fecha), p["id"])
                                )
                            st.rerun()

    st.divider()

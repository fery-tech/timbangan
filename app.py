from flask import Flask, jsonify, request, render_template, redirect, url_for
import mysql.connector
from datetime import datetime
from collections import defaultdict

# Inisialisasi Flask
app = Flask(__name__)

# Koneksi ke MySQL
db = mysql.connector.connect(
    host="103.94.238.27",
    user="sengkuni3523_sumopod",
    password="3UO4h_9uLChBvZG3",
    database="sengkuni3523_timbangan"
)

# Endpoint untuk mengambil data petani
@app.route('/api/petani', methods=['GET'])
def get_petani():
    with db.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT id, nama_petani FROM petani")
        data = cursor.fetchall()
    return jsonify(data)

# Endpoint untuk mengambil data sayur
@app.route('/api/sayur', methods=['GET'])
def get_sayur():
    with db.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT id, nama_sayur FROM sayur")
        data = cursor.fetchall()
    return jsonify(data)

# Endpoint untuk mengambil data grade
@app.route('/api/grade', methods=['GET'])
def get_grade():
    with db.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT id, grade FROM grade")
        data = cursor.fetchall()
    return jsonify(data)

@app.route('/api/submit', methods=['POST'])
def submit_data():
    data = request.json
    petani = data['petani']
    sayur = data['sayur']
    grade = data['grade']
    weight = float(data['weight'])

    with db.cursor(dictionary=True) as cursor:
        # Ambil harga saat ini
        cursor.execute("SELECT harga_per_kg, harga_jual FROM harga WHERE sayur=%s AND grade=%s", (sayur, grade))
        harga_row = cursor.fetchone()

        if not harga_row:
            return jsonify({"error": "Harga belum tersedia untuk kombinasi ini"}), 400

        harga_per_kg = float(harga_row['harga_per_kg'])
        harga_jual = float(harga_row['harga_jual'])

        total_harga = weight * harga_per_kg
        pendapatan = weight * harga_jual
        keuntungan = pendapatan - total_harga

        # Simpan ke tabel transaksi
        query = """
            INSERT INTO transaksi (petani, sayur, grade, weight, harga_per_kg, harga_jual, total_harga, pendapatan, keuntungan)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (petani, sayur, grade, weight, harga_per_kg, harga_jual, total_harga, pendapatan, keuntungan)
        cursor.execute(query, values)
        db.commit()

    return jsonify({
        "message": "Data berhasil disimpan!",
        "harga_per_kg": harga_per_kg,
        "harga_jual": harga_jual,
        "total_harga": total_harga,
        "pendapatan": pendapatan,
        "keuntungan": keuntungan
    })


# Endpoint untuk mengambil semua transaksi
@app.route('/api/transaksi', methods=['GET'])
def get_transaksi():
    with db.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT * FROM transaksi ORDER BY timestamp DESC")
        data = cursor.fetchall()
    return jsonify(data)

# Endpoint untuk grafik berat per petani
@app.route('/tren_berat', methods=['GET'])
def get_berat_tren():
    start = request.args.get('start')
    end = request.args.get('end')
    range_type = request.args.get('range', 'harian')
    now = datetime.now()

    with db.cursor(dictionary=True) as cursor:
        # Grafik
        cursor.execute("""
            SELECT sayur, grade, petani, SUM(weight) AS total_berat
            FROM transaksi
            WHERE DATE(timestamp) BETWEEN %s AND %s
            GROUP BY sayur, grade, petani
            ORDER BY total_berat DESC
        """, (start, end))
        grafik_data = cursor.fetchall()

        # Summary langsung dari tabel transaksi (bukan dari harga)
        cursor.execute("""
            SELECT petani, sayur, grade,
                   SUM(weight) AS total_berat,
                   MAX(harga_per_kg) AS harga_per_kg,
                   SUM(total_harga) AS total_harga
            FROM transaksi
            WHERE DATE(timestamp) BETWEEN %s AND %s
            GROUP BY petani, sayur, grade
        """, (start, end))
        summary_rows = cursor.fetchall()

    # Proses summary
    summary_data = {}
    for row in summary_rows:
        petani = row['petani']
        summary_data.setdefault(petani, []).append({
            'sayur': row['sayur'],
            'grade': row['grade'],
            'total_berat': float(row['total_berat']),
            'harga_per_kg': float(row['harga_per_kg']) if row['harga_per_kg'] else 0,
            'total_harga': float(row['total_harga']) if row['total_harga'] else 0
        })

    # Proses tren
    if range_type == 'mingguan':
        group_by = "DATE_FORMAT(timestamp, '%%Y-%%u')"  # Minggu ke-X tahun
    elif range_type == 'bulanan':
        group_by = "DATE_FORMAT(timestamp, '%%Y-%%m')"  # Bulan
    else:
        group_by = "DATE(timestamp)"  # Harian

    # Query tren per petani
    query = f"""
        SELECT {group_by} AS label, petani, SUM(weight) AS total_berat
        FROM transaksi
        WHERE timestamp BETWEEN %s AND %s
        GROUP BY label, petani
        ORDER BY label, petani
    """

    with db.cursor(dictionary=True) as cursor:
        cursor.execute(query, (start, end))
        rows = cursor.fetchall()

    # Proses tren multi-line per petani
    labels = sorted(list(set(row["label"] for row in rows)))
    petani_map = defaultdict(lambda: {label: 0 for label in labels})

    for row in rows:
        petani_map[row["petani"]][row["label"]] += float(row["total_berat"])

    # Warna untuk garis-garis tren
    colors = [
        "#36A2EB", "#FF6384", "#FFCE56", "#4BC0C0",
        "#9966FF", "#FF9F40", "#8B0000", "#228B22"
    ]

    datasets = []
    for i, (petani, data) in enumerate(petani_map.items()):
        # Ambil detail sayur dan grade per petani
        sayur_grade_list = summary_data.get(petani, [])
        detail = [
            f"{item['sayur']} ({item['grade']}): {item['total_berat']:.2f} kg"
            for item in sayur_grade_list
        ]

        datasets.append({
            "label": petani,
            "data": [data[label] for label in labels],
            "borderColor": colors[i % len(colors)],
            "fill": False,
            "tension": 0.3,
            "extraInfo": detail,  # ⬅️ kirim array string
        })

    tren_data = {
        "labels": labels,
        "datasets": datasets
    }

    return jsonify({
        "grafik": grafik_data,
        "summary": summary_data,
        "tren": tren_data
    })

# Endpoint untuk dashboard
@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/nota')
def nota_page():
    cursor = db.cursor(dictionary=True)

    # Ambil filter tanggal dan petani
    tanggal = request.args.get('tanggal')
    if not tanggal:
        tanggal = datetime.today().strftime('%Y-%m-%d')

    petani_filter = request.args.get('petani')

    # Query dasar
    query = """
        SELECT petani, sayur, grade, SUM(weight) AS total_berat,  
               harga_per_kg, SUM(COALESCE(total_harga, 0)) AS total_uang
        FROM transaksi
        WHERE DATE(timestamp) = %s
    """
    params = [tanggal]

    # Tambah filter petani kalau ada
    if petani_filter:
        query += " AND petani = %s"
        params.append(petani_filter)

    query += " GROUP BY petani, sayur, grade, harga_per_kg ORDER BY petani, sayur, grade"

    cursor.execute(query, params)
    data = cursor.fetchall()

    # Ambil semua nama petani untuk dropdown
    cursor.execute("SELECT DISTINCT petani FROM transaksi")
    semua_petani = [row['petani'] for row in cursor.fetchall()]

    cursor.close()

    # Kelompokkan per petani
    from collections import defaultdict
    hasil = defaultdict(list)
    for row in data:
        hasil[row['petani']].append(row)

    return render_template('nota.html', data=hasil, tanggal=tanggal, semua_petani=semua_petani, petani_filter=petani_filter)


@app.route('/manage')
def manage_data():
    with db.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT * FROM petani")
        petani = cursor.fetchall()
        cursor.execute("SELECT * FROM sayur")
        sayur = cursor.fetchall()
        cursor.execute("SELECT * FROM grade")
        grade = cursor.fetchall()
    return render_template('manage.html', petani=petani, sayur=sayur, grade=grade)

@app.route('/add/<table>', methods=['GET', 'POST'])
def add_data(table):
    if request.method == 'POST':
        value = request.form.get(f'nama_{table}' if table != 'grade' else 'grade')
        with db.cursor() as cursor:
            if table == 'petani':
                cursor.execute("INSERT INTO petani (nama_petani) VALUES (%s)", (value,))
            elif table == 'sayur':
                # 1. Tambahkan sayur baru
                cursor.execute("INSERT INTO sayur (nama_sayur) VALUES (%s)", (value,))
                sayur_id = cursor.lastrowid  # ambil ID sayur yang baru ditambahkan

                # 2. Ambil semua grade
                cursor.execute("SELECT grade FROM grade")
                grades = cursor.fetchall()

                # 3. Tambahkan ke tabel harga dengan harga default
                for g in grades:
                    grade = g[0] if isinstance(g, tuple) else g["grade"]
                    cursor.execute("""
                        INSERT INTO harga (sayur, grade, harga_per_kg, harga_jual)
                        VALUES (%s, %s, %s, %s)
                    """, (value, grade, 0, 0))  # harga default

            elif table == 'grade':
                cursor.execute("INSERT INTO grade (grade) VALUES (%s)", (value,))
            db.commit()
        return redirect(url_for('manage_data'))
    return render_template('add_form.html', table=table)


@app.route('/edit/<table>/<int:id>', methods=['GET', 'POST'])
def edit_data(table, id):
    if request.method == 'POST':
        value = request.form.get(f'nama_{table}' if table != 'grade' else 'grade')
        with db.cursor() as cursor:
            if table == 'petani':
                cursor.execute("UPDATE petani SET nama_petani=%s WHERE id=%s", (value, id))
            elif table == 'sayur':
                cursor.execute("UPDATE sayur SET nama_sayur=%s WHERE id=%s", (value, id))
            elif table == 'grade':
                cursor.execute("UPDATE grade SET grade=%s WHERE id=%s", (value, id))
            db.commit()
        return redirect(url_for('manage_data'))
    with db.cursor(dictionary=True) as cursor:
        cursor.execute(f"SELECT * FROM {table} WHERE id=%s", (id,))
        row = cursor.fetchone()
    return render_template('edit_form.html', table=table, row=row)

@app.route('/delete/<table>/<int:id>')
def delete_data(table, id):
    with db.cursor() as cursor:
        cursor.execute(f"DELETE FROM {table} WHERE id=%s", (id,))
        db.commit()
    return redirect(url_for('manage_data'))

# Tampilkan halaman harga
@app.route('/harga')
def halaman_harga():
    with db.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT * FROM harga ORDER BY sayur, grade")
        harga_list = cursor.fetchall()
    return render_template("harga.html", harga_list=harga_list)

# Update harga per kg
@app.route('/update-harga', methods=['POST'])
def update_harga():
    sayur = request.form['sayur']
    grade = request.form['grade']
    harga_per_kg = request.form['harga_per_kg']
    harga_jual = request.form['harga_jual']

    with db.cursor() as cursor:
        query = "UPDATE harga SET harga_per_kg = %s, harga_jual = %s WHERE sayur = %s AND grade = %s"
        cursor.execute(query, (harga_per_kg, harga_jual, sayur, grade))
        db.commit()

    return redirect(url_for('halaman_harga'))

@app.route("/keuangan")
def keuangan():
    cursor = db.cursor(dictionary=True)

    # Tanggal hari ini (format: YYYY-MM-DD)
    today = datetime.now().strftime('%Y-%m-%d')

    # Ambil parameter filter dari query string, default ke hari ini
    start = request.args.get("start") or today
    end = request.args.get("end") or today
    petani = request.args.get("petani")
    sayur = request.args.get("sayur")
    grade = request.args.get("grade")

    # Query dasar
    query = """
        SELECT 
            t.timestamp, 
            t.petani, 
            t.sayur, 
            t.grade, 
            t.weight, 
            t.harga_per_kg, 
            t.harga_jual, 
            t.total_harga AS uang_keluar,
            t.pendapatan, 
            t.keuntungan
        FROM transaksi t
        WHERE 1=1
    """
    params = []

    # Tambahkan filter ke query jika ada
    if start:
        query += " AND t.timestamp >= %s"
        params.append(start)
    if end:
        query += " AND t.timestamp <= %s"
        params.append(end + " 23:59:59")
    if petani:
        query += " AND t.petani = %s"
        params.append(petani)
    if sayur:
        query += " AND t.sayur = %s"
        params.append(sayur)
    if grade:
        query += " AND t.grade = %s"
        params.append(grade)

    query += " ORDER BY t.timestamp DESC"

    cursor.execute(query, params)
    hasil = cursor.fetchall()

    # Hitung total summary
    total_uang_keluar = sum(item["uang_keluar"] or 0 for item in hasil)
    total_pendapatan = sum(item["pendapatan"] or 0 for item in hasil)
    total_keuntungan = sum(item["keuntungan"] or 0 for item in hasil)

    # Ambil daftar unik petani, sayur, dan grade untuk filter select
    cursor.execute("SELECT DISTINCT petani FROM transaksi")
    daftar_petani = [row["petani"] for row in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT sayur FROM transaksi")
    daftar_sayur = [row["sayur"] for row in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT grade FROM transaksi")
    daftar_grade = [row["grade"] for row in cursor.fetchall()]

    cursor.close()

    return render_template("keuangan.html",
                           hasil=hasil,
                           total_uang_keluar=total_uang_keluar,
                           total_pendapatan=total_pendapatan,
                           total_keuntungan=total_keuntungan,
                           daftar_petani=daftar_petani,
                           daftar_sayur=daftar_sayur,
                           daftar_grade=daftar_grade,
                           start=start,
                           end=end,
                           petani=petani,
                           sayur=sayur,
                           grade=grade)


# Jalankan Flask app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)


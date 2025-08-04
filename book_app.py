import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from functools import wraps

# Flask uygulaması ve yapılandırma
app = Flask(__name__)
app.secret_key = 'gizli_anahtar'

# Yükleme klasörü ve izin verilen dosya uzantıları
app.config['UPLOAD_FOLDER'] = 'static/resimler'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# MySQL veritabanı yapılandırması
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Mehmet1905'
app.config['MYSQL_DB'] = 'kutuphane'

# Veritabanı bağlantısı
db = mysql.connector.connect(
    host=app.config['MYSQL_HOST'],
    user=app.config['MYSQL_USER'],
    password=app.config['MYSQL_PASSWORD'],
    database=app.config['MYSQL_DB']
)
cursor = db.cursor(dictionary=True)

# Kullanıcı oturumu kontrolü için decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Bu işlemi yapmak için giriş yapmalısınız.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Dosya uzantısı kontrolü
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    cursor.execute("SELECT * FROM kitaplar")
    kitaplar = cursor.fetchall()
    return render_template("index.html", kitaplar=kitaplar)

@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        ad = request.form.get('ad')
        soyad = request.form.get('soyad')
        email = request.form.get('email')
        sifre = request.form.get('sifre')

        hashed_password = generate_password_hash(sifre)

        cursor.execute("INSERT INTO kullanicilar (ad, soyad, email, sifre) VALUES (%s, %s, %s, %s)",
                       (ad, soyad, email, hashed_password))
        db.commit()
        flash("Kayıt başarılı. Giriş yapabilirsiniz.", "success")
        return redirect(url_for('login'))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        sifre = request.form.get("sifre")

        cursor.execute("SELECT * FROM kullanicilar WHERE email = %s", (email,))
        kullanici = cursor.fetchone()

        if kullanici and check_password_hash(kullanici['sifre'], sifre):
            session['user_id'] = kullanici['id']
            session['user_ad'] = kullanici['ad']
            flash("Giriş başarılı!", "success")
            return redirect(url_for("index"))
        else:
            flash("E-posta veya şifre hatalı!", "danger")

    return render_template("login.html")

@app.route('/logout')
def logout():
    session.clear()
    flash("Çıkış yapıldı.", "info")
    return redirect(url_for('index'))

@app.route('/kitap_islem', methods=["GET", "POST"])
@login_required
def kitap_islem():
    if request.method == "POST":
        if 'ekle' in request.form:
            ad = request.form['ad']
            yazar = request.form['yazar']
            baski_yili = request.form['baski_yili']
            resim_dosyasi = request.files.get('resim')

            dosya_adi = 'default.jpeg'
            if resim_dosyasi and allowed_file(resim_dosyasi.filename):
                dosya_adi = str(uuid.uuid4()) + os.path.splitext(resim_dosyasi.filename)[1]
                resim_dosyasi.save(os.path.join(app.config['UPLOAD_FOLDER'], dosya_adi))

            cursor.execute("INSERT INTO kitaplar (ad, yazar, baski_yili, resim) VALUES (%s, %s, %s, %s)",
                           (ad, yazar, baski_yili, dosya_adi))
            db.commit()
            flash("Kitap eklendi.", "success")

        elif 'sil' in request.form:
            kitap_id = request.form.get('sil_kitap_id')
            cursor.execute("SELECT resim FROM kitaplar WHERE id = %s", (kitap_id,))
            kitap = cursor.fetchone()

            if kitap:
                if kitap['resim'] and kitap['resim'] != 'default.jpeg':
                    resim_path = os.path.join(app.config['UPLOAD_FOLDER'], kitap['resim'])
                    if os.path.exists(resim_path):
                        os.remove(resim_path)
                cursor.execute("DELETE FROM odunc WHERE kitap_id = %s", (kitap_id,))
                cursor.execute("DELETE FROM kitaplar WHERE id = %s", (kitap_id,))
                db.commit()
                flash("Kitap silindi.", "success")

        elif 'guncelle' in request.form:
            kitap_id = request.form.get('guncelle_kitap_id')
            yeni_ad = request.form['yeni_ad']
            yeni_yazar = request.form['yeni_yazar']
            yeni_yil = request.form['yeni_yil']
            yeni_resim = request.files.get('yeni_resim')

            cursor.execute("UPDATE kitaplar SET ad=%s, yazar=%s, baski_yili=%s WHERE id=%s",
                           (yeni_ad, yeni_yazar, yeni_yil, kitap_id))

            if yeni_resim and allowed_file(yeni_resim.filename):
                cursor.execute("SELECT resim FROM kitaplar WHERE id=%s", (kitap_id,))
                eski = cursor.fetchone()
                if eski and eski['resim'] != 'default.jpeg':
                    eski_path = os.path.join(app.config['UPLOAD_FOLDER'], eski['resim'])
                    if os.path.exists(eski_path):
                        os.remove(eski_path)

                yeni_dosya = str(uuid.uuid4()) + os.path.splitext(yeni_resim.filename)[1]
                yeni_resim.save(os.path.join(app.config['UPLOAD_FOLDER'], yeni_dosya))
                cursor.execute("UPDATE kitaplar SET resim=%s WHERE id=%s", (yeni_dosya, kitap_id))

            db.commit()
            flash("Kitap bilgileri güncellendi.", "info")

    cursor.execute("SELECT * FROM kitaplar")
    kitaplar = cursor.fetchall()
    return render_template("kitap_islem.html", kitaplar=kitaplar)

@app.route('/odunc', methods=["GET", "POST"])
@login_required
def odunc():
    cursor.execute("SELECT * FROM kitaplar WHERE mevcut = TRUE")
    kitaplar = cursor.fetchall()
    cursor.execute("""SELECT o.id as odunc_id, k.ad as kitap_ad 
                      FROM odunc o JOIN kitaplar k ON o.kitap_id = k.id 
                      WHERE o.kullanici_id = %s AND o.teslim_edildi = FALSE""", (session['user_id'],))
    oduncler = cursor.fetchall()

    if request.method == "POST":
        if 'al' in request.form:
            kitap_id = request.form['kitap_id']
            cursor.execute("INSERT INTO odunc (kullanici_id, kitap_id) VALUES (%s, %s)", (session['user_id'], kitap_id))
            cursor.execute("UPDATE kitaplar SET mevcut = FALSE WHERE id = %s", (kitap_id,))
            db.commit()
            flash("Kitap ödünç alındı.", "success")

        elif 'teslim' in request.form:
            odunc_id = request.form['odunc_id']
            cursor.execute("UPDATE odunc SET teslim_edildi = TRUE WHERE id = %s", (odunc_id,))
            cursor.execute("UPDATE kitaplar SET mevcut = TRUE WHERE id = (SELECT kitap_id FROM odunc WHERE id = %s)", (odunc_id,))
            db.commit()
            flash("Kitap iade edildi.", "info")

        return redirect(url_for('odunc'))

    return render_template("odunc.html", kitaplar=kitaplar, oduncler=oduncler)

@app.route('/hesabim', methods=["GET", "POST"])
@login_required
def hesabim():
    if request.method == "POST":
        if 'guncelle' in request.form:
            ad = request.form['ad']
            email = request.form['email']
            cursor.execute("UPDATE kullanicilar SET ad = %s, email = %s WHERE id = %s",
                           (ad, email, session['user_id']))
            db.commit()
            session['user_ad'] = ad
            flash("Bilgiler güncellendi.", "success")

        elif 'sifre' in request.form:
            mevcut_sifre = request.form['mevcut_sifre']
            yeni_sifre = request.form['yeni_sifre']

            cursor.execute("SELECT sifre FROM kullanicilar WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()

            if user and check_password_hash(user['sifre'], mevcut_sifre):
                yeni_hash = generate_password_hash(yeni_sifre)
                cursor.execute("UPDATE kullanicilar SET sifre = %s WHERE id = %s", (yeni_hash, session['user_id']))
                db.commit()
                flash("Şifre başarıyla değiştirildi.", "info")
            else:
                flash("Mevcut şifre yanlış!", "danger")

        elif 'sil' in request.form:
            cursor.execute("DELETE FROM kullanicilar WHERE id = %s", (session['user_id'],))
            db.commit()
            session.clear()
            flash("Hesabınız silindi.", "danger")
            return redirect(url_for('index'))

    cursor.execute("SELECT * FROM kullanicilar WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    return render_template("hesabim.html", user=user)

if __name__ == '__main__':
    app.run(debug=True)

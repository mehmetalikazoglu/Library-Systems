import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from functools import wraps

# Flask ayarları
app = Flask(__name__)
app.secret_key = 'gizli_anahtar'

# Dosya yükleme ayarları
app.config['UPLOAD_FOLDER'] = 'static/resimler'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# MySQL ayarları
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Mehmet1905'
app.config['MYSQL_DB'] = 'kutuphane'


# Veritabanı bağlantısı
def get_db():
    if 'db' not in g:
        g.db = mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB']
        )
    return g.db

def get_cursor():
    if 'cursor' not in g:
        g.cursor = get_db().cursor(dictionary=True)
    return g.cursor

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()


# Kullanıcı giriş kontrolü (login_required)
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


# Kullanıcı bilgilerini her şablona aktarma
@app.before_request
def load_logged_in_user():
    g.user = None
    if "user_id" in session:
        cursor = get_cursor()
        cursor.execute("SELECT * FROM kullanicilar WHERE id=%s", (session['user_id'],))
        g.user = cursor.fetchone()

# Tüm html sayfalarına user bilgisini aktarma
@app.context_processor
def inject_user():
    return dict(user=g.user)


# Anasayfa
@app.route('/')
def index():
    cursor = get_cursor()
    cursor.execute("SELECT * FROM kitaplar")
    kitaplar = cursor.fetchall()
    return render_template("index.html", kitaplar=kitaplar)


# Kayıt ol
@app.route('/register', methods=["GET", "POST"])
def register():
    cursor = get_cursor()
    db = get_db()

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


# Kullanıcı giriş
@app.route("/login", methods=["GET", "POST"])
def login():
    cursor = get_cursor()
    if request.method == "POST":
        email = request.form.get("email")
        sifre = request.form.get("sifre")

        cursor.execute("SELECT * FROM kullanicilar WHERE email = %s", (email,))
        kullanici = cursor.fetchone()

        if kullanici and check_password_hash(kullanici['sifre'], sifre):
            session['user_id'] = kullanici['id']
            session['user_ad'] = kullanici['ad']
            session['profil_resmi'] = kullanici.get('profil_resmi')  # profil resmi session’a yaz
            flash("Giriş başarılı!", "success")
            return redirect(url_for("index"))
        else:
            flash("E-posta veya şifre hatalı!", "danger")

    return render_template("login.html")


# Kullanıcı çıkış
@app.route('/logout')
def logout():
    session.clear()
    flash("Çıkış yapıldı.", "info")
    return redirect(url_for('index'))


# Kitap işlemleri
@app.route('/kitap_islem', methods=["GET", "POST"])
@login_required
def kitap_islem():
    cursor = get_cursor()
    db = get_db()

    if request.method == "POST":
        if 'ekle' in request.form:
            ad = request.form['ad']
            yazar = request.form['yazar']
            baski_yili = request.form['baski_yili']
            kitap_ozet = request.form.get('kitap_ozet') or None
            resim_dosyasi = request.files.get('resim')

            dosya_adi = 'default.jpeg'
            if resim_dosyasi and allowed_file(resim_dosyasi.filename):
                dosya_adi = str(uuid.uuid4()) + os.path.splitext(resim_dosyasi.filename)[1]
                resim_yolu = os.path.join(app.config['UPLOAD_FOLDER'], dosya_adi)
                resim_dosyasi.save(resim_yolu)

            cursor.execute(
                "INSERT INTO kitaplar (ad, yazar, baski_yili, resim, kitap_ozet) VALUES (%s, %s, %s, %s, %s)",
                (ad, yazar, baski_yili, dosya_adi, kitap_ozet)
            )
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
            yeni_ad = request.form.get('yeni_ad')
            yeni_yazar = request.form.get('yeni_yazar')
            yeni_yil = request.form.get('yeni_yil')
            yeni_ozet = request.form.get('yeni_ozet')
            yeni_resim = request.files.get('yeni_resim')

            # Mevcut kitap bilgilerini al
            cursor.execute("SELECT * FROM kitaplar WHERE id=%s", (kitap_id,))
            eski_kitap = cursor.fetchone()

            fields = []
            values = []

            if yeni_ad:
                fields.append("ad=%s")
                values.append(yeni_ad)
            if yeni_yazar:
                fields.append("yazar=%s")
                values.append(yeni_yazar)
            if yeni_yil:
                fields.append("baski_yili=%s")
                values.append(yeni_yil)
            if yeni_ozet:
                fields.append("kitap_ozet=%s")
                values.append(yeni_ozet)
            elif yeni_ozet is None:
                # Özet boş bırakıldıysa eski değer korunur
                pass

            if yeni_resim and allowed_file(yeni_resim.filename):
                # Eski resmi sil
                if eski_kitap['resim'] and eski_kitap['resim'] != 'default.jpeg':
                    eski_path = os.path.join(app.config['UPLOAD_FOLDER'], eski_kitap['resim'])
                    if os.path.exists(eski_path):
                        os.remove(eski_path)
                yeni_dosya = str(uuid.uuid4()) + os.path.splitext(yeni_resim.filename)[1]
                yeni_resim.save(os.path.join(app.config['UPLOAD_FOLDER'], yeni_dosya))
                fields.append("resim=%s")
                values.append(yeni_dosya)

            if fields:
                values.append(kitap_id)
                sql = f"UPDATE kitaplar SET {', '.join(fields)} WHERE id=%s"
                cursor.execute(sql, values)
                db.commit()
                flash("Kitap bilgileri güncellendi.", "info")


    cursor.execute("SELECT * FROM kitaplar")
    kitaplar = cursor.fetchall()
    return render_template("kitap_islem.html", kitaplar=kitaplar)


# Ödünç kitap
@app.route('/odunc', methods=["GET", "POST"])
@login_required
def odunc():
    cursor = get_cursor()
    db = get_db()

    cursor.execute("SELECT * FROM kitaplar WHERE mevcut = TRUE")
    kitaplar = cursor.fetchall()
    cursor.execute("""SELECT o.id as odunc_id, k.ad as kitap_ad 
                      FROM odunc o JOIN kitaplar k ON o.kitap_id = k.id 
                      WHERE o.kullanici_id = %s AND o.teslim_edildi = FALSE""", (session['user_id'],))
    oduncler = cursor.fetchall()

    if request.method == "POST":
        if 'al' in request.form:
            kitap_id = request.form.get('kitap_id')

            if not kitap_id:
                flash("Lütfen bir kitap seçin.", "warning")
                return redirect(url_for('odunc'))

            cursor.execute("INSERT INTO odunc (kullanici_id, kitap_id) VALUES (%s, %s)", 
                           (session['user_id'], kitap_id))
            cursor.execute("UPDATE kitaplar SET mevcut = FALSE WHERE id = %s", (kitap_id,))
            db.commit()
            flash("Kitap ödünç alındı.", "success")

        elif 'teslim' in request.form:
            odunc_id = request.form.get('odunc_id')

            if not odunc_id:
                flash("Lütfen iade edilecek kitabı seçin.", "warning")
                return redirect(url_for('odunc'))

            cursor.execute("UPDATE odunc SET teslim_edildi = TRUE WHERE id = %s", (odunc_id,))
            cursor.execute("UPDATE kitaplar SET mevcut = TRUE WHERE id = (SELECT kitap_id FROM odunc WHERE id = %s)", 
                           (odunc_id,))
            db.commit()
            flash("Kitap iade edildi.", "info")

        return redirect(url_for('odunc', tab='odunc'))

    return render_template("odunc.html", kitaplar=kitaplar, oduncler=oduncler)


# Hesap / profil ayarları
PROFILE_UPLOAD_FOLDER = os.path.join('static', 'profil_fotograflari')
os.makedirs(PROFILE_UPLOAD_FOLDER, exist_ok=True)
app.config['PROFILE_UPLOAD_FOLDER'] = PROFILE_UPLOAD_FOLDER

def allowed_profile_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/hesabim', methods=["GET", "POST"])
@login_required
def hesabim():
    cursor = get_cursor()
    db = get_db()

    cursor.execute("SELECT * FROM kullanicilar WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()

    if request.method == "POST":

        # Kullanıcı bilgilerini güncelle
        if 'guncelle' in request.form:
            ad = request.form.get('ad', user['ad'])
            soyad = request.form.get('soyad', user['soyad'])
            email = request.form.get('email', user['email'])

            # Profil fotoğrafını kaldır
            if request.form.get('resim_kaldir'):
                if user['profil_resmi']:
                    eski_yol = os.path.join(app.config['PROFILE_UPLOAD_FOLDER'], user['profil_resmi'])
                    if os.path.exists(eski_yol):
                        os.remove(eski_yol)
                cursor.execute("UPDATE kullanicilar SET profil_resmi=NULL WHERE id=%s", (session['user_id'],))
                session['profil_resmi'] = None
                flash("Profil fotoğrafı kaldırıldı.", "success")

            # Yeni profil resmi yükle
            dosya = request.files.get('profil_resmi')
            if dosya and dosya.filename and allowed_profile_file(dosya.filename):
                _, ext = os.path.splitext(secure_filename(dosya.filename))
                yeni_dosya = f"{uuid.uuid4().hex}{ext.lower()}"
                hedef_yol = os.path.join(app.config['PROFILE_UPLOAD_FOLDER'], yeni_dosya)
                dosya.save(hedef_yol)

                if user['profil_resmi']:
                    eski_yol = os.path.join(app.config['PROFILE_UPLOAD_FOLDER'], user['profil_resmi'])
                    if os.path.exists(eski_yol):
                        os.remove(eski_yol)

                cursor.execute("UPDATE kullanicilar SET profil_resmi=%s WHERE id=%s",
                               (yeni_dosya, session['user_id']))
                session['profil_resmi'] = yeni_dosya
                flash("Profil fotoğrafı güncellendi.", "success")

            # Ad, soyad, email güncelle
            cursor.execute("UPDATE kullanicilar SET ad=%s, soyad=%s, email=%s WHERE id=%s",
                           (ad, soyad, email, session['user_id']))
            db.commit()
            flash("Bilgiler başarıyla güncellendi.", "success")

        # Şifre değiştir
        elif 'sifre' in request.form:
            mevcut_sifre = request.form.get('mevcut_sifre')
            yeni_sifre = request.form.get('yeni_sifre')

            if mevcut_sifre and yeni_sifre and check_password_hash(user['sifre'], mevcut_sifre):
                cursor.execute("UPDATE kullanicilar SET sifre=%s WHERE id=%s",
                               (generate_password_hash(yeni_sifre), session['user_id']))
                db.commit()
                flash("Şifre başarıyla güncellendi.", "success")
            else:
                flash("Mevcut şifre yanlış!", "danger")

        # Hesap sil
        elif 'sil' in request.form:
            cursor.execute("SELECT COUNT(*) as sayi FROM odunc WHERE kullanici_id=%s AND teslim_edildi=0", 
                           (session['user_id'],))
            odunc = cursor.fetchone()

            if odunc and odunc['sayi'] > 0:
                flash("Ödünç alınan kitaplar iade edilmeden hesap silinemez!", "danger")
            else:
                if user['profil_resmi']:
                    eski_yol = os.path.join(app.config['PROFILE_UPLOAD_FOLDER'], user['profil_resmi'])
                    if os.path.exists(eski_yol):
                        os.remove(eski_yol)

                cursor.execute("DELETE FROM kullanicilar WHERE id=%s", (session['user_id'],))
                db.commit()
                session.clear()
                flash("Hesabınız silindi.", "info")
                return redirect(url_for('index'))

        cursor.execute("SELECT * FROM kullanicilar WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()

    return render_template("hesabim.html", user=user)


if __name__ == '__main__':
    app.run(debug=True)

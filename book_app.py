import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from functools import wraps
from flask import g

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

def get_db():
    if 'db' not in g:
        g.db = mysql.connector.connect(
            host='localhost',
            user='root',
            password='Mehmet1905',
            database='kutuphane'
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

@app.before_request
def load_logged_in_user():
    cursor = get_cursor()
    if 'user_id' in session:
        cursor.execute("SELECT * FROM kullanicilar WHERE id = %s", (session['user_id'],))
        g.user = cursor.fetchone()
    else:
        g.user = None


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
            kitap_id = request.form.get('kitap_id')

            if not kitap_id:  # Kitap seçilmemişse
                flash("Lütfen bir kitap seçin.", "warning")
                return redirect(url_for('odunc'))

            cursor.execute("INSERT INTO odunc (kullanici_id, kitap_id) VALUES (%s, %s)", 
                           (session['user_id'], kitap_id))
            cursor.execute("UPDATE kitaplar SET mevcut = FALSE WHERE id = %s", (kitap_id,))
            db.commit()
            flash("Kitap ödünç alındı.", "success")

        elif 'teslim' in request.form:
            odunc_id = request.form.get('odunc_id')

            if not odunc_id:  # İade için kitap seçilmemişse
                flash("Lütfen iade edilecek kitabı seçin.", "warning")
                return redirect(url_for('odunc'))

            cursor.execute("UPDATE odunc SET teslim_edildi = TRUE WHERE id = %s", (odunc_id,))
            cursor.execute("UPDATE kitaplar SET mevcut = TRUE WHERE id = (SELECT kitap_id FROM odunc WHERE id = %s)", 
                           (odunc_id,))
            db.commit()
            flash("Kitap iade edildi.", "info")

        return redirect(url_for('odunc'))

    return render_template("odunc.html", kitaplar=kitaplar, oduncler=oduncler)




UPLOAD_FOLDER = 'static/profil_fotograflari'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/hesabim', methods=["GET", "POST"])
@login_required
def hesabim():
    """
    Hesabım sayfası: profil resmi yükleme/kaldırma, kullanıcı bilgileri güncelleme,
    şifre değiştirme ve hesap silme işlemlerini tek bir route üzerinden yönetir.
    - Dosyalar 'static/profil_fotograflari/' içine kaydedilir.
    - Yükleme sonrası session['profil_resmi'] güncellenir (navbar için).
    - Varsayılan görsel: 'defaultprofil.jpg' (profil_fotograflari klasöründe).
    """
    cursor = get_cursor()

    # 1) Mevcut kullanıcı bilgilerini çek (user her zaman tanımlı olur)
    cursor.execute("SELECT * FROM kullanicilar WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()

    # Güvence: eğer veritabanında profil_resmi boşsa local user dict'ine default atıyoruz
    if not user.get('profil_resmi'):
        user['profil_resmi'] = 'defaultprofil.jpg'
        session['profil_resmi'] = 'defaultprofil.jpg'
    else:
        # session'da da senkron tut
        session['profil_resmi'] = user['profil_resmi']

    if request.method == "POST":
        # ----- 1) Dosya yükleme (öncelik: yeni dosya yüklendiyse bu yapılır) -----
        dosya = request.files.get('profil_resmi')
        if dosya and dosya.filename:
            # izinli uzantı kontrolü (allowed_file fonksiyonunu proje genelinden kullanıyoruz)
            if allowed_file(dosya.filename):
                # hedef klasör
                hedef_klasor = os.path.join(app.root_path, 'static', 'profil_fotograflari')
                os.makedirs(hedef_klasor, exist_ok=True)

                # benzersiz dosya adı (uuid ile) -> cache & çakışma önleme
                _, ext = os.path.splitext(secure_filename(dosya.filename))
                yeni_dosya_adi = f"{uuid.uuid4().hex}{ext.lower()}"
                hedef_yol = os.path.join(hedef_klasor, yeni_dosya_adi)

                # dosyayı kaydet
                dosya.save(hedef_yol)

                # eski dosyayı sil (default değilse)
                if user.get('profil_resmi') and user['profil_resmi'] != 'defaultprofil.jpg':
                    eski_yol = os.path.join(hedef_klasor, user['profil_resmi'])
                    if os.path.exists(eski_yol):
                        try:
                            os.remove(eski_yol)
                        except OSError:
                            pass

                # veritabanına yaz ve session güncelle
                cursor.execute("UPDATE kullanicilar SET profil_resmi = %s WHERE id = %s",
                               (yeni_dosya_adi, session['user_id']))
                db.commit()
                session['profil_resmi'] = yeni_dosya_adi
                flash("Profil fotoğrafı güncellendi.", "success")

                # kullanıcı verisini güncelle (sayfaya yansısın)
                cursor.execute("SELECT * FROM kullanicilar WHERE id = %s", (session['user_id'],))
                user = cursor.fetchone()

            else:
                flash("Yalnızca png/jpg/jpeg/gif uzantılı dosyalar yüklenebilir.", "warning")

        # ----- 2) Fotoğraf kaldırma (sadece yeni dosya yüklenmediyse çalışır veya kullanıcı ayrı olarak kaldırdı) -----
        # Eğer kullanıcı 'resim_kaldir' işaretlediyse ve şu anda yüklü resim default değilse sil
        if 'resim_kaldir' in request.form and (not (dosya and dosya.filename)):
            if user.get('profil_resmi') and user['profil_resmi'] != 'defaultprofil.jpg':
                hedef_klasor = os.path.join(app.root_path, 'static', 'profil_fotograflari')
                eski_yol = os.path.join(hedef_klasor, user['profil_resmi'])
                if os.path.exists(eski_yol):
                    try:
                        os.remove(eski_yol)
                    except OSError:
                        pass

            # veritabanına default at
            cursor.execute("UPDATE kullanicilar SET profil_resmi = %s WHERE id = %s",
                           ('defaultprofil.jpg', session['user_id']))
            db.commit()
            session['profil_resmi'] = 'defaultprofil.jpg'
            flash("Profil fotoğrafı kaldırıldı.", "info")

            # kullanıcı verisini güncelle (sayfaya yansısın)
            cursor.execute("SELECT * FROM kullanicilar WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()

        # ----- 3) Kişisel bilgi güncelleme (ad, soyad, email) -----
        if 'guncelle' in request.form:
            ad = request.form.get('ad')
            soyad = request.form.get('soyad')
            email = request.form.get('email')

            # Basit doğrulama
            if ad and soyad and email:
                cursor.execute("UPDATE kullanicilar SET ad = %s, soyad = %s, email = %s WHERE id = %s",
                               (ad, soyad, email, session['user_id']))
                db.commit()
                session['user_ad'] = ad
                flash("Bilgiler güncellendi.", "success")
            else:
                flash("Ad, soyad ve email boş olamaz.", "warning")

            cursor.execute("SELECT * FROM kullanicilar WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()

        # ----- 4) Şifre değişikliği -----
        if 'sifre' in request.form:
            mevcut_sifre = request.form.get('mevcut_sifre')
            yeni_sifre = request.form.get('yeni_sifre')

            cursor.execute("SELECT sifre FROM kullanicilar WHERE id = %s", (session['user_id'],))
            satir = cursor.fetchone()
            if satir and check_password_hash(satir['sifre'], mevcut_sifre):
                yeni_hash = generate_password_hash(yeni_sifre)
                cursor.execute("UPDATE kullanicilar SET sifre = %s WHERE id = %s", (yeni_hash, session['user_id']))
                db.commit()
                flash("Şifre başarıyla değiştirildi.", "info")
            else:
                flash("Mevcut şifre yanlış!", "danger")

        # ----- 5) Hesap silme -----
        if 'sil' in request.form:
            # eski resim varsa sil
            if user.get('profil_resmi') and user['profil_resmi'] != 'defaultprofil.jpg':
                hedef_klasor = os.path.join(app.root_path, 'static', 'profil_fotograflari')
                eski_yol = os.path.join(hedef_klasor, user['profil_resmi'])
                if os.path.exists(eski_yol):
                    try:
                        os.remove(eski_yol)
                    except OSError:
                        pass

            cursor.execute("DELETE FROM kullanicilar WHERE id = %s", (session['user_id'],))
            db.commit()
            session.clear()
            flash("Hesabınız silindi.", "danger")
            return redirect(url_for('index'))

    # Render öncesi kesin güncel kullanıcı bilgisi
    cursor.execute("SELECT * FROM kullanicilar WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    # Güvence: eğer None veya boşsa default at
    if not user.get('profil_resmi'):
        user['profil_resmi'] = 'defaultprofil.jpg'
        session['profil_resmi'] = 'defaultprofil.jpg'
    else:
        session['profil_resmi'] = user['profil_resmi']

    return render_template("hesabim.html", user=user)

if __name__ == '__main__':
    app.run(debug=True)

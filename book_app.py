from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector

app = Flask(__name__)
app.secret_key = 'gizli_anahtar'

# Veritabanı bağlantısı
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Mehmet1905",
    database="kutuphane"
)
cursor = db.cursor(dictionary=True)

# Giriş kontrolü için decorator
def login_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash("Bu işlemi yapmak için giriş yapmalısınız.", "danger")
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return wrapper

@app.route('/')
def index():
    cursor.execute("SELECT * FROM kitaplar")
    kitaplar = cursor.fetchall()
    return render_template("index.html", kitaplar=kitaplar)

@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        ad = request.form['ad']
        soyad = request.form['soyad']
        email = request.form['email']
        sifre = generate_password_hash(request.form['sifre'])
        cursor.execute("INSERT INTO kullanicilar (ad, soyad, email, sifre) VALUES (%s, %s, %s, %s)",
                       (ad, soyad, email, sifre))
        db.commit()
        flash("Kayıt başarılı. Giriş yapabilirsiniz.", "success")
        return redirect(url_for('login'))
    return render_template("register.html")

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form['email']
        sifre = request.form['sifre']
        cursor.execute("SELECT * FROM kullanicilar WHERE email = %s", (email,))
        user = cursor.fetchone()
        if user and check_password_hash(user['sifre'], sifre):
            session['user_id'] = user['id']
            session['user_ad'] = user['ad']
            flash("Giriş başarılı.", "success")
            return redirect(url_for('index'))
        else:
            flash("Email veya şifre hatalı.", "danger")
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
            cursor.execute("INSERT INTO kitaplar (ad, yazar, baski_yili) VALUES (%s, %s, %s)",
                           (ad, yazar, baski_yili))
            db.commit()
            flash("Kitap eklendi.", "success")

        elif 'sil' in request.form:
            kitap_id = request.form.get('sil_kitap_id')
            cursor.execute("SELECT id FROM kitaplar WHERE id = %s", (kitap_id,))
            kitap = cursor.fetchone()

            if kitap:
                cursor.execute("DELETE FROM odunc WHERE kitap_id = %s", (kitap_id,))
                cursor.execute("DELETE FROM kitaplar WHERE id = %s", (kitap_id,))
                db.commit()
                flash("Kitap başarıyla silindi.", "success")
            else:
                flash("Seçilen kitap bulunamadı.", "warning")

        elif 'guncelle' in request.form:
            kitap_id = request.form.get('guncelle_kitap_id')
            yeni_ad = request.form['yeni_ad']
            yeni_yazar = request.form['yeni_yazar']
            yeni_yil = request.form['yeni_yil']

            cursor.execute(
                "UPDATE kitaplar SET ad = %s, yazar = %s, baski_yili = %s WHERE id = %s",
                (yeni_ad, yeni_yazar, yeni_yil, kitap_id)
            )
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

    cursor.execute("SELECT o.id as odunc_id, k.ad as kitap_ad FROM odunc o JOIN kitaplar k ON o.kitap_id = k.id WHERE o.kullanici_id = %s AND o.teslim_edildi = FALSE", (session['user_id'],))
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
            yeni = generate_password_hash(request.form['yeni_sifre'])
            cursor.execute("UPDATE kullanicilar SET sifre = %s WHERE id = %s", (yeni, session['user_id']))
            db.commit()
            flash("Şifre güncellendi.", "info")
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

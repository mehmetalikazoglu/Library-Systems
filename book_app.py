from flask import Flask, render_template, request, redirect, url_for
import mysql.connector

app = Flask(__name__)

# Veritabanı bağlantısı
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Mehmet1905",
    database="kutuphane"
)
cursor = db.cursor(dictionary=True)

# Anasayfa: Kitapları listele
@app.route('/')
def index():
    cursor.execute("SELECT * FROM kitaplar")
    kitaplar = cursor.fetchall()
    return render_template("index.html", kitaplar=kitaplar)

# Kullanıcı kayıt ekranı
@app.route('/kullanici', methods=["GET", "POST"])
def kullanici():
    if request.method == "POST":
        ad = request.form['ad']
        soyad = request.form['soyad']
        email = request.form['email']
        cursor.execute("INSERT INTO kullanicilar (ad, soyad, email) VALUES (%s, %s, %s)", (ad, soyad, email))
        db.commit()
        return redirect(url_for('index'))
    return render_template("kullanici.html")

# Kitap ekleme, silme, güncelleme
@app.route('/kitap_islem', methods=["GET", "POST"])
def kitap_islem():
    if request.method == "POST":
        if 'ekle' in request.form:
            ad = request.form['ad']
            yazar = request.form['yazar']
            baski_yili = request.form['baski_yili']
            cursor.execute("INSERT INTO kitaplar (ad, yazar, baski_yili) VALUES (%s, %s, %s)", (ad, yazar, baski_yili))
            db.commit()
        elif 'sil' in request.form:
            kitap_id = request.form['kitap_id']
            cursor.execute("DELETE FROM kitaplar WHERE id = %s", (kitap_id,))
            db.commit()
        elif 'guncelle' in request.form:
            kitap_id = request.form['kitap_id']
            yeni_ad = request.form['yeni_ad']
            cursor.execute("UPDATE kitaplar SET ad = %s WHERE id = %s", (yeni_ad, kitap_id))
            db.commit()
    cursor.execute("SELECT * FROM kitaplar")
    kitaplar = cursor.fetchall()
    return render_template("kitap_islem.html", kitaplar=kitaplar)

# Ödünç alma ve geri verme
@app.route('/odunc', methods=["GET", "POST"])
def odunc():
    cursor.execute("SELECT * FROM kullanicilar")
    kullanicilar = cursor.fetchall()
    cursor.execute("SELECT * FROM kitaplar WHERE mevcut = TRUE")
    kitaplar = cursor.fetchall()

    if request.method == "POST":
        kullanici_id = request.form['kullanici_id']
        kitap_id = request.form['kitap_id']
        cursor.execute("INSERT INTO odunc (kullanici_id, kitap_id) VALUES (%s, %s)", (kullanici_id, kitap_id))
        cursor.execute("UPDATE kitaplar SET mevcut = FALSE WHERE id = %s", (kitap_id,))
        db.commit()
        return redirect(url_for('index'))

    return render_template("odunc.html", kullanicilar=kullanicilar, kitaplar=kitaplar)

# Flask başlat
if __name__ == '__main__':
    app.run(debug=True)

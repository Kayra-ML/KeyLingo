# KeyLingo - macOS Global DeepL Çeviri Aracı

macOS üzerinde arka planda çalışan, herhangi bir uygulamada (Discord, Chrome, Safari, Telegram, VS Code, Notlar, ChatGPT vb.) yazı yazarken aktif text input içindeki metni global kısayollarla anında **Türkçe ↔ İngilizce** çeviren hafif Python aracı.

---

## 🎯 Özellikler

- **Global Erişim:** Aktif olan her metin kutusunda çalışır (Discord, Chrome, Safari, Slack, Telegram, ChatGPT, Claude, VS Code, Notes vb.).
- **Özel Hotkeyler (é Tuşu ile):**
  - `é + → (Sağ Ok)` : **Türkçe → İngilizce** (DeepL `EN-US`)
  - `é + ← (Sol Ok)` : **İngilizce → Türkçe** (DeepL `TR`)
- **Akıllı Tuş Bastırma (Key Suppression):** `é` bir modifier (Cmd/Alt/Ctrl) tuşu olmamasına rağmen, Quartz CGEventTap kullanılarak `é + Ok` basıldığında `é` karakterinin metin alanına yazılması engellenir.
- **Normal Yazımı Bozmaz:** Eğer kullanıcı sadece `é` tuşuna basıp bırakırsa veya ardından başka bir harfe basarsa, normal yazı akışı korunur (`é` karakteri yazılır).
- **Güvenlik Davranışı:**
  - İnternet kesintisi, API hatası, geçersiz anahtar veya timeout durumunda **kullanıcının orijinal metni ASLA silinmez**.
  - Aktif input boşsa hiçbir işlem yapılmaz.
  - API boş cevap dönerse metin değiştirilmez.
  - Hotkey art arda basılırsa duplicate API isteği oluşmaz (`lock` korumalıdır).
- **Pano (Clipboard) Koruma:** Kullanıcının çeviri öncesi panosunda bulunan veri geçici olarak saklanır ve yapıştırma bittikten sonra eski haline getirilir.
- **DeepL API Güvenliği:** API anahtarı hiçbir log veya konsol çıktısında görünmez (`[REDACTED_API_KEY]`).

---

## 🛠 Gereksinimler & macOS İzinleri

Bu aracın global klavye olaylarını dinleyebilmesi, kısayolları suppress edebilmesi ve metin seçebilmesi için **macOS Erişilebilirlik (Accessibility)** izni gereklidir.

### İzinleri Verme Adımları:
1. **Sistem Ayarları (System Settings)** uygulamasını açın.
2. **Gizlilik ve Güvenlik (Privacy & Security)** sekmesine gidin.
3. **Erişilebilirlik (Accessibility)** bölümüne tıklayın.
4. Terminal uygulamanızı (**Terminal**, **iTerm2** veya **Visual Studio Code**) listeye ekleyin ve yanındaki anahtarı **Açık (ON)** konuma getirin.
5. *(Gerekirse)* Aynı menü altındaki **Girdi İzleme (Input Monitoring)** bölümünde de terminalinizin izinli olduğundan emin olun.

---

## 🚀 Kurulum ve Çalıştırma

```bash
git clone https://github.com/Kayra-ML/KeyLingo.git
cd KeyLingo
```

### 1. Sanal Ortamı Oluşturun ve Paketleri Yükleyin:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. .env Dosyasını Oluşturun:
```bash
cp .env.example .env
```

`.env` dosyasını bir metin düzenleyiciyle açıp [DeepL API](https://www.deepl.com/pro-api) anahtarınızı ekleyin:

```env
DEEPL_AUTH_KEY=your_deepl_api_key_here
```

### 3. DeepL Bağlantısını Test Edin (Opsiyonel):
```bash
python main.py --test-api
```
Başarılı ise:
```text
Kaynak metin : Bu bir test cümlesidir.
[TR -> EN] Çevriliyor...
Çeviri sonucu: This is a test sentence.
[BAŞARILI] DeepL API bağlantısı sorunsuz çalışıyor!
```

### 4. Programı Başlatın:
```bash
python main.py
```

Başlatıldığında konsolda şu çıktıyı göreceksiniz:
```text
============================================================
  macOS Global Çeviri Aracı Başlatıldı (DeepL)
============================================================
Hotkeys:
  [é + →]  Türkçe    ->  İngilizce (EN-US)
  [é + ←]  İngilizce ->  Türkçe (TR)
------------------------------------------------------------
Hedef 'é' Keycode'ları : [10, 50]
Hedef Karakterler     : ['É', 'É', 'é', 'é']
------------------------------------------------------------
Çalışıyor... (Durdurmak için Ctrl+C tuşlayın)
```

---

## ⌨️ Klavye ve Tuş Uyumluluğu

Türkiye'deki standart Türkçe Q (Mac veya PC düzeni) klavyelerde `é` tuşu genellikle `Esc` tuşunun hemen altında veya `1` rakamının solundadır (macOS sanal tuş kodu `10` veya `50`).

Eğer farklı veya özel bir klavye düzeni kullanıyorsanız, tuşunuzun KeyCode değerini öğrenmek için dahili test aracını çalıştırabilirsiniz:

```bash
python main.py --detect-key
```

Ardından ekranda gördüğünüz KeyCode değerini `.env` dosyanıza ekleyebilirsiniz:
```env
E_KEYCODES=10,50,yeni_kod
```

---

## 💻 Kullanım Örneği

1. Herhangi bir uygulamada (örneğin Safari, Discord veya Telegram) yazı alanına şunu yazın:
   > *bu sistemi yarın sunucuya kuracağım ama önce api tarafındaki hatayı düzeltmem lazım*
2. Klavyenizde `é` tuşuna basılı tutarken `Sağ Ok (→)` tuşuna basın.
3. Terminalde log görünür:
   ```text
   [TR -> EN] Translating...
   [OK] Translation completed.
   ```
4. Aktif metin alanındaki yazı anında şu şekilde güncellenir:
   > *I will install this system on the server tomorrow, but first I need to fix the error on the api side*

Ters yönde (İngilizce metni Türkçeye çevirmek) için `é` tuşuna basılı tutarak `Sol Ok (←)` tuşuna basmanız yeterlidir.

---

## 🧪 Testleri Çalıştırma

Birim testleri çalıştırmak için:

```bash
python test_translator.py
```
Tüm testler güvenli geri yükleme, hata durumları ve kısayol mantığını doğrular.

---

## 📁 Proje Dosya Yapısı

```
translator/
├── main.py              # Quartz CGEventTap, DeepL ve Clipboard orkestratörü
├── requirements.txt     # Bağımlılıklar (deepl, pynput, pyperclip, pyobjc vb.)
├── .env.example         # Örnek konfigürasyon dosyası
├── .gitignore           # .env ve venv'in git'e eklenmesini önler
├── test_translator.py   # Birim test paketi
└── README.md            # Kurulum ve kullanım kılavuzu
```

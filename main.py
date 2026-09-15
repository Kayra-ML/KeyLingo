#!/usr/bin/env python3
"""
macOS Global Translator
Arka planda çalışan ve global kısayollarla aktif metin kutularındaki yazıyı
DeepL API kullanarak çift yönlü (TR <-> EN) çeviren hafif araç.

Hotkeys:
  é + Right Arrow (→): Türkçe   -> İngilizce (EN-US)
  é + Left Arrow  (←): İngilizce -> Türkçe (TR)
"""

import argparse
import os
import sys
import threading
import time
from typing import Optional, Set

# macOS Frameworks
import CoreFoundation as CF
import Quartz
from AppKit import NSPasteboard, NSPasteboardTypeString
from ApplicationServices import AXIsProcessTrusted, AXIsProcessTrustedWithOptions

# Third-party packages
import deepl
from dotenv import load_dotenv
from pynput.keyboard import Controller, Key

# --- Sabitler & Tuş Kodları ---
# Standart macOS Virtual Keycodes (Carbon / Events.h)
VK_LEFT_ARROW = 123   # kVK_LeftArrow
VK_RIGHT_ARROW = 124  # kVK_RightArrow

# ANSI Virtual Keycodes for shortcuts
VK_ANSI_A = 0  # Cmd + A (Select All)
VK_ANSI_C = 8  # Cmd + C (Copy)
VK_ANSI_V = 9  # Cmd + V (Paste)

# Kendi ürettiğimiz sentetik event'leri tanımak için özel etiket (magic tag)
MAGIC_EVENT_TAG = 0x1337BEEF


def check_accessibility_permissions() -> bool:
    """macOS Erişilebilirlik (Accessibility) izinlerini kontrol eder."""
    if AXIsProcessTrusted():
        return True

    print("\n" + "=" * 60)
    print("[UYARI] macOS Erişilebilirlik (Accessibility) izni gerekli!")
    print("=" * 60)
    print("Bu aracın global kısayolları dinleyebilmesi ve metin seçebilmesi için")
    print("Terminal uygulamanıza (Terminal, iTerm veya VS Code) izin vermelisiniz.\n")
    print("Nasıl izin verilir:")
    print("  1. Sistem Ayarları (System Settings) açın.")
    print("  2. Gizlilik ve Güvenlik (Privacy & Security) -> Erişilebilirlik (Accessibility) bölümüne gidin.")
    print("  3. Kullandığınız terminali listeye ekleyip açık (ON) konuma getirin.")
    print("  4. Ardından bu programı tekrar çalıştırın.")
    print("=" * 60 + "\n")

    # Kullanıcıya macOS izin dialogunu göster
    try:
        options = {"AXTrustedCheckOptionPrompt": True}
        AXIsProcessTrustedWithOptions(options)
    except Exception:
        pass

    return False


class Config:
    """Uygulama konfigürasyonu."""
    def __init__(self):
        # .env dosyasını script'in bulunduğu dizinden yükle
        base_dir = os.path.dirname(os.path.abspath(__file__))
        env_path = os.path.join(base_dir, ".env")
        load_dotenv(env_path)

        self.auth_key = os.getenv("DEEPL_AUTH_KEY", "").strip()

        # 'é' tuşu için keycode'lar (virgülle ayrılmış değerleri ayrıştır)
        # 10: Mac standart Türkçe Q klavyede Esc'nin altındaki tuş
        # 50: ISO klavyelerde backtick/section tuşu
        raw_keycodes = os.getenv("E_KEYCODES", "10,50")
        self.e_keycodes: Set[int] = set()
        for part in raw_keycodes.split(","):
            part = part.strip()
            if part.isdigit():
                self.e_keycodes.add(int(part))

        # Karakter bazlı eşleşmeler (é veya É)
        self.e_chars = {"é", "É", "e\u0301", "E\u0301"}


class ClipboardManager:
    """macOS NSPasteboard üzerinden hızlı ve güvenli pano yönetimi."""
    @staticmethod
    def get_pasteboard():
        return NSPasteboard.generalPasteboard()

    @classmethod
    def get_change_count(cls) -> int:
        return cls.get_pasteboard().changeCount()

    @classmethod
    def get_text(cls) -> str:
        pb = cls.get_pasteboard()
        val = pb.stringForType_(NSPasteboardTypeString)
        return str(val) if val is not None else ""

    @classmethod
    def set_text(cls, text: str) -> None:
        pb = cls.get_pasteboard()
        pb.clearContents()
        pb.setString_forType_(text, NSPasteboardTypeString)


class KeyboardSimulator:
    """Aktif metin alanında Cmd+A, Cmd+C, Cmd+V işlemlerini simüle eder."""
    def __init__(self):
        self.controller = Controller()

    def select_all(self):
        with self.controller.pressed(Key.cmd):
            self.controller.tap("a")

    def copy(self):
        with self.controller.pressed(Key.cmd):
            self.controller.tap("c")

    def paste(self):
        with self.controller.pressed(Key.cmd):
            self.controller.tap("v")

    def deselect(self):
        """Seçimi kaldırıp imleci metnin sonuna taşır."""
        self.controller.tap(Key.right)


class DeepLService:
    """DeepL API ile çeviri isteklerini yönetir."""
    def __init__(self, auth_key: str):
        if not auth_key or auth_key == "your_api_key_here":
            raise ValueError(
                "DEEPL_AUTH_KEY tanımsız veya geçersiz. Lütfen .env dosyasına geçerli API anahtarınızı ekleyin."
            )
        self.auth_key = auth_key
        self.client = deepl.Translator(auth_key)

    def sanitize_error(self, message: str) -> str:
        """API anahtarının loglarda görünmesini engeller."""
        if self.auth_key:
            return message.replace(self.auth_key, "[REDACTED_API_KEY]")
        return message

    def translate(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """Metni DeepL API ile çevirir."""
        try:
            result = self.client.translate_text(
                text,
                source_lang=source_lang,
                target_lang=target_lang
            )
            return result.text
        except Exception as e:
            clean_msg = self.sanitize_error(str(e))
            print(f"[ERROR] DeepL request failed: {clean_msg}")
            return None


class TranslationCoordinator:
    """
    Çeviri sürecini yöneten orkestratör:
    1. Orijinal panoyu saklar.
    2. Cmd+A ve Cmd+C ile aktif metni alır.
    3. DeepL API çağrısını gerçekleştirir.
    4. Başarılıysa Cmd+V ile yapıştırır.
    5. Orijinal panoyu geri yükler.
    6. Hata halinde orijinal metne ASLA dokunmaz.
    """
    def __init__(self, deepl_service: DeepLService):
        self.deepl_service = deepl_service
        self.keyboard = KeyboardSimulator()
        self.lock = threading.Lock()
        self.translation_in_progress = False

    def request_translation(self, direction: str):
        """Kısayol tetiklendiğinde çeviriyi ayrı bir thread'de başlatır."""
        # Duplicate istekleri engelle
        with self.lock:
            if self.translation_in_progress:
                return
            self.translation_in_progress = True

        thread = threading.Thread(
            target=self._run_translation_worker,
            args=(direction,),
            daemon=True
        )
        thread.start()

    def _run_translation_worker(self, direction: str):
        try:
            self._execute_flow(direction)
        finally:
            with self.lock:
                self.translation_in_progress = False

    def _execute_flow(self, direction: str):
        # Dil ayarları
        if direction == "TR->EN":
            source_lang = "TR"
            target_lang = "EN-US"
            log_direction = "TR -> EN"
        else:
            source_lang = "EN"
            target_lang = "TR"
            log_direction = "EN -> TR"

        # 1. Orijinal panoyu sakla
        original_clipboard = ClipboardManager.get_text()
        initial_change_count = ClipboardManager.get_change_count()

        # 2. Aktif metin alanındaki tüm metni seç (Cmd + A)
        self.keyboard.select_all()
        time.sleep(0.04)

        # 3. Metni kopyala (Cmd + C)
        self.keyboard.copy()

        # Panonun güncellenmesini bekle (maksimum 0.35 saniye)
        copied = False
        start_time = time.time()
        while time.time() - start_time < 0.35:
            if ClipboardManager.get_change_count() != initial_change_count:
                copied = True
                break
            time.sleep(0.015)

        # Kopyalanan metni al
        text_to_translate = ClipboardManager.get_text()

        # Boş girdi kontrolü: Aktif input boşsa hiçbir şey yapma
        if not copied or not text_to_translate or not text_to_translate.strip():
            # Eğer pano kazara değiştiyse orijinali geri yükle
            if copied:
                ClipboardManager.set_text(original_clipboard)
            return

        # 4. DeepL API çağrısı
        print(f"[{log_direction}] Translating...")

        translated_text = self.deepl_service.translate(
            text_to_translate,
            source_lang=source_lang,
            target_lang=target_lang
        )

        # GÜVENLİK DAVRANIŞI:
        # API başarısızsa veya boş döndüyse orijinal metne DOKUNMA!
        if translated_text is None or not translated_text.strip():
            # Panoyu orijinal haline getir
            ClipboardManager.set_text(original_clipboard)
            # Metni olduğu gibi bırak
            return

        # 5. Çeviriyi panoya yükle ve yapıştır (Cmd + V)
        ClipboardManager.set_text(translated_text)
        time.sleep(0.03)
        self.keyboard.paste()

        # Hedef uygulamanın yapıştırma işlemini tamamlaması için kısa bekleme
        time.sleep(0.20)

        # 6. Kullanıcının eski panosunu geri yükle
        ClipboardManager.set_text(original_clipboard)

        print("[OK] Translation completed.")


class GlobalHotkeyListener:
    """
    Quartz CGEventTap kullanarak global klavye dinleyici.
    'é' tuşunun karakter çıkışını suppress eder.
    'é + Right Arrow' ve 'é + Left Arrow' kombinasyonlarını yakalar.
    Eğer 'é' tek başına basılıp bırakılırsa veya başka bir harf yazılırsa 'é' harfini geri re-inject eder.
    """
    def __init__(self, config: Config, coordinator: TranslationCoordinator):
        self.config = config
        self.coordinator = coordinator

        # Durum değişkenleri
        self.is_e_down = False
        self.combo_fired = False
        self.pending_e_down_event = None

        self.tap = None
        self.run_loop = None

    def is_synthetic(self, event) -> bool:
        """Etkinliğin programın kendisi tarafından oluşturulup oluşturulmadığını kontrol eder."""
        # 1. Özel etiket kontrolü
        user_data = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGEventSourceUserData)
        if user_data == MAGIC_EVENT_TAG:
            return True

        # 2. Process ID kontrolü
        pid = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGEventSourceUnixProcessID)
        if pid == os.getpid():
            return True

        return False

    def is_trigger_key(self, keycode: int, char: str, flags: int) -> bool:
        """Basılan tuşun 'é' tetikleyici tuşu olup olmadığını kontrol eder."""
        # Eğer Cmd veya Ctrl basılıysa (örneğin Cmd+E veya Ctrl+E) bu bir sistem kısayoludur, dokunma
        if flags & (Quartz.kCGEventFlagMaskCommand | Quartz.kCGEventFlagMaskControl):
            return False

        # Karakter kontrolü
        if char and char in self.config.e_chars:
            return True

        # Keycode kontrolü
        if keycode in self.config.e_keycodes:
            return True

        return False

    def replay_event(self, event):
        """Saklanan bir klavye olayını sentetik etiketle yeniden gönderir."""
        if event is None:
            return
        tagged_copy = Quartz.CGEventCreateCopy(event)
        Quartz.CGEventSetIntegerValueField(tagged_copy, Quartz.kCGEventSourceUserData, MAGIC_EVENT_TAG)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, tagged_copy)

    def flush_pending_e(self):
        """Bekletilen 'é' tuşunu bırakır ve simüle eder."""
        if self.pending_e_down_event is not None:
            self.replay_event(self.pending_e_down_event)
            self.pending_e_down_event = None

    def event_tap_callback(self, proxy, event_type, event, refcon):
        # Event tap devre dışı kaldıysa otomatik olarak tekrar etkinleştir
        if event_type in (Quartz.kCGEventTapDisabledByTimeout, Quartz.kCGEventTapDisabledByUserInput):
            if self.tap:
                Quartz.CGEventTapEnable(self.tap, True)
            return event

        # Programın kendi simüle ettiği event'leri serbest bırak
        if self.is_synthetic(event):
            return event

        keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
        flags = Quartz.CGEventGetFlags(event)

        # Karakter bilgisini al
        actual_len, chars = Quartz.CGEventKeyboardGetUnicodeString(event, 4, None, None)
        char = chars if actual_len > 0 else ""

        # --- KEY DOWN ---
        if event_type == Quartz.kCGEventKeyDown:
            # 1. 'é' tuşuna basıldı
            if self.is_trigger_key(keycode, char, flags):
                self.is_e_down = True
                self.combo_fired = False

                # Eğer autorepeat değilse event'in bir kopyasını sakla
                if self.pending_e_down_event is None:
                    self.pending_e_down_event = Quartz.CGEventCreateCopy(event)

                # Tuşun ekrana yazılmasını engelle (SUPPRESS)
                return None

            # 2. 'é' basılıyken başka bir tuşa basıldı
            if self.is_e_down:
                # Right Arrow (→): TR -> EN
                if keycode == VK_RIGHT_ARROW:
                    self.combo_fired = True
                    self.pending_e_down_event = None
                    self.coordinator.request_translation("TR->EN")
                    return None  # Sağ ok hareketini suppress et

                # Left Arrow (←): EN -> TR
                elif keycode == VK_LEFT_ARROW:
                    self.combo_fired = True
                    self.pending_e_down_event = None
                    self.coordinator.request_translation("EN->TR")
                    return None  # Sol ok hareketini suppress et

                else:
                    # Başka bir normal tuşa basıldı (kullanıcı hızlıca yazı yazıyor)
                    # Bekleyen 'é' tuşunu gönder ve durumu sıfırla
                    self.flush_pending_e()
                    self.is_e_down = False
                    self.combo_fired = False
                    return event

            return event

        # --- KEY UP ---
        elif event_type == Quartz.kCGEventKeyUp:
            # 1. 'é' tuşu bırakıldı
            if self.is_trigger_key(keycode, char, flags):
                self.is_e_down = False

                if self.combo_fired:
                    # Kısayol başarıyla çalıştı, 'é' asla yazılmamalı
                    self.combo_fired = False
                    self.pending_e_down_event = None
                    return None  # KeyUp'ı suppress et
                else:
                    # Kullanıcı sadece 'é' tuşuna basıp bıraktı
                    self.flush_pending_e()
                    # Bu key up event'ini de tagged olarak gönder
                    self.replay_event(event)
                    return None

            # 2. Ok tuşu bırakıldı
            if keycode in (VK_LEFT_ARROW, VK_RIGHT_ARROW):
                if self.combo_fired:
                    # Kısayol sırasında basılan okun release event'ini suppress et
                    return None

            return event

        return event

    def start(self):
        """Event tap'i başlatır ve ana runloop'a ekler."""
        event_mask = (
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown) |
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyUp)
        )

        self.tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            event_mask,
            self.event_tap_callback,
            None
        )

        if not self.tap:
            print("[HATA] Quartz Event Tap oluşturulamadı. Erişilebilirlik iznini kontrol edin.")
            sys.exit(1)

        source = CF.CFMachPortCreateRunLoopSource(None, self.tap, 0)
        self.run_loop = CF.CFRunLoopGetCurrent()
        CF.CFRunLoopAddSource(self.run_loop, source, CF.kCFRunLoopDefaultMode)
        Quartz.CGEventTapEnable(self.tap, True)

        try:
            CF.CFRunLoopRun()
        except KeyboardInterrupt:
            pass
        finally:
            if self.tap:
                Quartz.CGEventTapEnable(self.tap, False)

    def stop(self):
        """Event tap ve runloop'u durdurur."""
        if self.run_loop:
            CF.CFRunLoopStop(self.run_loop)


def detect_keys_mode():
    """
    Kullanıcının klavyesindeki tuşların keycode ve karakterlerini
    canlı olarak ekrana yazdıran yardımcı mod.
    """
    print("=" * 60)
    print("TUŞ TESPİT MODU (KEY DETECTOR)")
    print("=" * 60)
    print("Klavyenizdeki herhangi bir tuşa basın.")
    print("Tetikleyici olarak kullanmak istediğiniz tuşun (örneğin é)")
    print("KeyCode değerini öğrenip .env dosyasına ekleyebilirsiniz.")
    print("Çıkış için Ctrl+C tuşlayın.\n")

    def detect_callback(proxy, event_type, event, refcon):
        if event_type == Quartz.kCGEventKeyDown:
            keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
            actual_len, chars = Quartz.CGEventKeyboardGetUnicodeString(event, 8, None, None)
            char = chars if actual_len > 0 else "<none>"
            print(f"-> KeyCode: {keycode:3d} | Karakter: {repr(char)}")
        return event

    tap = Quartz.CGEventTapCreate(
        Quartz.kCGSessionEventTap,
        Quartz.kCGHeadInsertEventTap,
        Quartz.kCGEventTapOptionListenOnly,
        Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown),
        detect_callback,
        None
    )

    if not tap:
        print("[HATA] Erişilebilirlik izni gerekli!")
        return

    source = CF.CFMachPortCreateRunLoopSource(None, tap, 0)
    loop = CF.CFRunLoopGetCurrent()
    CF.CFRunLoopAddSource(loop, source, CF.kCFRunLoopDefaultMode)
    Quartz.CGEventTapEnable(tap, True)

    try:
        CF.CFRunLoopRun()
    except KeyboardInterrupt:
        print("\nTuş tespit modu sonlandırıldı.")


def test_api_mode(config: Config):
    """DeepL API bağlantısını ve anahtarını test eder."""
    print("=" * 60)
    print("DeepL API Testi Başlatılıyor...")
    print("=" * 60)

    try:
        service = DeepLService(config.auth_key)
    except ValueError as ve:
        print(f"[HATA] {ve}")
        return

    test_sentence = "Bu bir test cümlesidir."
    print(f"Kaynak metin : {test_sentence}")
    print("[TR -> EN] Çevriliyor...")

    result = service.translate(test_sentence, "TR", "EN-US")
    if result:
        print(f"Çeviri sonucu: {result}")
        print("[BAŞARILI] DeepL API bağlantısı sorunsuz çalışıyor!")
    else:
        print("[BAŞARISIZ] Çeviri gerçekleştirilemedi.")


def main():
    parser = argparse.ArgumentParser(description="macOS Global Çeviri Aracı (DeepL)")
    parser.add_argument(
        "--detect-key",
        action="store_true",
        help="Klavyenizdeki tuşların KeyCode değerlerini canlı olarak görmek için çalıştırın."
    )
    parser.add_argument(
        "--test-api",
        action="store_true",
        help=".env dosyasındaki DeepL API anahtarını ve bağlantısını test eder."
    )
    args = parser.parse_args()

    # Erişilebilirlik iznini kontrol et
    if not check_accessibility_permissions():
        sys.exit(1)

    # 1. Tuş tespit modu
    if args.detect_key:
        detect_keys_mode()
        return

    # Konfigürasyonu yükle
    config = Config()

    # 2. API test modu
    if args.test_api:
        test_api_mode(config)
        return

    # Normal çalışma modu için API anahtarı kontrolü
    if not config.auth_key or config.auth_key == "your_api_key_here":
        print("\n[ERROR] DEEPL_AUTH_KEY bulunamadı!")
        print("Lütfen .env dosyasını oluşturup geçerli bir DeepL API anahtarı ekleyin:")
        print("  cp .env.example .env")
        print("  nano .env")
        print("\nAPI anahtarınızı girdikten sonra programı tekrar çalıştırın.\n")
        sys.exit(1)

    try:
        deepl_service = DeepLService(config.auth_key)
    except ValueError as e:
        print(f"\n[ERROR] {e}\n")
        sys.exit(1)

    coordinator = TranslationCoordinator(deepl_service)
    listener = GlobalHotkeyListener(config, coordinator)

    print("=" * 60)
    print("  macOS Global Çeviri Aracı Başlatıldı (DeepL)")
    print("=" * 60)
    print("Hotkeys:")
    print("  [é + →]  Türkçe    ->  İngilizce (EN-US)")
    print("  [é + ←]  İngilizce ->  Türkçe (TR)")
    print("-" * 60)
    print(f"Hedef 'é' Keycode'ları : {sorted(list(config.e_keycodes))}")
    print(f"Hedef Karakterler     : {sorted(list(config.e_chars))}")
    print("-" * 60)
    print("Çalışıyor... (Durdurmak için Ctrl+C tuşlayın)\n")

    listener.start()


if __name__ == "__main__":
    main()

import sys
import cv2
import json
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QWidget, 
                            QVBoxLayout, QHBoxLayout, QPushButton, QTabWidget,
                            QSlider, QFileDialog, QScrollArea, QGridLayout,
                            QLineEdit, QMessageBox)
from PyQt5.QtGui import QImage, QPixmap, QFont
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPoint

PRESETS_FILE = "color_presets.json"

class DesktopPet(QLabel):
    """Masaüstünde hareket eden şeffaf anime karakteri"""
    def __init__(self, video_path, hsv_values, scale=1.0, opacity=1.0):
        super().__init__()
        self.video_path = video_path
        self.lower_h, self.lower_s, self.lower_v = hsv_values['lower']
        self.upper_h, self.upper_s, self.upper_v = hsv_values['upper']
        self.scale_factor = scale
        self.opacity_value = opacity
        
        # Şeffaf, kenarlıksız, her zaman üstte pencere
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(opacity)
        
        self.cap = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        
        # Sürükleme için
        self.dragging = False
        self.offset = QPoint()
        
        self.original_size = None
        
        self.load_video()
        
    def load_video(self):
        if not os.path.exists(self.video_path):
            QMessageBox.critical(None, "Hata", f"Video bulunamadı: {self.video_path}")
            return
            
        self.cap = cv2.VideoCapture(self.video_path)
        ret, frame = self.cap.read()
        if not ret:
            QMessageBox.critical(None, "Hata", "Video açılamadı!")
            return
        
        # Video boyutuna göre pencereyi ayarla ve scale uygula
        h, w, _ = frame.shape
        self.original_size = (w, h)
        scaled_w = int(w * self.scale_factor)
        scaled_h = int(h * self.scale_factor)
        self.setGeometry(100, 100, scaled_w, scaled_h)
        self.timer.start(30)
    
    def set_scale(self, scale):
        """Ölçeği değiştir"""
        self.scale_factor = scale
        if self.original_size:
            w, h = self.original_size
            self.resize(int(w * scale), int(h * scale))
    
    def set_opacity(self, opacity):
        """Şeffaflığı değiştir"""
        self.opacity_value = opacity
        self.setWindowOpacity(opacity)
        
    def update_frame(self):
        if not self.cap:
            return
            
        ret, frame = self.cap.read()
        if not ret:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
        
        if not ret:
            return
        
        # BGR -> RGBA
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)
        
        # HSV ile chroma key
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower = (self.lower_h, self.lower_s, self.lower_v)
        upper = (self.upper_h, self.upper_s, self.upper_v)
        
        mask = cv2.inRange(hsv, lower, upper)
        frame[mask > 0] = (0, 0, 0, 0)
        
        # Scale uygula
        h, w, _ = frame.shape
        if self.scale_factor != 1.0:
            new_w = int(w * self.scale_factor)
            new_h = int(h * self.scale_factor)
            frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # PyQt için QImage oluştur
        h, w, ch = frame.shape
        qimg = QImage(frame.data, w, h, w*ch, QImage.Format_RGBA8888)
        self.setPixmap(QPixmap.fromImage(qimg))
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.offset = event.pos()
    
    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move(self.mapToParent(event.pos() - self.offset))
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
    
    def closeEvent(self, event):
        if self.cap:
            self.cap.release()
        self.timer.stop()
        event.accept()


class ControlPanel(QWidget):
    """Video seçimi ve oynatma kontrolleri"""
    start_pet = pyqtSignal(str, dict, float, float)
    stop_pet = pyqtSignal()
    update_pet_scale = pyqtSignal(float)
    update_pet_opacity = pyqtSignal(float)
    
    def __init__(self):
        super().__init__()
        self.current_preset = None
        self.video_path = None
        self.is_running = False
        self.scale_value = 1.0
        self.opacity_value = 1.0
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("🎮 Desktop Pet Kontrolü")
        title.setStyleSheet("font-size: 20px; color: #c77dff; font-weight: bold; padding: 10px;")
        layout.addWidget(title)
        
        # Video selection
        video_layout = QHBoxLayout()
        video_label = QLabel("📹 Video:")
        video_label.setStyleSheet("color: #c77dff; font-size: 14px; min-width: 80px;")
        
        self.video_path_label = QLabel("Video seçilmedi")
        self.video_path_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a2e;
                border: 2px solid #7b2cbf;
                border-radius: 5px;
                padding: 8px;
                color: #9d4edd;
            }
        """)
        
        browse_btn = QPushButton("📁 Seç")
        browse_btn.clicked.connect(self.select_video)
        browse_btn.setStyleSheet(self.get_button_style())
        
        video_layout.addWidget(video_label)
        video_layout.addWidget(self.video_path_label, 1)
        video_layout.addWidget(browse_btn)
        layout.addLayout(video_layout)
        
        # Preset selection
        preset_layout = QHBoxLayout()
        preset_label = QLabel("🎨 Preset:")
        preset_label.setStyleSheet("color: #c77dff; font-size: 14px; min-width: 80px;")
        
        self.preset_label = QLabel("Preset seçilmedi")
        self.preset_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a2e;
                border: 2px solid #7b2cbf;
                border-radius: 5px;
                padding: 8px;
                color: #9d4edd;
            }
        """)
        
        preset_layout.addWidget(preset_label)
        preset_layout.addWidget(self.preset_label, 1)
        layout.addLayout(preset_layout)
        
        # Settings section
        settings_title = QLabel("⚙️ Pet Ayarları")
        settings_title.setStyleSheet("font-size: 16px; color: #c77dff; font-weight: bold; margin-top: 15px; padding: 5px;")
        layout.addWidget(settings_title)
        
        # Scale slider
        scale_layout = QHBoxLayout()
        scale_label = QLabel("📏 Boyut:")
        scale_label.setStyleSheet("color: #9d4edd; font-size: 14px; min-width: 100px;")
        
        self.scale_slider = QSlider(Qt.Horizontal)
        self.scale_slider.setMinimum(25)
        self.scale_slider.setMaximum(200)
        self.scale_slider.setValue(100)
        self.scale_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #1a1a2e;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #9d4edd;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: #c77dff;
            }
        """)
        self.scale_slider.valueChanged.connect(self.on_scale_changed)
        
        self.scale_value_label = QLabel("100%")
        self.scale_value_label.setStyleSheet("color: #c77dff; font-size: 14px; min-width: 50px;")
        
        scale_layout.addWidget(scale_label)
        scale_layout.addWidget(self.scale_slider)
        scale_layout.addWidget(self.scale_value_label)
        layout.addLayout(scale_layout)
        
        # Opacity slider
        opacity_layout = QHBoxLayout()
        opacity_label = QLabel("🌟 Şeffaflık:")
        opacity_label.setStyleSheet("color: #9d4edd; font-size: 14px; min-width: 100px;")
        
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setMinimum(20)
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #1a1a2e;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #9d4edd;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: #c77dff;
            }
        """)
        self.opacity_slider.valueChanged.connect(self.on_opacity_changed)
        
        self.opacity_value_label = QLabel("100%")
        self.opacity_value_label.setStyleSheet("color: #c77dff; font-size: 14px; min-width: 50px;")
        
        opacity_layout.addWidget(opacity_label)
        opacity_layout.addWidget(self.opacity_slider)
        opacity_layout.addWidget(self.opacity_value_label)
        layout.addLayout(opacity_layout)
        
        # Position presets
        position_layout = QHBoxLayout()
        position_label = QLabel("📍 Konum:")
        position_label.setStyleSheet("color: #9d4edd; font-size: 14px; min-width: 100px;")
        
        self.pos_topleft_btn = QPushButton("⬉ Sol Üst")
        self.pos_topleft_btn.clicked.connect(lambda: self.set_position("topleft"))
        self.pos_topleft_btn.setStyleSheet(self.get_small_button_style())
        self.pos_topleft_btn.setEnabled(False)
        
        self.pos_topright_btn = QPushButton("⬈ Sağ Üst")
        self.pos_topright_btn.clicked.connect(lambda: self.set_position("topright"))
        self.pos_topright_btn.setStyleSheet(self.get_small_button_style())
        self.pos_topright_btn.setEnabled(False)
        
        self.pos_bottomleft_btn = QPushButton("⬋ Sol Alt")
        self.pos_bottomleft_btn.clicked.connect(lambda: self.set_position("bottomleft"))
        self.pos_bottomleft_btn.setStyleSheet(self.get_small_button_style())
        self.pos_bottomleft_btn.setEnabled(False)
        
        self.pos_bottomright_btn = QPushButton("⬊ Sağ Alt")
        self.pos_bottomright_btn.clicked.connect(lambda: self.set_position("bottomright"))
        self.pos_bottomright_btn.setStyleSheet(self.get_small_button_style())
        self.pos_bottomright_btn.setEnabled(False)
        
        position_layout.addWidget(position_label)
        position_layout.addWidget(self.pos_topleft_btn)
        position_layout.addWidget(self.pos_topright_btn)
        position_layout.addWidget(self.pos_bottomleft_btn)
        position_layout.addWidget(self.pos_bottomright_btn)
        layout.addLayout(position_layout)
        
        # Info box
        info = QLabel("ℹ️ Saved Settings sekmesinden bir preset seçin, ardından START'a basın")
        info.setStyleSheet("""
            QLabel {
                background-color: #1a1a2e;
                border-left: 4px solid #9d4edd;
                padding: 12px;
                color: #c77dff;
                font-size: 13px;
                border-radius: 5px;
                margin: 10px 0;
            }
        """)
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Control buttons
        btn_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("▶ START")
        self.start_btn.clicked.connect(self.start_desktop_pet)
        self.start_btn.setStyleSheet(self.get_button_style("#27ae60", "#2ecc71"))
        self.start_btn.setEnabled(False)
        
        self.stop_btn = QPushButton("⏹ STOP")
        self.stop_btn.clicked.connect(self.stop_desktop_pet)
        self.stop_btn.setStyleSheet(self.get_button_style("#c0392b", "#e74c3c"))
        self.stop_btn.setEnabled(False)
        
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)
        
        # Status
        self.status_label = QLabel("⭕ Durdu")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a2e;
                border: 2px solid #7b2cbf;
                border-radius: 8px;
                padding: 15px;
                color: #e74c3c;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def get_button_style(self, color="#7b2cbf", hover_color="#9d4edd"):
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 15px 30px;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: #5a189a;
            }}
            QPushButton:disabled {{
                background-color: #3c3c3c;
                color: #666;
            }}
        """
    
    def get_small_button_style(self):
        return """
            QPushButton {
                background-color: #5a189a;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7b2cbf;
            }
            QPushButton:pressed {
                background-color: #3c096c;
            }
            QPushButton:disabled {
                background-color: #2c2c2c;
                color: #666;
            }
        """
    
    def select_video(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Video Seç", "", "Video Files (*.mp4 *.avi *.mov)")
        if file_path:
            self.video_path = file_path
            self.video_path_label.setText(os.path.basename(file_path))
            self.check_ready()
    
    def set_preset(self, name, values):
        self.current_preset = values
        self.preset_label.setText(name)
        self.check_ready()
    
    def check_ready(self):
        if self.video_path and self.current_preset:
            self.start_btn.setEnabled(True)
        else:
            self.start_btn.setEnabled(False)
    
    def on_scale_changed(self, value):
        self.scale_value = value / 100.0
        self.scale_value_label.setText(f"{value}%")
        if self.is_running:
            self.update_pet_scale.emit(self.scale_value)
    
    def on_opacity_changed(self, value):
        self.opacity_value = value / 100.0
        self.opacity_value_label.setText(f"{value}%")
        if self.is_running:
            self.update_pet_opacity.emit(self.opacity_value)
    
    def set_position(self, position):
        """Pet'in pozisyonunu ayarla"""
        from PyQt5.QtWidgets import QApplication
        screen = QApplication.desktop().screenGeometry()
        
        # Pet boyutunu hesapla
        if hasattr(self, 'pet_size'):
            pet_w, pet_h = self.pet_size
        else:
            pet_w, pet_h = 300, 400
        
        positions = {
            'topleft': (20, 20),
            'topright': (screen.width() - pet_w - 20, 20),
            'bottomleft': (20, screen.height() - pet_h - 60),
            'bottomright': (screen.width() - pet_w - 20, screen.height() - pet_h - 60)
        }
        
        # MainWindow üzerinden pet'e eriş
        main_window = self.window()
        if hasattr(main_window, 'desktop_pet') and main_window.desktop_pet:
            x, y = positions[position]
            main_window.desktop_pet.move(x, y)
    
    def start_desktop_pet(self):
        if self.video_path and self.current_preset:
            self.start_pet.emit(self.video_path, self.current_preset, self.scale_value, self.opacity_value)
            self.is_running = True
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.pos_topleft_btn.setEnabled(True)
            self.pos_topright_btn.setEnabled(True)
            self.pos_bottomleft_btn.setEnabled(True)
            self.pos_bottomright_btn.setEnabled(True)
            self.status_label.setText("✅ Çalışıyor")
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #1a1a2e;
                    border: 2px solid #27ae60;
                    border-radius: 8px;
                    padding: 15px;
                    color: #2ecc71;
                    font-size: 16px;
                    font-weight: bold;
                }
            """)
    
    def stop_desktop_pet(self):
        self.stop_pet.emit()
        self.is_running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.pos_topleft_btn.setEnabled(False)
        self.pos_topright_btn.setEnabled(False)
        self.pos_bottomleft_btn.setEnabled(False)
        self.pos_bottomright_btn.setEnabled(False)
        self.status_label.setText("⭕ Durdu")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a2e;
                border: 2px solid #7b2cbf;
                border-radius: 8px;
                padding: 15px;
                color: #e74c3c;
                font-size: 16px;
                font-weight: bold;
            }
        """)


class SavedSettingsWidget(QWidget):
    """Gallery yerine Saved Settings"""
    preset_selected = pyqtSignal(str, dict)
    
    def __init__(self):
        super().__init__()
        self.presets = self.load_presets()
        self.selected_preset = None
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        title = QLabel("💾 Saved Settings")
        title.setStyleSheet("font-size: 20px; color: #c77dff; font-weight: bold; padding: 10px;")
        layout.addWidget(title)
        
        # Scroll area for presets
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: #0f0f1e; }")
        
        container = QWidget()
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(15)
        container.setLayout(self.grid_layout)
        
        self.refresh_gallery()
        
        scroll.setWidget(container)
        layout.addWidget(scroll)
        self.setLayout(layout)
    
    def refresh_gallery(self):
        # Clear existing widgets
        for i in reversed(range(self.grid_layout.count())): 
            self.grid_layout.itemAt(i).widget().setParent(None)
        
        self.presets = self.load_presets()
        
        if not self.presets:
            empty_label = QLabel("Henüz ayar kaydedilmedi.\n'Add' sekmesinden yeni ayar ekleyin.")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #9d4edd; font-size: 16px; padding: 50px;")
            self.grid_layout.addWidget(empty_label, 0, 0)
            return
        
        row, col = 0, 0
        for name, values in self.presets.items():
            preset_widget = self.create_preset_widget(name, values)
            self.grid_layout.addWidget(preset_widget, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1
    
    def create_preset_widget(self, name, values):
        widget = QWidget()
        is_selected = (self.selected_preset == name)
        
        widget.setStyleSheet(f"""
            QWidget {{
                background-color: {'#5a189a' if is_selected else '#1a1a2e'};
                border: 2px solid {'#c77dff' if is_selected else '#7b2cbf'};
                border-radius: 10px;
                padding: 15px;
            }}
            QWidget:hover {{
                border-color: #c77dff;
            }}
        """)
        
        layout = QVBoxLayout()
        
        name_label = QLabel(f"{'✓ ' if is_selected else '🎨 '}{name}")
        name_label.setStyleSheet(f"color: {'#ffffff' if is_selected else '#c77dff'}; font-size: 16px; font-weight: bold;")
        layout.addWidget(name_label)
        
        info_label = QLabel(f"Lower: {values['lower']}\nUpper: {values['upper']}")
        info_label.setStyleSheet(f"color: {'#e0e0e0' if is_selected else '#9d4edd'}; font-size: 12px;")
        layout.addWidget(info_label)
        
        btn_layout = QHBoxLayout()
        
        select_btn = QPushButton("✓ Seç" if not is_selected else "✓ Seçili")
        select_btn.clicked.connect(lambda: self.select_preset(name, values))
        select_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {'#27ae60' if is_selected else '#5a189a'};
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {'#2ecc71' if is_selected else '#7b2cbf'};
            }}
        """)
        
        delete_btn = QPushButton("🗑")
        delete_btn.clicked.connect(lambda: self.delete_preset(name))
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #e63946;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px;
                font-size: 12px;
                max-width: 40px;
            }
            QPushButton:hover {
                background-color: #d62828;
            }
        """)
        
        btn_layout.addWidget(select_btn)
        btn_layout.addWidget(delete_btn)
        layout.addLayout(btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def select_preset(self, name, values):
        self.selected_preset = name
        self.preset_selected.emit(name, values)
        self.refresh_gallery()
    
    def delete_preset(self, name):
        reply = QMessageBox.question(self, 'Sil', f'"{name}" ayarını silmek istediğinize emin misiniz?',
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            del self.presets[name]
            self.save_presets()
            if self.selected_preset == name:
                self.selected_preset = None
            self.refresh_gallery()
    
    def load_presets(self):
        if os.path.exists(PRESETS_FILE):
            with open(PRESETS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_presets(self):
        with open(PRESETS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.presets, f, indent=2, ensure_ascii=False)


class AddPresetWidget(QWidget):
    preset_saved = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.video_path = None
        self.cap = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_preview)
        
        self.lower_h, self.lower_s, self.lower_v = 0, 0, 0
        self.upper_h, self.upper_s, self.upper_v = 179, 255, 10
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("➕ Yeni Ayar Ekle")
        title.setStyleSheet("font-size: 20px; color: #c77dff; font-weight: bold; padding: 10px;")
        layout.addWidget(title)
        
        # Name input
        name_layout = QHBoxLayout()
        name_label = QLabel("Ayar Adı:")
        name_label.setStyleSheet("color: #c77dff; font-size: 14px; min-width: 100px;")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Örn: Yeşil Ekran, Mavi Arka Plan...")
        self.name_input.setStyleSheet("""
            QLineEdit {
                background-color: #1a1a2e;
                border: 2px solid #7b2cbf;
                border-radius: 5px;
                padding: 8px;
                color: white;
                font-size: 14px;
            }
        """)
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)
        
        # Preview
        preview_btn = QPushButton("📹 Test Videosu Yükle (Önizleme İçin)")
        preview_btn.clicked.connect(self.load_preview_video)
        preview_btn.setStyleSheet(self.get_button_style())
        layout.addWidget(preview_btn)
        
        self.preview_label = QLabel("Video yükleyerek ayarları test edebilirsiniz")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a2e;
                border: 2px solid #9d4edd;
                border-radius: 10px;
                color: #c77dff;
                min-height: 300px;
            }
        """)
        layout.addWidget(self.preview_label)
        
        # HSV Sliders
        sliders_layout = QVBoxLayout()
        
        # Lower HSV
        lower_label = QLabel("🔽 Lower HSV Değerleri (Silinecek Renkler - Alt Sınır)")
        lower_label.setStyleSheet("color: #c77dff; font-size: 16px; font-weight: bold; margin-top: 10px;")
        sliders_layout.addWidget(lower_label)
        
        self.lower_h_slider = self.create_slider("Hue:", 0, 179, 0, self.update_lower_h)
        self.lower_s_slider = self.create_slider("Saturation:", 0, 255, 0, self.update_lower_s)
        self.lower_v_slider = self.create_slider("Value:", 0, 255, 0, self.update_lower_v)
        
        sliders_layout.addLayout(self.lower_h_slider)
        sliders_layout.addLayout(self.lower_s_slider)
        sliders_layout.addLayout(self.lower_v_slider)
        
        # Upper HSV
        upper_label = QLabel("🔼 Upper HSV Değerleri (Silinecek Renkler - Üst Sınır)")
        upper_label.setStyleSheet("color: #c77dff; font-size: 16px; font-weight: bold; margin-top: 10px;")
        sliders_layout.addWidget(upper_label)
        
        self.upper_h_slider = self.create_slider("Hue:", 0, 179, 179, self.update_upper_h)
        self.upper_s_slider = self.create_slider("Saturation:", 0, 255, 255, self.update_upper_s)
        self.upper_v_slider = self.create_slider("Value:", 0, 255, 10, self.update_upper_v)
        
        sliders_layout.addLayout(self.upper_h_slider)
        sliders_layout.addLayout(self.upper_s_slider)
        sliders_layout.addLayout(self.upper_v_slider)
        
        layout.addLayout(sliders_layout)
        
        # Save button
        save_btn = QPushButton("💾 Ayarları Kaydet")
        save_btn.clicked.connect(self.save_preset)
        save_btn.setStyleSheet(self.get_button_style("#27ae60", "#2ecc71"))
        layout.addWidget(save_btn)
        
        self.setLayout(layout)
    
    def create_slider(self, label_text, min_val, max_val, default, callback):
        layout = QHBoxLayout()
        
        label = QLabel(label_text)
        label.setStyleSheet("color: #9d4edd; font-size: 13px; min-width: 100px;")
        
        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(default)
        slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #1a1a2e;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #9d4edd;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: #c77dff;
            }
        """)
        slider.valueChanged.connect(callback)
        
        value_label = QLabel(str(default))
        value_label.setStyleSheet("color: #c77dff; font-size: 13px; min-width: 40px;")
        slider.valueChanged.connect(lambda v: value_label.setText(str(v)))
        
        layout.addWidget(label)
        layout.addWidget(slider)
        layout.addWidget(value_label)
        
        return layout
    
    def get_button_style(self, color="#7b2cbf", hover_color="#9d4edd"):
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: #5a189a;
            }}
        """
    
    def update_lower_h(self, v):
        self.lower_h = v
    def update_lower_s(self, v):
        self.lower_s = v
    def update_lower_v(self, v):
        self.lower_v = v
    def update_upper_h(self, v):
        self.upper_h = v
    def update_upper_s(self, v):
        self.upper_s = v
    def update_upper_v(self, v):
        self.upper_v = v
    
    def load_preview_video(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Video Seç", "", "Video Files (*.mp4 *.avi *.mov)")
        if file_path:
            self.video_path = file_path
            if self.cap:
                self.cap.release()
            self.cap = cv2.VideoCapture(self.video_path)
            self.timer.start(30)
    
    def update_preview(self):
        if not self.cap:
            return
        
        ret, frame = self.cap.read()
        if not ret:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
        
        if not ret:
            return
        
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        lower = (self.lower_h, self.lower_s, self.lower_v)
        upper = (self.upper_h, self.upper_s, self.upper_v)
        
        mask = cv2.inRange(hsv, lower, upper)
        frame[mask > 0] = (0, 0, 0, 0)
        
        h, w, _ = frame.shape
        max_w, max_h = 600, 300
        if w > max_w or h > max_h:
            scale = min(max_w/w, max_h/h)
            new_w, new_h = int(w*scale), int(h*scale)
            frame = cv2.resize(frame, (new_w, new_h))
        
        h, w, ch = frame.shape
        qimg = QImage(frame.data, w, h, w*ch, QImage.Format_RGBA8888)
        self.preview_label.setPixmap(QPixmap.fromImage(qimg))
    
    def save_preset(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir ayar adı girin!")
            return
        
        presets = {}
        if os.path.exists(PRESETS_FILE):
            with open(PRESETS_FILE, 'r', encoding='utf-8') as f:
                presets = json.load(f)
        
        presets[name] = {
            'lower': [self.lower_h, self.lower_s, self.lower_v],
            'upper': [self.upper_h, self.upper_s, self.upper_v]
        }
        
        with open(PRESETS_FILE, 'w', encoding='utf-8') as f:
            json.dump(presets, f, indent=2, ensure_ascii=False)
        
        QMessageBox.information(self, "Başarılı", f"'{name}' ayarı kaydedildi!")
        self.name_input.clear()
        self.preset_saved.emit()


class AboutWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        
        title = QLabel("👨‍💻 About Developer")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 28px; color: #c77dff; font-weight: bold; margin: 20px;")
        
        info = QLabel("""
        <div style='text-align: center; line-height: 1.8;'>
        <p style='font-size: 20px; color: #9d4edd; margin: 10px;'>
        <b>🎭WaifuEngine</b>
        </p>
        <p style='font-size: 16px; color: #7b2cbf;'>
        Anime karakterlerinizi masaüstünüze getirin!<br>
        Şeffaf arka plan ile gerçek bir desktop pet deneyimi
        </p>
        <p style='font-size: 14px; color: #9d4edd; margin-top: 30px;'>
        ✨ Özellikler:<br>
        • Masaüstü üzerinde özgürce hareket eden pet<br>
        • Chroma key ile tam şeffaflık<br>
        • Özelleştirilebilir HSV renk ayarları<br>
        • Sürükle-bırak ile taşıma<br>
        • Kaydedilebilir preset'ler<br>
        • Boyut ve şeffaflık ayarları<br>
        • Her zaman üstte kalır<br>
        </p>
        <p style='font-size: 14px; color: #7b2cbf; margin-top: 30px;'>
        💡 Nasıl Kullanılır:<br>
        1. Add sekmesinden HSV değerlerini ayarlayın<br>
        2. Saved Settings'den preset seçin<br>
        3. Run/Stop sekmesinden video seçip START!<br>
        4. Desktop pet'iniz hazır! 🎉
        </p>
        <p style='font-size: 14px; color: #7b2cbf; margin-top: 30px;'>
        Version 1.0<br>
        Built with PyQt5 & OpenCV<br>
        💜 Developed by @hudulovhamzat0 on Github
        </p>
        </div>
        """)
        info.setAlignment(Qt.AlignCenter)
        info.setWordWrap(True)
        
        layout.addWidget(title)
        layout.addWidget(info)
        layout.addStretch()
        
        self.setLayout(layout)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎭 Desktop Pet - Anime Companion")
        self.setGeometry(100, 100, 1000, 700)
        
        self.desktop_pet = None
        
        # Set dark purple theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0f0f1e;
            }
            QTabWidget::pane {
                border: 2px solid #7b2cbf;
                border-radius: 8px;
                background-color: #0f0f1e;
            }
            QTabBar::tab {
                background-color: #1a1a2e;
                color: #9d4edd;
                padding: 12px 24px;
                margin: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #7b2cbf;
                color: white;
            }
            QTabBar::tab:hover {
                background-color: #5a189a;
                color: white;
            }
        """)
        
        # Create tab widget
        self.tabs = QTabWidget()
        
        # Create widgets
        self.control_panel = ControlPanel()
        self.saved_settings = SavedSettingsWidget()
        self.add_preset = AddPresetWidget()
        self.about = AboutWidget()
        
        # Connect signals
        self.control_panel.start_pet.connect(self.start_desktop_pet)
        self.control_panel.stop_pet.connect(self.stop_desktop_pet)
        self.control_panel.update_pet_scale.connect(self.update_pet_scale)
        self.control_panel.update_pet_opacity.connect(self.update_pet_opacity)
        self.saved_settings.preset_selected.connect(self.control_panel.set_preset)
        self.add_preset.preset_saved.connect(self.saved_settings.refresh_gallery)
        
        # Add tabs
        self.tabs.addTab(self.control_panel, "▶ Run/Stop")
        self.tabs.addTab(self.saved_settings, "💾 Saved Settings")
        self.tabs.addTab(self.add_preset, "➕ Add")
        self.tabs.addTab(self.about, "ℹ About")
        
        self.setCentralWidget(self.tabs)
    
    def start_desktop_pet(self, video_path, hsv_values, scale, opacity):
        # Eğer zaten çalışan bir pet varsa kapat
        if self.desktop_pet:
            self.desktop_pet.close()
            self.desktop_pet = None
        
        # Yeni desktop pet oluştur
        self.desktop_pet = DesktopPet(video_path, hsv_values, scale, opacity)
        self.desktop_pet.show()
        
        # Pet boyutunu kaydet
        if self.desktop_pet.original_size:
            w, h = self.desktop_pet.original_size
            self.control_panel.pet_size = (int(w * scale), int(h * scale))
    
    def update_pet_scale(self, scale):
        if self.desktop_pet:
            self.desktop_pet.set_scale(scale)
            # Boyutu güncelle
            if self.desktop_pet.original_size:
                w, h = self.desktop_pet.original_size
                self.control_panel.pet_size = (int(w * scale), int(h * scale))
    
    def update_pet_opacity(self, opacity):
        if self.desktop_pet:
            self.desktop_pet.set_opacity(opacity)
    
    def stop_desktop_pet(self):
        if self.desktop_pet:
            self.desktop_pet.close()
            self.desktop_pet = None
    
    def closeEvent(self, event):
        # Ana pencere kapatılırken desktop pet'i de kapat
        if self.desktop_pet:
            self.desktop_pet.close()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
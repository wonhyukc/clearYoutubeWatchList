import sys
import json
import time
import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QSpinBox,
    QCheckBox,
    QMessageBox,
    QSystemTrayIcon,
    QMenu,
    QDialog,
    QTextBrowser,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon
import pyautogui as pa
import keyboard as kb


class DeleteWorker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)

    def __init__(self, x_gap, y_gap, delay, parent=None):
        super().__init__(parent)
        self.x_gap = x_gap
        self.y_gap = y_gap
        self.delay = delay
        self.is_running = True
        self.delete_count = 0
        self.start_time = None

    def run(self):
        self.start_time = time.time()
        while self.is_running:
            try:
                pos = pa.position()
                pa.click(pos)
                time.sleep(0.3)

                x = pos.x + self.x_gap
                y = pos.y + self.y_gap
                pa.click((x, y))
                pa.moveTo(pos)

                self.delete_count += 1
                self.progress.emit(self.delete_count)

                elapsed = time.time() - self.start_time
                speed = self.delete_count / elapsed if elapsed > 0 else 0
                self.status.emit(
                    f"삭제된 항목: {self.delete_count}개\n"
                    f"경과 시간: {int(elapsed)}초\n"
                    f"평균 속도: {speed:.1f}개/초"
                )

                time.sleep(self.delay)
            except Exception as e:
                self.status.emit(f"오류 발생: {str(e)}")
                self.is_running = False

    def stop(self):
        self.is_running = False


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("사용 방법")
        self.setGeometry(100, 100, 600, 400)

        layout = QVBoxLayout()

        help_text = QTextBrowser()
        help_text.setOpenExternalLinks(True)
        help_text.setHtml(
            """
        <h2>YouTube 시청 기록 삭제 도구 사용 방법</h2>
        
        <h3>1. YouTube 시청 기록 페이지 준비</h3>
        <ul>
            <li>YouTube 시청 기록 페이지를 왼쪽 모니터에 전체 화면으로 엽니다</li>
            <li><a href="https://www.youtube.com/feed/history">https://www.youtube.com/feed/history</a>에 접속합니다</li>
        </ul>
        
        <h3>2. 위치 설정</h3>
        <ul>
            <li>F8 키를 누릅니다</li>
            <li>첫 번째 위치: 삭제할 첫 번째 항목에 마우스를 두고 클릭합니다</li>
            <li>두 번째 위치: "삭제" 버튼에 마우스를 두고 클릭합니다</li>
            <li>설정이 완료되면 "설정이 완료되었습니다!" 메시지가 표시됩니다</li>
        </ul>
        
        <h3>3. 삭제 시작</h3>
        <ul>
            <li>F2 키를 누르면 삭제가 시작됩니다</li>
            <li>다시 F2를 누르면 삭제가 중지됩니다</li>
            <li>삭제 중에는 삭제된 항목 수와 속도가 표시됩니다</li>
        </ul>
        
        <h3>단축키</h3>
        <ul>
            <li>F8: 위치 설정</li>
            <li>F2: 삭제 시작/중지</li>
            <li>ESC: 프로그램 종료</li>
        </ul>
        
        <h3>주의사항</h3>
        <ul>
            <li>프로그램을 처음 실행할 때는 반드시 위치를 설정해야 합니다</li>
            <li>YouTube 페이지가 전체 화면이어야 정확하게 동작합니다</li>
            <li>삭제 중에는 마우스를 움직이지 마세요</li>
        </ul>
        """
        )

        layout.addWidget(help_text)

        close_button = QPushButton("닫기")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        self.setLayout(layout)


class YouTubeHistoryDeleter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.loadSettings()
        self.worker = None
        self.pos_list = []
        self.is_setup = False

        # 시스템 트레이 아이콘 설정
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("icon.png"))  # 아이콘 파일이 필요합니다
        self.createTrayMenu()

    def initUI(self):
        self.setWindowTitle("YouTube 시청 기록 삭제 도구")
        self.setGeometry(100, 100, 400, 500)

        # 메인 위젯과 레이아웃
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # 상태 표시 레이블
        self.status_label = QLabel("준비")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # 설정 섹션
        settings_group = QWidget()
        settings_layout = QVBoxLayout(settings_group)

        # 딜레이 설정
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("삭제 간격 (초):"))
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, 10)
        self.delay_spin.setValue(1)
        delay_layout.addWidget(self.delay_spin)
        settings_layout.addLayout(delay_layout)

        # 자동 시작 옵션
        self.auto_start_check = QCheckBox("프로그램 시작 시 자동으로 삭제 시작")
        settings_layout.addWidget(self.auto_start_check)

        layout.addWidget(settings_group)

        # 버튼 섹션
        button_layout = QHBoxLayout()

        self.setup_btn = QPushButton("위치 설정 (F8)")
        self.setup_btn.clicked.connect(self.setup_positions)
        button_layout.addWidget(self.setup_btn)

        self.start_btn = QPushButton("삭제 시작 (F2)")
        self.start_btn.clicked.connect(self.toggle_deletion)
        button_layout.addWidget(self.start_btn)

        # 도움말 버튼
        help_btn = QPushButton("사용 방법")
        help_btn.clicked.connect(self.show_help)
        button_layout.addWidget(help_btn)

        layout.addLayout(button_layout)

        # 진행 상황 표시
        self.progress_label = QLabel("0")
        self.progress_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.progress_label)

        # 단축키 설정
        self.setupShortcuts()

    def setupShortcuts(self):
        kb.add_hotkey("f8", self.setup_positions)
        kb.add_hotkey("f2", self.toggle_deletion)

    def createTrayMenu(self):
        tray_menu = QMenu()
        show_action = tray_menu.addAction("보이기")
        show_action.triggered.connect(self.show)
        quit_action = tray_menu.addAction("종료")
        quit_action.triggered.connect(self.close)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def setup_positions(self):
        if len(self.pos_list) < 2:
            pos = pa.position()
            self.pos_list.append(pos)
            self.status_label.setText(f"위치 {len(self.pos_list)} 저장됨: {pos}")

            if len(self.pos_list) == 2:
                self.x_gap = self.pos_list[1][0] - self.pos_list[0][0]
                self.y_gap = self.pos_list[1][1] - self.pos_list[0][1]
                self.is_setup = True
                self.status_label.setText("설정이 완료되었습니다!")
                self.saveSettings()

    def toggle_deletion(self):
        if not self.is_setup:
            QMessageBox.warning(self, "경고", "먼저 위치를 설정해주세요!")
            return

        if self.worker is None or not self.worker.is_running:
            self.start_deletion()
        else:
            self.stop_deletion()

    def start_deletion(self):
        self.worker = DeleteWorker(self.x_gap, self.y_gap, self.delay_spin.value())
        self.worker.progress.connect(self.updateProgress)
        self.worker.status.connect(self.updateStatus)
        self.worker.start()
        self.start_btn.setText("삭제 중지 (F2)")

    def stop_deletion(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
        self.start_btn.setText("삭제 시작 (F2)")

    def updateProgress(self, count):
        self.progress_label.setText(str(count))

    def updateStatus(self, status):
        self.status_label.setText(status)

    def saveSettings(self):
        settings = {
            "x_gap": self.x_gap,
            "y_gap": self.y_gap,
            "delay": self.delay_spin.value(),
            "auto_start": self.auto_start_check.isChecked(),
        }
        with open("settings.json", "w") as f:
            json.dump(settings, f)

    def loadSettings(self):
        try:
            with open("settings.json", "r") as f:
                settings = json.load(f)
                self.x_gap = settings.get("x_gap", 0)
                self.y_gap = settings.get("y_gap", 0)
                self.delay_spin.setValue(settings.get("delay", 1))
                self.auto_start_check.setChecked(settings.get("auto_start", False))
                self.is_setup = True
        except FileNotFoundError:
            pass

    def closeEvent(self, event):
        self.saveSettings()
        self.stop_deletion()
        event.accept()

    def show_help(self):
        dialog = HelpDialog(self)
        dialog.exec_()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = YouTubeHistoryDeleter()
    ex.show()
    sys.exit(app.exec_())

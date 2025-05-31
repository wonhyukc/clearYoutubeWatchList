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
    QTabWidget,
    QScrollArea,
    QFrame,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QPoint
from PyQt5.QtGui import QIcon
import pyautogui as pa
import keyboard as kb


class DeleteWorker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)

    def __init__(self, base_pos, x_gap, y_gap, delay, parent=None):
        super().__init__(parent)
        self.base_position = base_pos  # F8로 설정된 첫 번째 위치
        self.x_gap = x_gap
        self.y_gap = y_gap
        self.delay = delay
        self.is_running = True
        self.delete_count = 0
        self.start_time = None

    def run(self):
        self.start_time = time.time()
        print("Debug: 삭제 작업 시작")
        print(f"Debug: 기준 위치 (F8 설정값): {self.base_position}")
        print(f"Debug: X 간격={self.x_gap}, Y 간격={self.y_gap}, 딜레이={self.delay}초")

        while self.is_running:
            try:
                if not self.is_running:
                    break

                # 첫 번째 위치 클릭 (기준 위치로 이동 후 클릭)
                print(f"Debug: 첫 번째 클릭 (목표): {self.base_position}")
                pa.moveTo(self.base_position)
                pa.click()
                time.sleep(0.3)

                if not self.is_running:
                    break

                # 두 번째 위치 클릭 (기준 위치 기준으로 계산)
                target_x = self.base_position.x + self.x_gap
                target_y = self.base_position.y + self.y_gap
                target_pos_2 = (target_x, target_y)
                print(
                    f"Debug: 두 번째 클릭 (목표): {target_pos_2} (간격: x={self.x_gap}, y={self.y_gap})"
                )
                pa.click(target_pos_2)
                pa.moveTo(self.base_position)  # 기준 위치로 마우스 이동

                self.delete_count += 1
                self.progress.emit(self.delete_count)

                elapsed = time.time() - self.start_time
                speed = self.delete_count / elapsed if elapsed > 0 else 0
                status_text = (
                    f"삭제된 항목: {self.delete_count}개\n"
                    f"경과 시간: {int(elapsed)}초\n"
                    f"평균 속도: {speed:.1f}개/초"
                )
                # print(f"Debug: {status_text}") # 상태 표시는 GUI로 충분하므로 로그 간소화
                self.status.emit(status_text)

                if not self.is_running:
                    break

                # print(f"Debug: {self.delay}초 대기") # 딜레이 로그 간소화
                time.sleep(self.delay)
            except Exception as e:
                error_msg = f"오류 발생: {str(e)}"
                print(f"Debug: {error_msg}")
                self.status.emit(error_msg)
                self.is_running = False
                break

    def stop(self):
        print("Debug: 작업 중지 요청")
        self.is_running = False
        self.wait()


class DebugWorker(QThread):
    position_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.is_running = True

    def run(self):
        while self.is_running:
            pos = pa.position()
            self.position_signal.emit(f"마우스 위치: x={pos.x}, y={pos.y}")
            time.sleep(0.1)

    def stop(self):
        self.is_running = False


class YouTubeHistoryDeleter(QMainWindow):
    def __init__(self):
        super().__init__()
        print("Debug: 프로그램 시작")
        self.loaded_base_pos = None
        self.loaded_x_gap = None
        self.loaded_y_gap = None
        self.can_load_previous_coords = False

        self.initUI()
        self.loadSettings()

        # loadSettings 이후에 버튼 상태 업데이트
        if self.can_load_previous_coords:
            self.load_prev_coords_btn.setEnabled(True)

        self.worker = None
        self.debug_worker = None
        self.pos_list = []
        self.is_setup = False
        self.is_debugging = True
        self.start_debug()  # 디버그 모드 자동 시작

        # 시스템 트레이 아이콘 설정
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("icon.png"))
        self.createTrayMenu()

    def initUI(self):
        self.setWindowTitle("YouTube 시청 기록 삭제 도구")
        self.setGeometry(100, 100, 800, 800)

        # 메인 위젯과 레이아웃
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # 스크롤 영역 생성
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # 스크롤 영역의 내용 위젯
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        # 상태 표시 레이블
        self.status_label = QLabel("준비")
        self.status_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(self.status_label)

        # 디버그 정보 표시 레이블
        self.debug_label = QLabel("디버그 정보")
        self.debug_label.setAlignment(Qt.AlignLeft)
        self.debug_label.setStyleSheet(
            "QLabel { background-color: #f0f0f0; padding: 5px; }"
        )
        content_layout.addWidget(self.debug_label)

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

        content_layout.addWidget(settings_group)

        # 버튼 섹션
        button_layout = QHBoxLayout()

        self.setup_btn = QPushButton("위치1 설정 (F8)")
        self.setup_btn.clicked.connect(self.setup_first_position)
        button_layout.addWidget(self.setup_btn)

        self.setup_second_btn = QPushButton("위치2 설정 (F9)")
        self.setup_second_btn.clicked.connect(self.setup_second_position)
        button_layout.addWidget(self.setup_second_btn)

        self.load_prev_coords_btn = QPushButton("이전 좌표 사용 (F6)")
        self.load_prev_coords_btn.clicked.connect(self.load_previous_coordinates)
        self.load_prev_coords_btn.setEnabled(False)
        button_layout.addWidget(self.load_prev_coords_btn)

        self.start_btn = QPushButton("삭제 시작 (F2)")
        self.start_btn.clicked.connect(self.toggle_deletion)
        button_layout.addWidget(self.start_btn)

        content_layout.addLayout(button_layout)

        # 진행 상황 표시
        self.progress_label = QLabel("0")
        self.progress_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(self.progress_label)

        # 구분선
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        content_layout.addWidget(line)

        # 사용 방법 섹션
        help_text = QTextBrowser()
        help_text.setOpenExternalLinks(True)
        help_text.setHtml(
            """
        <h2>사용 방법</h2>
        
        <h3>1. YouTube 시청 기록 페이지 준비</h3>
        <ul>
            <li>YouTube 시청 기록 페이지를 왼쪽 모니터에 전체 화면으로 엽니다</li>
            <li><a href="https://www.youtube.com/feed/history">https://www.youtube.com/feed/history</a>에 접속합니다</li>
        </ul>
        
        <h3>2. 위치 설정</h3>
        <ul>
            <li><b>F8:</b> 첫 번째 위치 (삭제할 항목의 메뉴 버튼) 설정</li>
            <li><b>F9:</b> 두 번째 위치 (나타나는 메뉴의 '삭제' 항목) 설정</li>
            <li><b>F6:</b> (선택 사항) 이전에 저장된 좌표 불러오기 (저장된 좌표가 있을 경우 활성화)</li>
            <li>설정이 완료되면 "설정이 완료되었습니다!" 메시지가 표시됩니다</li>
        </ul>
        
        <h3>3. 삭제 시작</h3>
        <ul>
            <li><b>F2:</b> 삭제 시작/중지</li>
            <li><b>F4:</b> 프로그램 종료</li>
            <li>삭제 중에는 삭제된 항목 수와 속도가 표시됩니다</li>
        </ul>
        
        <h3>주의사항</h3>
        <ul>
            <li>프로그램을 처음 실행하거나 F6을 사용하지 않을 경우, 반드시 F8, F9로 위치를 설정해야 합니다</li>
            <li>YouTube 페이지가 전체 화면이어야 정확하게 동작합니다</li>
            <li>삭제 중에는 마우스를 움직이지 마세요</li>
            <li>프로그램을 종료할 때는 F4 키를 사용하세요</li>
        </ul>

        <h3>문제 해결</h3>
        <ul>
            <li><b>위치 설정이 안 되는 경우:</b> F8, F9를 다시 눌러 설정 / YouTube 페이지 전체 화면 확인</li>
            <li><b>삭제가 안 되는 경우:</b> 위치 설정 확인 / YouTube 페이지 변경 여부 확인</li>
            <li><b>프로그램 응답 없음:</b> F4로 종료 후 재시작 / 작업 관리자에서 Python 프로세스 종료</li>
        </ul>
        """
        )

        content_layout.addWidget(help_text)

        # 스크롤 영역에 내용 위젯 설정
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        # 단축키 설정
        self.setupShortcuts()

    def setupShortcuts(self):
        kb.add_hotkey("f8", self.setup_first_position)
        kb.add_hotkey("f9", self.setup_second_position)
        kb.add_hotkey("f6", self.load_previous_coordinates)
        kb.add_hotkey("f2", self.toggle_deletion)
        kb.add_hotkey("f4", self.force_quit)

    def createTrayMenu(self):
        tray_menu = QMenu()
        show_action = tray_menu.addAction("보이기")
        show_action.triggered.connect(self.show)
        quit_action = tray_menu.addAction("종료")
        quit_action.triggered.connect(self.close)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def setup_positions(self):
        pos = pa.position()
        self.pos_list.append(pos)
        status_text = f"위치 {len(self.pos_list)} 저장됨: {pos}"
        print(f"Debug: {status_text}")
        self.status_label.setText(status_text)

        if self.is_debugging:
            debug_text = (
                f"마우스 위치: x={pos.x}, y={pos.y}\n"
                f"현재 설정된 위치: {self.pos_list}\n"
                f"설정 완료: {self.is_setup}\n"
                f"저장된 위치 수: {len(self.pos_list)}"
            )
            print(f"Debug: {debug_text}")
            self.debug_label.setText(debug_text)

        if len(self.pos_list) == 2:
            self.x_gap = self.pos_list[1][0] - self.pos_list[0][0]
            self.y_gap = self.pos_list[1][1] - self.pos_list[0][1]
            self.is_setup = True
            status_text = "설정이 완료되었습니다!"
            print(f"Debug: {status_text}")
            print(f"Debug: X 간격={self.x_gap}, Y 간격={self.y_gap}")
            print(f"Debug: 첫 번째 위치={self.pos_list[0]}")
            print(f"Debug: 두 번째 위치={self.pos_list[1]}")
            self.status_label.setText(status_text)
            self.saveSettings()

            if self.is_debugging:
                debug_text = (
                    f"마우스 위치: x={pos.x}, y={pos.y}\n"
                    f"현재 설정된 위치: {self.pos_list}\n"
                    f"설정 완료: {self.is_setup}\n"
                    f"저장된 위치 수: {len(self.pos_list)}\n"
                    f"X 간격: {self.x_gap}\n"
                    f"Y 간격: {self.y_gap}"
                )
                print(f"Debug: {debug_text}")
                self.debug_label.setText(debug_text)

    def setup_first_position(self):
        self.pos_list = []  # 위치 초기화
        self.is_setup = False
        self.setup_positions()

    def setup_second_position(self):
        if len(self.pos_list) == 1:  # 첫 번째 위치가 설정된 경우에만
            self.setup_positions()
        else:
            self.status_label.setText("먼저 F8로 첫 번째 위치를 설정해주세요!")

    def toggle_deletion(self):
        if not self.is_setup:
            msg = "먼저 위치를 설정해주세요!"
            print(f"Debug: {msg}")
            QMessageBox.warning(self, "경고", msg)
            return

        if self.worker is None or not self.worker.is_running:
            print("Debug: 삭제 시작")
            self.start_deletion()
        else:
            print("Debug: 삭제 중지")
            self.stop_deletion()

    def start_deletion(self):
        if not self.is_setup or not self.pos_list or len(self.pos_list) < 1:
            QMessageBox.warning(
                self, "경고", "먼저 F8, F9 또는 F6로 위치를 설정해주세요!"
            )
            return

        base_pos_for_worker = self.pos_list[0]  # pyautogui.Point 객체여야 함
        print(
            f"Debug: 삭제 작업자 시작 (딜레이: {self.delay_spin.value()}초, 기준위치: {base_pos_for_worker})"
        )
        self.worker = DeleteWorker(
            base_pos_for_worker, self.x_gap, self.y_gap, self.delay_spin.value()
        )
        self.worker.progress.connect(self.updateProgress)
        self.worker.status.connect(self.updateStatus)
        self.worker.start()
        self.start_btn.setText("삭제 중지 (F2)")

    def stop_deletion(self):
        print("Debug: 삭제 작업자 중지")
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
            "delay": self.delay_spin.value(),
            "auto_start": self.auto_start_check.isChecked(),
        }
        if self.is_setup and self.pos_list and len(self.pos_list) > 0:
            # self.pos_list[0]은 pyautogui.Point 객체일 수 있음
            base_pos = self.pos_list[0]
            settings["base_pos_x"] = base_pos.x
            settings["base_pos_y"] = base_pos.y
            settings["x_gap"] = self.x_gap
            settings["y_gap"] = self.y_gap
            print(
                f"Debug: 설정 저장 - base_pos=({base_pos.x},{base_pos.y}), x_gap={self.x_gap}, y_gap={self.y_gap}"
            )

        with open("settings.json", "w") as f:
            json.dump(settings, f)

    def loadSettings(self):
        try:
            with open("settings.json", "r") as f:
                settings = json.load(f)
                self.delay_spin.setValue(settings.get("delay", 1))
                self.auto_start_check.setChecked(settings.get("auto_start", False))

                base_x = settings.get("base_pos_x")
                base_y = settings.get("base_pos_y")
                x_g = settings.get("x_gap")
                y_g = settings.get("y_gap")

                if (
                    base_x is not None
                    and base_y is not None
                    and x_g is not None
                    and y_g is not None
                ):
                    self.loaded_base_pos = QPoint(base_x, base_y)  # QPoint로 저장
                    self.loaded_x_gap = x_g
                    self.loaded_y_gap = y_g
                    self.can_load_previous_coords = True
                    print(
                        f"Debug: 이전 설정 로드됨 - base_pos=({base_x},{base_y}), x_gap={x_g}, y_gap={y_g}"
                    )
                else:
                    self.can_load_previous_coords = False
                    print("Debug: 저장된 이전 좌표 정보 없음")
        except FileNotFoundError:
            print("Debug: settings.json 파일을 찾을 수 없습니다.")
            self.can_load_previous_coords = False
        except json.JSONDecodeError:
            print("Debug: settings.json 파일 분석 오류.")
            self.can_load_previous_coords = False

    def closeEvent(self, event):
        self.force_quit()
        event.accept()

    def start_debug(self):
        self.debug_worker = DebugWorker()
        self.debug_worker.position_signal.connect(self.update_debug_info)
        self.debug_worker.start()

    def stop_debug(self):
        if self.debug_worker:
            self.debug_worker.stop()
            self.debug_worker = None

    def update_debug_info(self, info):
        if self.is_debugging:
            pos = pa.position()
            new_text = (
                f"{info}\n"
                f"현재 설정된 위치: {self.pos_list}\n"
                f"설정 완료: {self.is_setup}\n"
                f"저장된 위치 수: {len(self.pos_list)}"
            )
            if self.is_setup:
                new_text += f"\nX 간격: {self.x_gap}\nY 간격: {self.y_gap}"
            self.debug_label.setText(new_text)

    def force_quit(self):
        print("Debug: 프로그램 강제 종료")
        if self.worker:
            self.worker.stop()
            self.worker = None
        if self.debug_worker:
            self.debug_worker.stop()
            self.debug_worker = None

        self.saveSettings()
        QApplication.quit()

    def load_previous_coordinates(self):
        if (
            self.can_load_previous_coords
            and self.loaded_base_pos
            and self.loaded_x_gap is not None
            and self.loaded_y_gap is not None
        ):
            base_x = self.loaded_base_pos.x()
            base_y = self.loaded_base_pos.y()

            # pyautogui.Point와 QPoint 간 호환을 위해 x, y 속성 직접 사용
            first_pos = pa.Point(x=base_x, y=base_y)
            second_pos_x = base_x + self.loaded_x_gap
            second_pos_y = base_y + self.loaded_y_gap
            second_pos = pa.Point(x=second_pos_x, y=second_pos_y)

            self.pos_list = [first_pos, second_pos]
            self.x_gap = self.loaded_x_gap
            self.y_gap = self.loaded_y_gap
            self.is_setup = True

            status_msg = f"이전 좌표 로드 완료: 위치1={first_pos}, 위치2={second_pos}, 간격=({self.x_gap}, {self.y_gap})"
            self.status_label.setText(status_msg)
            print(f"Debug: {status_msg}")
            if self.is_debugging:
                self.debug_label.setText(
                    f"이전 좌표 로드됨.\n기준 위치: {first_pos}\nX 간격: {self.x_gap}, Y 간격: {self.y_gap}"
                )
        else:
            msg = "저장된 이전 좌표가 없거나 유효하지 않습니다."
            self.status_label.setText(msg)
            QMessageBox.warning(self, "정보", msg)
            print(f"Debug: {msg}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = YouTubeHistoryDeleter()
    ex.show()
    sys.exit(app.exec_())

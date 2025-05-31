import sys
import json
import time
import os
import logging
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
    QTextBrowser,
    QScrollArea,
    QFrame,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon
import pyautogui as pa
import keyboard as kb

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# --- Constants ---
SETTINGS_FILE_NAME = "settings.json"
ICON_FILE_NAME = "icon.png"


# --- Worker Classes (상단으로 이동) ---
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
        self.wait()


class DeleteWorker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)

    def __init__(self, base_pos, x_gap, y_gap, delay, parent=None):
        super().__init__(parent)
        self.base_position = base_pos
        self.x_gap = x_gap
        self.y_gap = y_gap
        self.delay = delay
        self.is_running = True
        self.delete_count = 0
        self.start_time = None

    def run(self):
        self.start_time = time.time()
        logger.debug(
            f"삭제 작업 시작 - 기준: {self.base_position}, 간격: ({self.x_gap},{self.y_gap}), 딜레이: {self.delay}s"
        )
        while self.is_running:
            try:
                if not self.is_running:
                    break
                logger.debug(f"클릭1 목표: {self.base_position}")
                pa.moveTo(self.base_position)
                pa.click()
                time.sleep(0.3)
                if not self.is_running:
                    break
                target_x = self.base_position.x + self.x_gap
                target_y = self.base_position.y + self.y_gap
                target_pos_2 = pa.Point(target_x, target_y)  # pyautogui.Point로 생성
                logger.debug(
                    f"클릭2 목표: {target_pos_2} (간격: x={self.x_gap}, y={self.y_gap})"
                )
                pa.click(target_pos_2)
                pa.moveTo(self.base_position)
                self.delete_count += 1
                self.progress.emit(self.delete_count)
                elapsed = time.time() - self.start_time
                speed = self.delete_count / elapsed if elapsed > 0 else 0
                status_text = (
                    f"삭제된 항목: {self.delete_count}개\n"
                    f"경과 시간: {int(elapsed)}초\n"
                    f"평균 속도: {speed:.1f}개/초"
                )
                self.status.emit(status_text)
                if not self.is_running:
                    break
                time.sleep(self.delay)
            except Exception as e:
                error_msg = f"오류 발생: {str(e)}"
                logger.error(error_msg, exc_info=True)
                self.status.emit(error_msg)
                self.is_running = False
                break

    def stop(self):
        logger.debug("DeleteWorker 작업 중지 요청")
        self.is_running = False
        self.wait()


# --- Settings Manager Class ---
class SettingsManager:
    """설정 파일(JSON) 읽기 및 쓰기를 관리하는 클래스."""

    def __init__(self, filename=SETTINGS_FILE_NAME):
        self.filename = filename
        self.settings = {}
        self._load()

    def _load(self):
        """파일에서 설정을 로드합니다."""
        try:
            with open(self.filename, "r") as f:
                self.settings = json.load(f)
                logger.info(f"설정 로드 완료 from {self.filename}")
        except FileNotFoundError:
            logger.warning(f"{self.filename} 파일을 찾을 수 없음. 기본 설정 사용.")
            self.settings = {}  # 기본값은 호출하는 쪽에서 처리하거나 여기서 정의
        except json.JSONDecodeError as e:
            logger.error(f"{self.filename} 파일 분석 오류: {e}. 기본 설정 사용.")
            self.settings = {}

    def save(self, data_to_save):
        """주어진 데이터를 파일에 설정으로 저장합니다."""
        try:
            with open(self.filename, "w") as f:
                json.dump(data_to_save, f, indent=4)
                logger.info(f"설정 저장 완료 to {self.filename}")
        except Exception as e:
            logger.error(f"설정 저장 실패 - {e}", exc_info=True)

    def get(self, key, default=None):
        """설정 값을 가져옵니다. 없으면 기본값을 반환합니다."""
        return self.settings.get(key, default)


# --- Main Application Class ---
class YouTubeHistoryDeleter(QMainWindow):
    """YouTube 시청 기록 삭제 도구의 메인 애플리케이션 클래스."""

    def __init__(self):
        super().__init__()
        logger.info("프로그램 시작")

        self.settings_manager = SettingsManager()

        self.pos_list = []
        self.x_gap = 0
        self.y_gap = 0
        self.is_setup = False  # 좌표 설정 완료 여부
        self.is_debugging = True  # 디버그 모드 기본 ON

        self.worker = None
        self.debug_worker = None

        self.initUI()  # UI 요소 생성 및 초기화
        self._apply_loaded_settings()  # 로드된 설정 적용

        if self.is_debugging:
            self.start_debug()  # 디버그 모드 자동 시작

        self._setup_tray_icon()  # 트레이 아이콘 설정

    def initUI(self):
        """UI 요소들을 초기화하고 배치합니다."""
        self.setWindowTitle("YouTube 시청 기록 삭제 도구")
        self.setGeometry(100, 100, 800, 800)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        scroll_area = self._create_scroll_area()
        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        content_layout = QVBoxLayout(content_widget)

        self._create_status_labels(content_layout)
        self._create_settings_group(content_layout)
        self._create_control_buttons(content_layout)
        self._create_progress_label(content_layout)

        # 구분선
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        content_layout.addWidget(line)

        self._create_help_text_widget(content_layout)

        main_layout.addWidget(scroll_area)
        self._setup_shortcuts()  # 단축키 설정

    def _create_scroll_area(self) -> QScrollArea:
        """메인 스크롤 영역을 생성합니다."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        return scroll

    def _create_status_labels(self, parent_layout: QVBoxLayout):
        """상태 및 디버그 정보 레이블을 생성하여 레이아웃에 추가합니다."""
        self.status_label = QLabel("준비")
        self.status_label.setAlignment(Qt.AlignCenter)
        parent_layout.addWidget(self.status_label)

        self.debug_label = QLabel("디버그 정보")
        self.debug_label.setAlignment(Qt.AlignLeft)
        self.debug_label.setStyleSheet(
            "QLabel { background-color: #f0f0f0; padding: 5px; }"
        )
        parent_layout.addWidget(self.debug_label)

    def _create_settings_group(self, parent_layout: QVBoxLayout):
        """딜레이 및 자동 시작 설정 UI 그룹을 생성하여 레이아웃에 추가합니다."""
        settings_group = QWidget()
        settings_layout = QVBoxLayout(settings_group)

        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("삭제 간격 (초):"))
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, 10)
        self.delay_spin.setValue(1)
        delay_layout.addWidget(self.delay_spin)
        settings_layout.addLayout(delay_layout)

        self.auto_start_check = QCheckBox("프로그램 시작 시 자동으로 삭제 시작")
        settings_layout.addWidget(self.auto_start_check)
        parent_layout.addWidget(settings_group)

    def _create_control_buttons(self, parent_layout: QVBoxLayout):
        """제어 버튼(위치 설정, 삭제 시작/중지)들을 생성하여 레이아웃에 추가합니다."""
        button_layout = QHBoxLayout()
        self.setup_btn = QPushButton("위치1 설정 (F8)")
        self.setup_btn.clicked.connect(self.setup_first_position)
        button_layout.addWidget(self.setup_btn)
        self.setup_second_btn = QPushButton("위치2 설정 (F9)")
        self.setup_second_btn.clicked.connect(self.setup_second_position)
        button_layout.addWidget(self.setup_second_btn)
        self.start_btn = QPushButton("삭제 시작 (F2)")
        self.start_btn.clicked.connect(self.toggle_deletion)
        button_layout.addWidget(self.start_btn)
        parent_layout.addLayout(button_layout)

    def _create_progress_label(self, parent_layout: QVBoxLayout):
        """삭제 진행 상황 레이블을 생성하여 레이아웃에 추가합니다."""
        self.progress_label = QLabel("0")
        self.progress_label.setAlignment(Qt.AlignCenter)
        parent_layout.addWidget(self.progress_label)

    def _create_help_text_widget(self, parent_layout: QVBoxLayout):
        """도움말 텍스트 위젯을 생성하여 레이아웃에 추가합니다."""
        help_text_widget = QTextBrowser()
        help_text_widget.setOpenExternalLinks(True)
        help_text_widget.setHtml(
            """
        <h2>사용 방법</h2>
        <h3>1. YouTube 시청 기록 페이지 준비</h3>
        <ul>
            <li>YouTube 시청 기록 페이지를 왼쪽 모니터에 전체 화면으로 엽니다</li>
            <li><a href="https://www.youtube.com/feed/history">https://www.youtube.com/feed/history</a>에 접속합니다</li>
        </ul>
        <h3>2. 위치 설정</h3>
        <ul>
            <li><b>F8:</b> 첫 번째 위치 (삭제할 항목의 메뉴 버튼)를 마우스로 클릭하여 설정합니다.</li>
            <li><b>F9:</b> 두 번째 위치 (나타나는 메뉴의 '삭제' 항목)를 마우스로 클릭하여 설정합니다.</li>
            <li>설정이 완료되면 "설정이 완료되었습니다!" 메시지가 표시됩니다.</li>
            <li>또는, 이전에 저장된 설정이 있다면 프로그램 시작 시 자동으로 불러옵니다.</li>
        </ul>
        <h3>3. 삭제 시작/중지</h3>
        <ul>
            <li><b>F2:</b> 삭제 작업을 시작하거나 중지합니다.</li>
        </ul>
        <h3>4. 프로그램 종료</h3>
        <ul>
            <li><b>F4:</b> 프로그램을 종료합니다.</li>
        </ul>
        <h3>주의사항</h3>
        <ul>
            <li>위치를 처음 설정할 때는 반드시 F8, F9 순서로 설정해야 합니다.</li>
            <li>YouTube 페이지가 전체 화면이어야 정확하게 동작합니다.</li>
            <li>삭제 중에는 마우스를 움직이지 마세요.</li>
        </ul>
        <h3>문제 해결</h3>
        <ul>
            <li><b>위치 설정이 안 되는 경우:</b> F8, F9를 다시 눌러 설정 / YouTube 페이지 전체 화면 확인</li>
            <li><b>삭제가 안 되는 경우:</b> 위치 설정 확인 / YouTube 페이지 변경 여부 확인</li>
            <li><b>프로그램 응답 없음:</b> F4로 종료 후 재시작 / 작업 관리자에서 Python 프로세스 종료</li>
        </ul>
        """
        )
        parent_layout.addWidget(help_text_widget)

    def _apply_loaded_settings(self):
        """SettingsManager를 통해 로드된 설정을 애플리케이션 상태에 적용합니다."""
        self.delay_spin.setValue(self.settings_manager.get("delay", 1))
        self.auto_start_check.setChecked(self.settings_manager.get("auto_start", False))

        pos1_x = self.settings_manager.get("pos1_x")
        pos1_y = self.settings_manager.get("pos1_y")
        x_g = self.settings_manager.get("x_gap")
        y_g = self.settings_manager.get("y_gap")

        if (
            pos1_x is not None
            and pos1_y is not None
            and x_g is not None
            and y_g is not None
        ):
            first_pos = pa.Point(pos1_x, pos1_y)
            second_pos = pa.Point(pos1_x + x_g, pos1_y + y_g)
            self.pos_list = [first_pos, second_pos]
            self.x_gap = x_g
            self.y_gap = y_g
            self.is_setup = True
            logger.info(
                f"이전 설정 적용됨 - pos1={first_pos}, x_gap={x_g}, y_gap={y_g}"
            )
            self._update_status_and_debug_labels_after_config_change()
        else:
            self.is_setup = False
            logger.info("저장된 이전 좌표 정보 없음. 새로 설정 필요.")
            self._update_status_and_debug_labels_after_config_change()

    def _save_current_settings(self):
        """현재 애플리케이션 설정을 SettingsManager를 통해 저장합니다."""
        current_settings = {
            "delay": self.delay_spin.value(),
            "auto_start": self.auto_start_check.isChecked(),
        }
        if self.is_setup and self.pos_list and len(self.pos_list) == 2:
            current_settings["pos1_x"] = self.pos_list[0].x
            current_settings["pos1_y"] = self.pos_list[0].y
            current_settings["x_gap"] = self.x_gap
            current_settings["y_gap"] = self.y_gap
            logger.debug(
                f"저장할 설정 - pos1=({self.pos_list[0].x},{self.pos_list[0].y}), x_gap={self.x_gap}, y_gap={self.y_gap}"
            )
        else:
            logger.debug(f"저장할 설정 - 위치 정보 없음 (is_setup: {self.is_setup})")

        self.settings_manager.save(current_settings)

    def _setup_shortcuts(self):
        """키보드 단축키를 설정합니다."""
        kb.add_hotkey("f8", self.setup_first_position)
        kb.add_hotkey("f9", self.setup_second_position)
        kb.add_hotkey("f2", self.toggle_deletion)
        kb.add_hotkey("f4", self.force_quit)

    def _setup_tray_icon(self):
        """시스템 트레이 아이콘을 설정합니다."""
        self.tray_icon = QSystemTrayIcon(self)
        if os.path.exists(ICON_FILE_NAME):
            self.tray_icon.setIcon(QIcon(ICON_FILE_NAME))
        else:
            logger.warning(f"{ICON_FILE_NAME} 파일 없음. 기본 아이콘 사용")

        tray_menu = QMenu()
        show_action = tray_menu.addAction("보이기/숨기기")
        show_action.triggered.connect(self._toggle_window_visibility)
        quit_action = tray_menu.addAction("종료")
        quit_action.triggered.connect(self.force_quit)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def _toggle_window_visibility(self):
        """창 보이기/숨기기 상태를 토글합니다."""
        if self.isVisible():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow()

    def _update_status_and_debug_labels_after_config_change(self):
        """좌표 설정 변경 또는 로드 후 상태 및 디버그 레이블을 업데이트합니다."""
        if self.is_setup and self.pos_list and len(self.pos_list) == 2:
            pos1_text = f"위치1: {self.pos_list[0]}"
            gap_text = f"간격: (X: {self.x_gap}, Y: {self.y_gap})"
            current_status_msg = f"설정 완료: {pos1_text}, {gap_text}"
            self.status_label.setText(current_status_msg)
            if self.is_debugging:
                self.debug_label.setText(f"현재 설정:\n{pos1_text}\n{gap_text}")
        else:
            self.status_label.setText("준비 (F8, F9로 위치 설정 필요)")
            if self.is_debugging:
                self.debug_label.setText("디버그 모드 ON. F8/F9로 위치를 설정하세요.")
        logger.debug(f"UI 상태 레이블 업데이트: {self.status_label.text()}")

    def setup_first_position(self):
        """F8: 첫 번째 위치를 설정합니다."""
        self.pos_list = []
        self.is_setup = False
        current_mouse_pos = pa.position()
        self.pos_list.append(pa.Point(current_mouse_pos.x, current_mouse_pos.y))
        self._update_status_and_debug_labels_after_config_change()
        logger.debug(f"위치 1 저장됨: {self.pos_list[0]}")

    def setup_second_position(self):
        """F9: 두 번째 위치를 설정하고, 유효하면 전체 설정을 완료합니다."""
        if len(self.pos_list) == 1:
            current_mouse_pos = pa.position()
            self.pos_list.append(pa.Point(current_mouse_pos.x, current_mouse_pos.y))
            self.x_gap = self.pos_list[1].x - self.pos_list[0].x
            self.y_gap = self.pos_list[1].y - self.pos_list[0].y
            self.is_setup = True
            logger.info(
                f"위치 2 저장 및 설정 완료! 위치1={self.pos_list[0]}, 위치2={self.pos_list[1]}, 간격=({self.x_gap},{self.y_gap})"
            )
            self._update_status_and_debug_labels_after_config_change()
            self._save_current_settings()
        else:
            msg = "먼저 F8로 첫 번째 위치를 설정해주세요!"
            self.status_label.setText(msg)
            QMessageBox.warning(self, "경고", msg)
            logger.warning(msg)

    def start_debug(self):
        """디버그 정보 출력을 위한 Worker를 시작합니다."""
        if self.debug_worker is None or not self.debug_worker.isRunning():
            self.debug_worker = DebugWorker()
            self.debug_worker.position_signal.connect(
                self._update_debug_label_continuous
            )
            self.debug_worker.start()
            logger.info("디버그 워커 시작")

    def stop_debug(self):
        """디버그 정보 출력 Worker를 중지합니다."""
        if self.debug_worker:
            self.debug_worker.stop()
            self.debug_worker = None
            logger.info("디버그 워커 중지")

    def _update_debug_label_continuous(self, mouse_pos_info_from_worker):
        """DebugWorker로부터 지속적으로 마우스 위치를 받아 디버그 레이블을 업데이트합니다."""
        if not self.is_debugging:
            return

        current_config_info = ""
        if self.is_setup and self.pos_list and len(self.pos_list) == 2:
            current_config_info = f"설정된 위치1: {self.pos_list[0]}\n설정된 간격: (X:{self.x_gap}, Y:{self.y_gap})\n"
        elif self.pos_list and len(self.pos_list) == 1:
            current_config_info = (
                f"설정된 위치1: {self.pos_list[0]}\n위치2 설정 대기 중...\n"
            )
        else:
            current_config_info = "위치 설정 안됨 (F8, F9 필요)\n"

        self.debug_label.setText(
            f"{mouse_pos_info_from_worker}\n{current_config_info}---------------------"
        )

    def toggle_deletion(self):
        """F2: 삭제 작업을 시작하거나 중지합니다."""
        if not self.is_setup:
            msg = "먼저 위치를 설정해주세요 (F8, F9 또는 이전 설정 로드)"
            logger.warning(msg)
            QMessageBox.warning(self, "경고", msg)
            return

        if self.worker is None or not self.worker.is_running:
            logger.info("삭제 시작 요청")
            self._start_deletion_worker()
            self.start_btn.setText("삭제 중지 (F2)")
        else:
            logger.info("삭제 중지 요청")
            self._stop_deletion_worker()
            self.start_btn.setText("삭제 시작 (F2)")

    def _start_deletion_worker(self):
        """삭제 작업을 수행하는 DeleteWorker를 시작합니다."""
        if not self.is_setup or not self.pos_list or len(self.pos_list) < 1:
            QMessageBox.warning(self, "경고", "위치가 설정되지 않았습니다.")
            return

        base_pos_for_worker = self.pos_list[0]
        logger.info(
            f"DeleteWorker 시작 - 딜레이: {self.delay_spin.value()}s, 기준위치: {base_pos_for_worker}"
        )
        self.worker = DeleteWorker(
            base_pos_for_worker, self.x_gap, self.y_gap, self.delay_spin.value()
        )
        self.worker.progress.connect(self.updateProgress)
        self.worker.status.connect(self.updateStatus)
        self.worker.finished.connect(
            self._on_delete_worker_finished
        )  # 작업 완료 시그널 연결
        self.worker.start()

    def _stop_deletion_worker(self):
        """실행 중인 DeleteWorker를 중지합니다."""
        if self.worker:
            self.worker.stop()  # is_running = False, 스레드 자체는 wait()로 종료 대기
            # self.worker = None # finished 시그널에서 None으로 처리

    def _on_delete_worker_finished(self):
        """DeleteWorker가 작업을 완료했을 때 호출됩니다."""
        logger.info("DeleteWorker 작업 완료됨 (finished 시그널 수신)")
        self.worker = None  # 작업자 참조 제거
        self.start_btn.setText("삭제 시작 (F2)")  # 버튼 상태 복원
        # 필요하다면 추가적인 상태 업데이트 (예: 최종 상태 메시지)
        if self.is_setup:  # 아직 설정이 유효하다면
            self.status_label.setText(
                f"삭제 작업 중단됨/완료됨. 마지막 삭제 수: {self.progress_label.text()}"
            )
        else:
            self.status_label.setText("삭제 작업 중단됨/완료됨.")

    def updateProgress(self, count):
        """DeleteWorker로부터 진행 상황(삭제된 항목 수)을 받아 UI에 업데이트합니다."""
        self.progress_label.setText(str(count))

    def updateStatus(self, status_msg_from_worker):
        """DeleteWorker로부터 상태 메시지를 받아 UI에 업데이트합니다."""
        self.status_label.setText(status_msg_from_worker)

    def force_quit(self):
        """F4 또는 트레이 메뉴: 프로그램을 강제 종료합니다."""
        logger.info("프로그램 강제 종료 요청")
        self.stop_debug()
        if self.worker:
            self.worker.stop()
            # self.worker.wait() # force_quit에서는 빠르게 종료. 스레드가 즉시 정리되지 않을 수 있음
        self._save_current_settings()  # 종료 전 설정 저장
        QApplication.instance().quit()

    def closeEvent(self, event):
        """창 닫기 버튼 클릭 시 호출됩니다."""
        # 현재는 F4와 동일하게 완전 종료
        logger.info("창 닫기 이벤트 발생. 강제 종료 실행.")
        self.force_quit()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = YouTubeHistoryDeleter()
    ex.show()
    sys.exit(app.exec_())

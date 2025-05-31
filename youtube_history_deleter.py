import pyautogui as pa
import keyboard as kb
import os
import time
from datetime import datetime


class YouTubeHistoryDeleter:
    def __init__(self):
        self.pos_list = []
        self.x_gap = 0
        self.y_gap = 0
        self.is_setup = False
        self.delete_count = 0
        self.start_time = None

    def clear_screen(self):
        os.system("cls" if os.name == "nt" else "clear")

    def print_status(self):
        self.clear_screen()
        print("=== YouTube 시청 기록 삭제 도구 ===")
        if not self.is_setup:
            print("\n[설정 단계]")
            print("1. F8: 첫 번째 위치 설정 (삭제할 항목)")
            print("2. F9: 두 번째 위치 설정 (삭제 버튼)")
        else:
            print("\n[삭제 단계]")
            print(f"삭제된 항목: {self.delete_count}개")
            if self.start_time:
                elapsed = time.time() - self.start_time
                print(f"경과 시간: {int(elapsed)}초")
                if self.delete_count > 0:
                    print(f"평균 속도: {self.delete_count/elapsed:.1f}개/초")
        print("\n[단축키]")
        print("F8: 첫 번째 위치 설정")
        print("F9: 두 번째 위치 설정")
        print("F2: 한 개 삭제")
        print("F3: 연속 삭제 시작/중지")
        print("ESC: 프로그램 종료")

    def setup_positions(self):
        pos = pa.position()
        print(f"\n위치 저장됨: {pos}")
        self.pos_list.append(pos)
        pa.click(pos)
        time.sleep(0.3)

        if len(self.pos_list) == 2:
            self.x_gap = self.pos_list[1][0] - self.pos_list[0][0]
            self.y_gap = self.pos_list[1][1] - self.pos_list[0][1]
            self.is_setup = True
            print("\n설정이 완료되었습니다!")
            print(f"위치 간격: x={self.x_gap}, y={self.y_gap}")
            time.sleep(1)

    def delete_item(self):
        if not self.is_setup:
            print("\n먼저 위치를 설정해주세요!")
            return

        pos = pa.position()
        pa.click(pos)
        time.sleep(0.3)

        x = pos.x + self.x_gap
        y = pos.y + self.y_gap
        pa.click((x, y))
        pa.moveTo(pos)

        self.delete_count += 1
        if self.delete_count == 1:
            self.start_time = time.time()

    def run(self):
        self.clear_screen()
        print("프로그램을 시작합니다...")
        print("YouTube 시청 기록 페이지를 왼쪽 모니터에 전체 화면으로 열어주세요.")
        time.sleep(2)

        continuous_delete = False

        while True:
            self.print_status()

            if kb.is_pressed("esc"):
                print("\n프로그램을 종료합니다...")
                break

            if kb.is_pressed("f8"):
                if len(self.pos_list) < 2:
                    self.setup_positions()
                time.sleep(0.3)

            if kb.is_pressed("f9"):
                if len(self.pos_list) < 2:
                    self.setup_positions()
                time.sleep(0.3)

            if kb.is_pressed("f2"):
                self.delete_item()
                time.sleep(0.3)

            if kb.is_pressed("f3"):
                continuous_delete = not continuous_delete
                print(f"\n연속 삭제: {'시작' if continuous_delete else '중지'}")
                time.sleep(0.3)

            if continuous_delete:
                self.delete_item()
                time.sleep(0.5)  # 연속 삭제 시 약간의 딜레이

            time.sleep(0.1)  # CPU 사용량 감소


if __name__ == "__main__":
    try:
        deleter = YouTubeHistoryDeleter()
        deleter.run()
    except KeyboardInterrupt:
        print("\n프로그램이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n오류가 발생했습니다: {e}")
    finally:
        print("\n프로그램을 종료합니다...")

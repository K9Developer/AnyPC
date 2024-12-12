import socket
from constants import Options, Events
from screen_share import ScreenShare
from utils import Connection, NetworkUtils
import pyautogui
import threading
import numpy as np
import cv2
import time
from ctypes import *
from terminal import Terminal

pyautogui.FAILSAFE = False

def get_fields(data: bytes, lengths: list[int]):
    fields = []
    for l in lengths:
        fields.append(data[:l])
        data = data[l:]
    return fields

def encode_image_diff(prev_img, img, diff=True):

    if diff == False:
        diff_bytes = bytearray()
        for y in range(img.shape[0]):
            for x in range(img.shape[1]):
                color = img[y, x]
                diff_bytes.extend(int(x).to_bytes(2, 'big'))
                diff_bytes.extend(int(y).to_bytes(2, 'big'))
                diff_bytes.extend(color)
        return bytes(diff_bytes)

    diff = cv2.absdiff(prev_img, img)
    changed_pixels = np.argwhere(diff > 0)

    diff_bytes = bytearray()
    for x, y, _ in changed_pixels:
        if 0 <= x < img.shape[1] and 0 <= y < img.shape[0]:
            color = img[y, x]
            diff_bytes.extend(int(x).to_bytes(2, 'big'))
            diff_bytes.extend(int(y).to_bytes(2, 'big'))
            diff_bytes.extend(color)

    return bytes(diff_bytes)

class ScreenControl:

    Terminal.info("Initializing screen control sockets...")
    mouse_update_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    screen_update_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    keyboard_update_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    mouse_update_socket.bind(("0.0.0.0", Options.MOUSE_UPDATE_PORT))
    screen_update_socket.bind(("0.0.0.0", Options.SCREEN_FRAME_PORT))
    keyboard_update_socket.bind(("0.0.0.0", Options.KEYBOARD_UPDATE_PORT))

    mouse_update_conn = Connection(mouse_update_socket, None)

    keyboard_update_socket.listen(1)
    screen_update_socket.listen(1)

    accepting_sc = False
    allow_control = True
    main_conn = None

    @staticmethod
    def start(main_conn: Connection):
        if not ScreenControl.accepting_sc: return
        ScreenControl.main_conn = main_conn

        ScreenControl.accepting_sc = False
        time.sleep(0.5)
        ScreenControl.accepting_sc = True

        ScreenControl.mouse_update_conn.encryption_manager = main_conn.encryption_manager

        mouse_thread = threading.Thread(target=ScreenControl.mouse_listener)
        screen_thread = threading.Thread(target=ScreenControl.screen_share)
        keyboard_thread = threading.Thread(target=ScreenControl.keyboard_listener)

        if ScreenControl.allow_control: mouse_thread.start()
        if ScreenControl.allow_control: keyboard_thread.start()
        screen_thread.start()



    @staticmethod
    def mouse_listener():

        STATE_SIZE = 1
        BUTTON_SIZE = 1
        X_SIZE = 2
        Y_SIZE = 2
        screen_size = pyautogui.size()
        holding = {
            "left": False,
            "right": False,
            "middle": False
        }

        # [state: 0: no action, 1: down, 2: scroll down, 3: scroll up][button: 0: no action, 1: left, 2: right, 3: middle][x][y]
        while ScreenControl.accepting_sc:
            recv = NetworkUtils.recieve_parts(ScreenControl.mouse_update_conn)
            if recv is None:
                continue

            _, raw_data = recv

            data = raw_data[1]
            fields = get_fields(data, [STATE_SIZE, BUTTON_SIZE, X_SIZE, Y_SIZE])
            mouse_state_id = int.from_bytes(fields[0])
            mouse_button_id = int.from_bytes(fields[1])
            mouse_pos_x_prec = int.from_bytes(fields[2])
            mouse_pos_y_prec = int.from_bytes(fields[3])

            mouse_x = int(mouse_pos_x_prec / Options.MOUSE_POSITION_ACCURACY * screen_size.width)
            mouse_y = int(mouse_pos_y_prec / Options.MOUSE_POSITION_ACCURACY * screen_size.height)

            mouse_button = None if mouse_button_id == 0 else ("left" if mouse_button_id == 1 else ("right" if mouse_button_id == 2 else "middle"))
            mouse_state = 'up' if mouse_state_id == 0 else ("down" if mouse_state_id == 1 else ("scroll_d" if mouse_state_id == 2 else "scroll_u"))

            if mouse_button is not None:
                if mouse_state == "down" and not holding[mouse_button]:
                    pyautogui.mouseDown(button=mouse_button, x=mouse_x, y=mouse_y)
                    holding[mouse_button] = True
                elif mouse_state == "up":
                    pyautogui.mouseUp(button=mouse_button, x=mouse_x, y=mouse_y)
                    holding[mouse_button] = False
                elif mouse_state == "scroll_d":
                    pyautogui.scroll(-30, x=mouse_x, y=mouse_y)
                elif mouse_state == "scroll_u":
                    pyautogui.scroll(30, x=mouse_x, y=mouse_y)

            pyautogui.moveTo(mouse_x, mouse_y, _pause=False)

        ScreenControl.mouse_update_conn.encryption_manager = None


    @staticmethod
    def keyboard_listener():
        soc, addr = ScreenControl.keyboard_update_socket.accept()
        client = Connection(soc, addr)
        client.encryption_manager = ScreenControl.main_conn.encryption_manager
        hold_map: dict[str, bool] = {}

        while ScreenControl.accepting_sc:
            recv = client.recieve_parts()
            if recv is None:
                ScreenControl.accepting_sc = False
                break

            data_parts, _ = recv

            key_state = int.from_bytes(data_parts[1])
            key = data_parts[2].decode()

            if key_state == 1 and key not in hold_map:
                Terminal.verbose(f"Recieved keyboard update: {key} is {key_state} being pressed")
                pyautogui.keyDown(key=key)
                hold_map[key] = True
            elif key_state == 2:
                Terminal.verbose(f"Recieved keyboard update: {key} is {key_state} being released")
                pyautogui.keyUp(key=key)
                if key in hold_map: del hold_map[key]
        
        client.disconnect()
        ScreenControl.main_conn = None

    @staticmethod
    def screen_share():
        soc, addr = ScreenControl.screen_update_socket.accept()
        client = Connection(soc, addr)
        client.encryption_manager = ScreenControl.main_conn.encryption_manager

        ss = ScreenShare()
        with ss as screen_share:
            frame_count = 0
            fps_timer = time.time()
            data_sent_per_sec = 0

            while ScreenControl.accepting_sc:
                packets = screen_share.get_frame()
                if packets is None:
                    Terminal.verbose(f"Got empty packets, skippig...")
                    continue
                    
                for packet in packets:
                    NetworkUtils.send_parts(client, [Events.ScreenFrame_Action.value, packet])
                    data_sent_per_sec += len(packet)

                frame_count += 1
                if time.time() - fps_timer >= 1.0:
                    kb_sent = data_sent_per_sec / 1024
                    Terminal.verbose(f"ScreenShare FPS: {frame_count} | KB/s: {kb_sent:.2f}")
                    frame_count = 0
                    data_sent_per_sec = 0
                    fps_timer = time.time()

        client.disconnect()
        ScreenControl.main_conn = None

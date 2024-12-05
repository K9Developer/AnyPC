import win32gui, win32ui, win32api
import numpy as np
from mss import mss
import cv2
from constants import Options
import av
from fractions import Fraction
from terminal import Terminal
import os

def get_cursor(hcursor):
    try:
        # Create a device context and bitmap
        hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
        hbmp = win32ui.CreateBitmap()
        hbmp.CreateCompatibleBitmap(hdc, 36, 36)
        hdc = hdc.CreateCompatibleDC()
        hdc.SelectObject(hbmp)
        hdc.DrawIcon((0, 0), hcursor)

        # Get bitmap info and bits
        bmpinfo = hbmp.GetInfo()
        bmpstr = hbmp.GetBitmapBits(True)

        # Convert the raw bitmap string into a NumPy array
        height, width = bmpinfo['bmHeight'], bmpinfo['bmWidth']
        raw_array = np.frombuffer(bmpstr, dtype=np.uint8)
        img_array = raw_array.reshape((height, width, 4))  # Assuming 32-bit with BGRA format

        # Drop the alpha channel (if desired, you can retain it)
        img_rgb = img_array[:, :, :3]

        # Release resources
        win32gui.DestroyIcon(hcursor)
        win32gui.DeleteObject(hbmp.GetHandle())
        hdc.DeleteDC()

        # Return the RGB image
        return img_rgb
    except:
        return None

def add_cursor_to_frame(frame):
    # Get cursor information
    flags, hcursor, (cx, cy) = win32gui.GetCursorInfo()
    cursor = get_cursor(hcursor)

    if cursor is None:
        return frame

    # Get cursor hotspot information
    hotspot_x, hotspot_y = win32gui.GetIconInfo(hcursor)[1:3]

    # Extract cursor dimensions
    ch, cw = cursor.shape[:2]

    # Adjust cursor position by subtracting hotspot offset
    cx = cx - hotspot_x
    cy = cy - hotspot_y

    # Ensure cursor is within frame boundaries
    fx = max(0, min(cx, frame.shape[1] - cw))
    fy = max(0, min(cy, frame.shape[0] - ch))

    # Create alpha mask based on cursor's intensity
    mask = (cursor[:, :, :3].max(axis=-1) > 10).astype(np.float32)[:, :, np.newaxis]

    # Blend cursor with the frame using the mask
    roi = frame[fy:fy+ch, fx:fx+cw]
    cursor_region = cursor[:, :, :3] * mask + roi * (1 - mask)
    frame[fy:fy+ch, fx:fx+cw] = cursor_region.astype(np.uint8)

    return frame

class ScreenShare:
    def __init__(self) -> None:
        Terminal.info("Initializing screen share codec...")

        self.sct = None
        self.monitor = None

        self.codec = av.CodecContext.create("h264", "w")
        self.codec.width = win32api.GetSystemMetrics(0)
        self.codec.height = win32api.GetSystemMetrics(1)
        self.codec.pix_fmt = 'yuv420p'
        self.codec.time_base = Fraction(1, int(Options.SCREEN_UPDATE_FRAME_RATE))
        self.codec.framerate = Options.SCREEN_UPDATE_FRAME_RATE
        self.codec.options = {
            'preset': 'ultrafast',
            'crf': '30',
            'tune': 'zerolatency',
            'threads': str(os.cpu_count()//2),
            'thread_type': 'frame',
            'rc-lookahead': '0',
            'fast_pskip': '1',
            'zerolatency': '1',
        }
        

        self.frame_count = 0

    def __enter__(self):
        Terminal.debug("Entering screen share context...")
        self.sct = mss()
        self.monitor = self.sct.monitors[1]
        while not self.codec.is_open:
            self.codec.open()
        Terminal.info("Codec is ready.")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        Terminal.debug("Exiting screen share context...")
        if self.sct:
            self.sct.close()
        try:
            for packet in self.codec.encode(None): # flush the codec
                pass
        except Exception:
            pass

    def __compress_and_encode_frame(self, frame):
        encoded_frame = av.VideoFrame.from_ndarray(frame, format='bgr24')
        encoded_frame.pts = self.frame_count
        self.frame_count += 1
        packets = self.codec.encode(encoded_frame)
        
        return packets

    def get_frame(self):
        try:
            if self.sct is None or self.monitor is None:
                return None

            screenshot = self.sct.grab(self.monitor)
            frame = np.array(screenshot)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            frame = add_cursor_to_frame(frame)

            new_width = int(frame.shape[1] * Options.SCREEN_SIZE_FACTOR)
            new_height = int(frame.shape[0] * Options.SCREEN_SIZE_FACTOR)
            frame = cv2.resize(frame, (new_width, new_height))

            av_packets = self.__compress_and_encode_frame(frame)

            to_send = []
            for packet in av_packets:
                packet_bytes = bytes(packet)
                to_send.append(packet_bytes)

            return to_send
        except Exception as e:
            return None

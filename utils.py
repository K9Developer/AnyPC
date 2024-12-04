from enum import Enum

import struct
import socket
import threading
from typing import Any

from constants import DataType, Error, Options, Events
from terminal import Terminal

def byte_length(i):
    return (i.bit_length() + 7) // 8

class Connection:
    def __init__(self, s: socket.socket, addr: tuple[str, int]) -> None:
        self.socket: socket.socket = s
        self.ip: str = addr[0]
        self.port: int = addr[1]

    def disconnect(self):
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
            self.socket.close()
        except Exception:
            pass

    def send(self, parts):
        NetworkUtils.send_parts(self.socket, parts)

    def send_event(self, event: Events, parts: list):
        self.send([event.value, *parts])

    def recieve_parts(self) -> tuple[list[bytes], list[bytes]] | None:
        return NetworkUtils.recieve_parts(self.socket)

    def send_success(self, msg: str):
        self.send([Events.OperationSuccess_Response.value])
        Terminal.success(msg)

    def send_failure(self, err: Error, msg: str, data: list = []):
        self.send([Events.OperationFailed_Response.value, err.value, *data])
        Terminal.error(msg)

    def __hash__(self):
        return hash((self.ip, self.port))

    def __eq__(self, other):
        if isinstance(other, Connection):
            return self.ip == other.ip and self.port == other.port
        return False

class Event:
    @staticmethod
    def handle(data: list[bytes], conn: Connection):
        pass

class NetworkUtils:
    actions: dict[Events, tuple[type[Event], DataType]] = {}
    event_thread_status: dict[Connection, Any] = {}

    @staticmethod
    def close(s: socket.socket):
        s.shutdown(socket.SHUT_RDWR)
        s.close()

    @staticmethod
    def __recieve_raw(src: socket.socket) -> bytes | None:
        data = None
        try:
            match src.type:
                case socket.SOCK_STREAM:
                    size_bytes = b""
                    for _ in range(Options.SIZE_OF_SIZE):
                        b = src.recv(1)
                        if b == b"": return None
                        size_bytes += b

                    size = struct.unpack(Options.SIZE_OF_SIZE_ENCODING_PROTOCOL, size_bytes)[0]

                    data_bytes = b""
                    for _ in range(size):
                        b = src.recv(1)
                        if b == b"": return None
                        data_bytes += b

                    data = data_bytes

                case socket.SOCK_DGRAM:
                    size_bytes, _ = src.recvfrom(Options.SIZE_OF_SIZE)
                    if size_bytes == b"": size_bytes = struct.pack(Options.SIZE_OF_SIZE_ENCODING_PROTOCOL, 0)
                    size = struct.unpack(Options.SIZE_OF_SIZE_ENCODING_PROTOCOL, size_bytes)[0]
                    data_bytes, _ = src.recvfrom(size)
                    data = data_bytes

        except Exception as e:
            Terminal.error("Error occured while recieving data " + str(e))

        return data

    @staticmethod
    def recieve_parts(src: socket.socket) -> tuple[list[bytes], list[bytes]] | None:
        raw_data = NetworkUtils.__recieve_raw(src)
        if raw_data is None: return None

        sep_parts = raw_data.split(Options.SEPERATOR)
        raw_parts = raw_data.split(Options.SEPERATOR, 1)

        return (sep_parts, raw_parts)

    @staticmethod
    def __send_raw(dst: socket.socket, bts: bytes, addr: tuple[str, int] | None):
        try:
            length_b = struct.pack(Options.SIZE_OF_SIZE_ENCODING_PROTOCOL, len(bts))
            match dst.type:
                case socket.SOCK_STREAM:
                    data = length_b + bts
                    dst.sendall(data)
                    return True
                case socket.SOCK_DGRAM:
                    if addr is None: return
                    dst.sendto(length_b, addr)
                    dst.sendto(bts, addr)
                    return True

            return False
        except Exception:
            return False

    @staticmethod
    def send_parts(dst: socket.socket, parts: list, add_sep = True, addr: tuple[str, int] | None = None):
        encoded_parts = [b if type(b) != str else b.encode() for b in parts]
        encoded_parts = [b if type(b) != int else int.to_bytes(b, byte_length(b)) for b in encoded_parts]
        bts = (Options.SEPERATOR if add_sep else b'').join(encoded_parts)
        return NetworkUtils.__send_raw(dst, bts, addr)

    @staticmethod
    def add_listener(event_id: Events, event: type[Event], data_type: DataType = DataType.Part):
        NetworkUtils.actions[event_id] = (event, data_type)

    @staticmethod
    def __callback_event(event_id: Events, data: list[Any], raw_data: list[bytes], conn: Connection):
        event = NetworkUtils.actions.get(event_id)

        if event == None:
            NetworkUtils.__callback_event(Events.UnknownEvent, [event_id, *data], [event_id.value.encode(), *data], conn)
            return

        event, data_type = event

        try:
            match data_type:
                case DataType.Part:
                    event.handle(data, conn)
                case DataType.Raw:
                    event.handle(raw_data, conn)
        except Exception as e:
            Terminal.error(f"Error occured while handling event {event_id}: {e}")

    @staticmethod
    def listen_for_events(client: Connection):
        def thread():
            while NetworkUtils.event_thread_status[client]:

                parts = client.recieve_parts()
                if parts == None:
                    NetworkUtils.__callback_event(Events.ConnectionClosed, [], [] ,client)
                    continue

                if len(parts) == 0: continue

                sep_parts, raw_parts = parts

                event_id_str: str = sep_parts[0].decode()
                event_id: Events = Events.from_val(event_id_str)

                NetworkUtils.__callback_event(event_id, sep_parts[1:], raw_parts[1:], client)

        NetworkUtils.event_thread_status[client] = True
        t = threading.Thread(target=thread, daemon=True)
        t.start()
        t.join()

    @staticmethod
    def remove_event_listener(conn: Connection):
        t = NetworkUtils.event_thread_status.get(conn)
        if t is None: return
        NetworkUtils.event_thread_status[conn] = False

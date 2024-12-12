from enum import Enum

import struct
import socket
import threading
from typing import Any

from constants import DataType, Error, Options, Events
from terminal import Terminal
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES, PKCS1_OAEP
import base64

def byte_length(i):
    return (i.bit_length() + 7) // 8

class Connection:
    def __init__(self, s: socket.socket, addr: tuple[str, int]) -> None:
        self.socket: socket.socket = s
        self.ip: str = addr[0]
        self.port: int = addr[1]
        self.secret: AES.EaxMode = None
        
    def initiate_key_switch(self):
        # try:
            k = RSA.generate(Options.RSA_KEY_SIZE)
            pub = k.publickey()
            private_key_obj = PKCS1_OAEP.new(k)
            public_key_bytes = pub.export_key(format='DER')
            Terminal.verbose("Created RSA keys")
            
            self.send_event(Events.PublicKeyTransfer_Action, [base64.b64encode(public_key_bytes)], encrypt=False)
            Terminal.verbose("Waiting for symetric key")
            
            parts, _ = self.recieve_parts(decrypt=False)
            if parts[0] == Events.SecretTransfer_Action.value.encode():
                nonce = private_key_obj.decrypt(base64.b64decode(parts[1]))
                secret_k = private_key_obj.decrypt(base64.b64decode(parts[2]))
                Terminal.verbose(f"Recieved secret: {'*'*len(secret_k)} {secret_k}")
                self.secret = AES.new(secret_k, AES.MODE_EAX, nonce=nonce)
                Terminal.verbose(f"Created AES secret.")
                self.send_success("Successfully achieved end-to-end encryption channel.")
            else:
                self.send_failure(Error.FailureToSendKey, "Failed to complete end-to-end encryption", encrypt=False)
        # except Exception:
        #     self.send_failure(Error.FailureToSendKey, "Failed to complete end-to-end encryption", encrypt=False)
        #     self.disconnect()

    def disconnect(self):
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
            self.socket.close()
        except Exception:
            pass

    def send(self, parts, encrypt=True):
        NetworkUtils.send_parts(self, parts, encrypt=encrypt)

    def send_event(self, event: Events, parts: list, encrypt=True):
        self.send([event.value, *parts], encrypt)

    def recieve_parts(self, decrypt = True) -> tuple[list[bytes], list[bytes]] | None:
        return NetworkUtils.recieve_parts(self, decrypt)

    def send_success(self, msg: str):
        self.send([Events.OperationSuccess_Response.value])
        Terminal.success(msg)

    def send_failure(self, err: Error, msg: str, data: list = [], encrypt=True):
        self.send([Events.OperationFailed_Response.value, err.value, *data], encrypt)
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
    def __recieve_raw(client: Connection, decrypt = True) -> bytes | None:
        data = None
        try:
            match client.socket.type:
                case socket.SOCK_STREAM:
                    size_bytes = b""
                    for _ in range(Options.SIZE_OF_SIZE):
                        b = client.socket.recv(1)
                        if b == b"": return None
                        size_bytes += b

                    size = struct.unpack(Options.SIZE_OF_SIZE_ENCODING_PROTOCOL, size_bytes)[0]

                    data_bytes = b""
                    for _ in range(size):
                        b = client.socket.recv(1)
                        if b == b"": return None
                        data_bytes += b

                    data = data_bytes

                case socket.SOCK_DGRAM:
                    size_bytes, _ = client.socket.recvfrom(Options.SIZE_OF_SIZE)
                    if size_bytes == b"": size_bytes = struct.pack(Options.SIZE_OF_SIZE_ENCODING_PROTOCOL, 0)
                    size = struct.unpack(Options.SIZE_OF_SIZE_ENCODING_PROTOCOL, size_bytes)[0]
                    data_bytes, _ = client.socket.recvfrom(size)
                    data = data_bytes

        except Exception as e:
            Terminal.error("Error occured while recieving data " + str(e))

        if not decrypt: return data

        cipher, tag = data.split(Options.SEPERATOR)
        derypted = client.secret.decrypt(base64.b64decode(cipher.decode()))
        try:
            client.secret.verify(base64.b64decode(tag.decode()))
        except ValueError:
            client.send_failure(Error.CouldntVerifyKey, "Key sent by client could not be verified, terminating connecting.")
            client.disconnect()

        return derypted

    @staticmethod
    def recieve_parts(client: Connection, decrypt = True) -> tuple[list[bytes], list[bytes]] | None:
        raw_data = NetworkUtils.__recieve_raw(client, decrypt)
        if raw_data is None: return None

        sep_parts = raw_data.split(Options.SEPERATOR)
        raw_parts = raw_data.split(Options.SEPERATOR, 1)

        return (sep_parts, raw_parts)

    @staticmethod
    def __send_raw(client: Connection, bts: bytes, encrypt = True):
        # try:

            if encrypt:    
                encrypted, tag = client.secret.encrypt_and_digest(bts)
                print(1, encrypted, client.secret)
                print(client.secret.decrypt(encrypted))
                encrypted = base64.b64encode(encrypted)
                tag = base64.b64encode(tag)
                length_b = struct.pack(Options.SIZE_OF_SIZE_ENCODING_PROTOCOL, len(encrypted+Options.SEPERATOR+tag))
            else:
                length_b = struct.pack(Options.SIZE_OF_SIZE_ENCODING_PROTOCOL, len(bts))
                
            match client.socket.type:
                case socket.SOCK_STREAM:
                    
                    if encrypt:
                        client.socket.sendall(length_b+encrypted+Options.SEPERATOR+tag)
                    else:
                        client.socket.sendall(length_b+bts)
                    return True
                case socket.SOCK_DGRAM:
                    client.socket.sendto(length_b, (client.ip, client.port))
                    if encrypt:
                        client.socket.sendto(encrypted+Options.SEPERATOR+tag,(client.ip, client.port))
                    else:
                        client.socket.sendto(bts,(client.ip, client.port))
                        
                    return True

            return False
        # except Exception:
        #     return False

    @staticmethod
    def send_parts(client: Connection, parts: list, add_sep = True, encrypt = True):
        encoded_parts = [b if type(b) != str else b.encode() for b in parts]
        encoded_parts = [b if type(b) != int else int.to_bytes(b, byte_length(b)) for b in encoded_parts]
        bts = (Options.SEPERATOR if add_sep else b'').join(encoded_parts)
        return NetworkUtils.__send_raw(client, bts, encrypt)

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

                parts = client.recieve_parts(decrypt=False)
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

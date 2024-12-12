__author__ = "K9 & Alon"
import math
from encryption_manager import EncryptionManager
import event_handler
from utils import Connection, DataType, NetworkUtils, Event
import socket
import threading
from constants import Options, Events
from terminal import Terminal
import time

class ControlledPC:
    def __init__(self) -> None:

        self.clients: list[Connection] = []

        Terminal.info("Initializing server socket...")
        self.server_s = socket.socket()
        self.server_s.bind(("0.0.0.0", Options.PORT))
        self.server_s.listen(Options.MAX_CONNECTED)
        Terminal.info(f"Server started on port {Options.PORT}")

        self.open = True

        Terminal.info("Adding event listeners...")
        NetworkUtils.add_listener(Events.Screenshot_Request, event_handler.ScreenshotRequestEvent)
        NetworkUtils.add_listener(Events.FileContent_Request, event_handler.FileRequestEvent)
        NetworkUtils.add_listener(Events.UnknownEvent, event_handler.UnknownEvent)
        NetworkUtils.add_listener(Events.ConnectionClosed, event_handler.ConnectionClosedEvent)
        NetworkUtils.add_listener(Events.FileList_Request, event_handler.FileListRequestEvent)
        NetworkUtils.add_listener(Events.CopyFile_Request, event_handler.FileCopyRequestEvent)
        NetworkUtils.add_listener(Events.MoveFile_Request, event_handler.FileMoveRequestEvent)
        NetworkUtils.add_listener(Events.FileChunkUpload_Action, event_handler.FileChunkUploadEvent, DataType.Raw)
        NetworkUtils.add_listener(Events.CommandRun_Request, event_handler.CommandRunRequestEvent)
        NetworkUtils.add_listener(Events.RemoveFile_Request, event_handler.FileRemoveEventRequest)
        NetworkUtils.add_listener(Events.ScreenControl_Request, event_handler.ScreenControlRequestEvent)
        NetworkUtils.add_listener(Events.ScreenWatch_Request, event_handler.ScreenWatchRequestEvent)
        NetworkUtils.add_listener(Events.ScreenControlDisconnect_Action, event_handler.ScreenControlDisconnectEvent)
        NetworkUtils.add_listener(Events.ScreenWatchDisconnect_Action, event_handler.ScreenControlDisconnectEvent)
        Terminal.info("14 event listeners added!")

    def handle_exit(self):
        Terminal.info("Closing server socket...")
        self.open = False
        self.server_s.close()

        Terminal.info("Disconnecting clients...")
        for client in self.clients:
            client.disconnect()

        Terminal.success("Server closed successfully!")
        exit(0)

    def handle_client(self, client: Connection):
        
        client.initiate_key_switch()
        NetworkUtils.listen_for_events(client)

    def start_accept_clients(self):
        Terminal.info("Waiting for clients to connect...")
        self.server_s.settimeout(0.5)

        while self.open:
            try:
                soc, addr = self.server_s.accept()
            except socket.timeout:
                continue

            if len(self.clients) >= Options.MAX_CONNECTED:
                Terminal.warning(f"Client ({addr[0]}:{addr[1]}) tried to connect but the server is full!")
                continue

            Terminal.info(f"Client connected: {addr[0]}:{addr[1]}")
            client = Connection(soc, addr)
            self.clients.append(client)
            threading.Thread(target=self.handle_client, args=(client, ), daemon=True).start()


if __name__ == "__main__":
    Terminal.clear()
    Terminal.logo()
    Terminal.info("Starting server...")
    time.sleep(1)
    cpc = ControlledPC()
    Terminal.success("Server started successfully!")
    try:
        cpc.start_accept_clients()
    except KeyboardInterrupt:
        cpc.handle_exit()

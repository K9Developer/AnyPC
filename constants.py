from enum import Enum

class Options:
    MAX_CONNECTED = 20
    PORT = 34981
    CHUNK_SIZE = 4096*2
    DEBUG_LEVEL = 2 # 1 = Normal debug, 2 = Verbose debug

    SCREENSHOTS_FOLDER = "screenshots"

    SIZE_OF_SIZE_ENCODING_PROTOCOL = "I"
    SIZE_OF_SIZE = 4
    SEPERATOR = b"\0"

    MOUSE_POISITION_ACCURACY = 1000
    SCREEN_FRAME_PORT = 34982
    MOUSE_UPDATE_PORT = 34983
    KEYBOARD_UPDATE_PORT = 34984

    SCREEN_UPDATE_FRAME_RATE = 30
    SCREEN_CHANGE_DETECTION_THRESHOLD = 5
    SCREEN_SHARE_PITURE_QUALITY = 70
    REGION_SIZE_BYTES = 3
    MAX_REGION_AREA = 60000
    SCREEN_SIZE_FACTOR = 0.9
    
    RSA_KEY_SIZE = 1024
    NONCE_SIZE = 16
    TAG_SIZE = 16

class Events(Enum):
    Screenshot_Request = "SSRQ"
    FileContent_Request = "FLRQ"
    FileList_Request = "LSRQ"
    CopyFile_Request = "CPRQ"
    MoveFile_Request = "MVRQ"
    ScreenControl_Request = "SCRQ"
    CommandRun_Request = "CMDR"
    RemoveFile_Request = "RMRQ"

    ScreenControlInput_Action = "SCIN"
    ScreenControlDisconnect_Action = "DNSC"
    FileChunkUpload_Action = "UPCK"
    ScreenFrame_Action = "SCFR"

    ScreenshotDone_Response = "SDON"
    FileChunkDownload_Response = "DNCK"
    FileList_Response = "FOLL"
    OperationSuccess_Response = "SUCC"
    OperationFailed_Response = "ERRR"
    AcceptScreenControl_Response = "ACSC"
    CommandRun_Response = "CMDO"

    ScreenWatch_Request = "SWRQ"
    ScreenWatchDisconnect_Action = "DNSW"
    AcceptScreenWatch_Response = "ACSW"

    PublicKeyTransfer_Action = "PUKT"
    SecretTransfer_Action = "SECT"

    ConnectionClosed = "CLOS"
    UnknownEvent = "UNKNOWN_EVENT"

    @classmethod
    def from_val(cls, value: str) -> 'Events':
        for event in cls:
            if value == event.value:
                return event
        return cls.UnknownEvent

class Error(Enum):
    UnknownError     = 0
    FileNotFound     = 1
    BadPath          = 2
    FailureToSendKey = 3
    CouldntVerifyKey = 4

class DataType(Enum):
    Raw = "RAW",
    Part = "PART"

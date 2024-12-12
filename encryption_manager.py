from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Random import get_random_bytes
from Crypto.PublicKey import RSA

from constants import Options
import base64

class Key:
    def __init__(self, key: RSA.RsaKey) -> None:
        self.key = key
    
    def dump_bytes(self):
        return self.key.export_key(format='DER')
    
    @staticmethod
    def import_bytes(self, key_bytes: bytes):
        return Key(RSA.import_key(key_bytes))
    
    def get_key(self):
        return self.key


class Encryption:

    def __init__(self) -> None:
        self.sym_key = None

    def __aes_encrypt(self, data: bytes):
        nonce = get_random_bytes(Options.NONCE_SIZE)
        cipher = AES.new(self.sym_key, AES.MODE_EAX, nonce=nonce, mac_len=Options.TAG_SIZE)
        ciphertext, tag = cipher.encrypt_and_digest(data)
        return [nonce, tag, ciphertext]
    
    def aes_net_encrypt(self, data: bytes):
        return b''.join(self.__aes_encrypt(data))
    
    def __aes_decrypt(self, nonce: bytes, tag: bytes, ciphertext: bytes):
        cipher = AES.new(self.sym_key, AES.MODE_EAX, nonce=nonce, mac_len=Options.TAG_SIZE)
        try:
            data = cipher.decrypt_and_verify(ciphertext, tag)
            return data
        except ValueError:
            return None
    
    def aes_net_decrypt(self, full: bytes):
        if full is None or len(full) < Options.NONCE_SIZE + Options.TAG_SIZE:
            return None
        nonce = full[:Options.NONCE_SIZE]
        tag = full[Options.NONCE_SIZE:Options.NONCE_SIZE+Options.TAG_SIZE]
        ciphertext = full[Options.NONCE_SIZE+Options.TAG_SIZE:]
        return self.__aes_decrypt(nonce, tag, ciphertext)

    def generate_rsa_keys(self):
        k = RSA.generate(Options.RSA_KEY_SIZE)
        return Key(k), Key(k.publickey())
    
    def set_sym_key(self, key: bytes):
        self.sym_key = key
    
    def rsa_encrypt(self, key: Key, data: bytes):
        cipher = PKCS1_OAEP.new(key.get_key())
        return cipher.encrypt(data)
    
    def rsa_decrypt(self, key: Key, data: bytes):
        cipher = PKCS1_OAEP.new(key.get_key())
        return cipher.decrypt(data)
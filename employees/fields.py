import decimal
import logging
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)


class FernetCipher:
    @staticmethod
    def get_fernet():
        key = getattr(settings, 'ENCRYPTION_KEY', None)
        if not key:
            raise ValueError("ENCRYPTION_KEY is not set in Django settings.")
        return Fernet(key.encode() if isinstance(key, str) else key)

    @classmethod
    def encrypt(cls, value):
        if value is None or value == '':
            return value
        val_str = str(value)
        if val_str.startswith('gAAAAA'):
            # Already an encrypted Fernet token — don't double-encrypt.
            return val_str
        f = cls.get_fernet()
        return f.encrypt(val_str.encode('utf-8')).decode('utf-8')

    @classmethod
    def decrypt(cls, value):
        if value is None or value == '':
            return value
        val_str = str(value)
        if not val_str.startswith('gAAAAA'):
            # Not a Fernet token at all — this is a plain, not-yet-encrypted
            # value (e.g. a Python-side field default like Decimal("0"),
            # or raw input from a form before it's ever been saved/encrypted).
            # Treat it as already-plaintext instead of attempting to decrypt it.
            return val_str
        f = cls.get_fernet()
        try:
            return f.decrypt(val_str.encode('utf-8')).decode('utf-8')
        except InvalidToken:
            # This means the value LOOKS like a Fernet token (right prefix)
            # but can't be decrypted with the current key — either the key
            # changed, or the data is corrupted. This is a serious
            # data-integrity problem and must not be hidden from whoever is
            # looking at this record.
            logger.error(
                "Failed to decrypt a field value: the current ENCRYPTION_KEY "
                "does not match the key used to encrypt this data, or the "
                "stored value is corrupted. The value may be lost if the "
                "original key cannot be recovered."
            )
            raise


class EncryptedCharField(models.CharField):
    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return FernetCipher.encrypt(value)

    def from_db_value(self, value, expression, connection):
        return FernetCipher.decrypt(value)

    def to_python(self, value):
        decrypted = FernetCipher.decrypt(value)
        return super().to_python(decrypted)


class EncryptedDecimalField(models.DecimalField):
    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None:
            return None
        return FernetCipher.encrypt(str(value))

    def from_db_value(self, value, expression, connection):
        decrypted = FernetCipher.decrypt(value)
        if decrypted is None or decrypted == '':
            return None
        return decimal.Decimal(decrypted)

    def to_python(self, value):
        decrypted = FernetCipher.decrypt(value)
        if decrypted is None or decrypted == '':
            return None
        if isinstance(decrypted, decimal.Decimal):
            return decrypted
        return super().to_python(decrypted)

# import decimal
# from django.db import models

# # Neutralized fields: encryption has been completely removed. 
# # These now act as normal pass-through fields to prevent breaking your models.

# class EncryptedCharField(models.CharField):
#     def get_prep_value(self, value):
#         return super().get_prep_value(value)

#     def from_db_value(self, value, expression, connection):
#         return value

#     def to_python(self, value):
#         return super().to_python(value)


# class EncryptedDecimalField(models.DecimalField):
#     def get_prep_value(self, value):
#         return super().get_prep_value(value)

#     def from_db_value(self, value, expression, connection):
#         return value

#     def to_python(self, value):
#         return super().to_python(value)
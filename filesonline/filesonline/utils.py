import os, time

import pyAesCrypt
import jwt

from filesonline.settings import encrypt_password, encrypt_bufferSize
from filesonline.settings import token_sign_key, token_expiration
from filesonline.settings import (IMAGE_EXTENSIONS, AUDIO_EXTENSIONS, VIDEO_EXTENSIONS,
    EXCEL_EXTENSIONS, WORD_EXTENSIONS, POWERPOINT_EXTENSIONS, PDF_EXTENSIONS,
    CODING_EXTENSIONS, ARCHIVE_EXTENSIONS)


def get_user_encrypt_password(user):

    e_p = encrypt_password
    u_e_p = user.user_profile.enc_pass

    return ''.join([chr(ord(e_p[i]) + ord(u_e_p[i % len(u_e_p)])) for i in range(len(e_p))])


def encrypt_file(file_path, user):

    new_path, _ = find_good_name(file_path + '.enc')

    pyAesCrypt.encryptFile(file_path, new_path, get_user_encrypt_password(user), encrypt_bufferSize)

    return new_path


def decrypt_file(encrypted_path, user):
    dec_path, _ = find_good_name(encrypted_path[:-4])
    pyAesCrypt.decryptFile(encrypted_path, dec_path, get_user_encrypt_password(user), encrypt_bufferSize)

    return dec_path


def find_good_name(path):

    if not os.path.exists(path):
        return path, None

    i = 2

    base, base_ext = os.path.splitext(os.path.splitext(path)[0])
    ext = base_ext + os.path.splitext(path)[1]

    test_name = base + ' ({})'.format(i) + ext
    while os.path.exists(test_name):
        i += 1
        test_name = base + ' ({})'.format(i) + ext
    path = test_name

    return path, i


def get_file_type(ext):

    if ext in AUDIO_EXTENSIONS:
        return 'audio'

    if ext in IMAGE_EXTENSIONS:
        return 'image'

    if ext in VIDEO_EXTENSIONS:
        return 'video'

    if ext in EXCEL_EXTENSIONS:
        return 'excel'

    if ext in WORD_EXTENSIONS:
        return 'word'

    if ext in POWERPOINT_EXTENSIONS:
        return 'power'

    if ext in PDF_EXTENSIONS:
        return 'pdf'

    if ext in CODING_EXTENSIONS:
        return 'code'

    if ext in ARCHIVE_EXTENSIONS:
        return 'archive'

    return 'file'


def human_readable_size(size):

    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024 or unit == 'TB':
            return ''.join(["%.2f" % size, unit])
        size /= 1024


def get_vault_token(user):

    message = {
        'user': user.pk,
        'created_date': time.time()
    }

    return jwt.encode(message, token_sign_key, algorithm='HS256').decode('utf-8')


def check_vault_token(token, user):

    if not token:
        return False

    try:
        message = jwt.decode(token, token_sign_key)

        print('time since token created: {}'.format(time.time() - message.get('created_date')))

        if (
                message.get('user') == user.pk
            and  time.time() - message.get('created_date') < token_expiration
        ):
            return True

        return False
    except jwt.exceptions.DecodeError as e:
        print(e)
        return False

"""
This module contains the default configurations for hedweb

If you want to locally run debug code, create a copy of this file called
config.py and set the BASE_DIRECTORY at the top of it to be valid.
"""


import os
import tempfile




class Config(object):
    BASE_DIRECTORY = os.getcwd()
    # Folder the program stores hed cache, log, etc.  Make sure the program has access to this directory.
    # BASE_DIRECTORY = '/path/to/base/folder'
    LOG_DIRECTORY = os.path.join(BASE_DIRECTORY, 'log')
    os.makedirs(LOG_DIRECTORY, exist_ok=True)
    LOG_FILE = os.path.join(LOG_DIRECTORY, 'error.log')
    KEY_FILE = os.path.join(LOG_DIRECTORY, 'tmp.txt')
    if not os.path.exists(KEY_FILE):
        with open(KEY_FILE, 'w+') as f:
            f.write(str(os.urandom(24)))
    with open(KEY_FILE, 'r') as f:
        SECRET_KEY = f.read()  # os.getenv('SECRET_KEY') # os.urandom(24)
    STATIC_URL_PATH = None
    STATIC_URL_PATH_ATTRIBUTE_NAME = 'STATIC_URL_PATH'
    UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), 'hedtools_uploads')
    URL_PREFIX = None
    HED_CACHE_FOLDER = os.path.join(BASE_DIRECTORY, 'schema_cache')



class DevelopmentConfig(Config):
    DEBUG = False
    TESTING = False


class TestConfig(Config):
    DEBUG = False
    TESTING = True


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False


class DebugConfig(Config):
    DEBUG = True
    TESTING = False

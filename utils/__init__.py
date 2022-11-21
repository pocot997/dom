from logging import info
from os import urandom


def generate_password():
    password = urandom(32).hex()
    info("Generated random admin password: %s", password)
    return password

import os
import socket


# -----------------------UTILS FUNCTIONS FOR CONSOLE-----------------------#
def clearScreen():
    if os.name == "nt":  # Nếu là Windows
        os.system("cls")
    else:  # Nếu là hệ điều hành khác (Linux/MacOS)
        os.system("clear")


def gotoxy(x, y):
    print("\033[%d;%dH" % (x, y), end="")


def setTextColor(color):
    if color == "red":
        return "\033[91m"
    elif color == "green":
        return "\033[92m"
    elif color == "yellow":
        return "\033[93m"
    elif color == "blue":
        return "\033[94m"
    elif color == "purple":
        return "\033[95m"
    elif color == "cyan":
        return "\033[96m"
    elif color == "white":
        return "\033[97m"
    else:
        return "\033[0m"


# -----------------------UTILS FUNCTIONS FOR CONSOLE-----------------------#

# -----------------------UTILS FUNCTIONS FOR MAIN-----------------------#


def inputChoice():
    # -----------------SETTINGS UP CONSOLE-----------------#
    screenWidth = 80
    screenHeigh = 25

    TITLE = "SOCKET FILES TRANSFER"

    clearScreen()

    print(setTextColor("green"))
    print(screenWidth * "-")
    print(
        "|"
        + setTextColor("cyan")
        + " " * ((screenWidth - len(TITLE)) // 2 - 1)
        + TITLE
        + " " * ((screenWidth - len(TITLE)) // 2 - 1)
        + setTextColor("green")
        + "|"
    )
    print(screenWidth * "-", end="")
    print(setTextColor("white"))

    print("0. Exit")
    print("1. Download file from server with input.txt with TCP")
    print("2. Download file from server with input.txt with UDP")

    # Processing users' choice
    print()
    print("Choose your option: ", end="")

    return int(input())


# -----------------------UTILS FUNCTIONS FOR MAIN-----------------------#


def get_file_size(filename):
    """
    Get the size of the file in bytes.
    """
    file_path = os.path.join("./files_received/", filename)
    return os.path.getsize(file_path)


def check_file_exist(filename):
    """
    Check if the file exists.
    """

    file_path = os.path.join("./files_received/", filename)
    return os.path.exists(file_path)


def count_files_with_prefix(directory, prefix):
    count = 0
    for filename in os.listdir(directory):
        if filename.startswith(prefix):
            count += 1
    return count


def find_free_port(HOST):
    """
    Find a free port on the server.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def standardize_str(s, n):
    while len(s) < n:
        s += " "
    return s

# import sys
# import utils
# import clientCore
# import signal
# import clientCoreUDP
# import threading
# from fileMonitor import FileMonitor
# import time

# filename = "input.txt"


# def main():
#     # Create a FileMonitor instance
#     monitor = FileMonitor(filename)

#     # Start the monitoring in a separate thread
#     monitor_thread = threading.Thread(target=monitor.monitor_file)
#     monitor_thread.start()

#     # Set up signal handling for Ctrl+C
#     signal.signal(signal.SIGINT, signal_handler(monitor, monitor_thread))

#     # -----------------------------------------------------------------------

#     # Menu options
#     while True:
#         # Get user input
#         choice = utils.inputChoice()

#         # Select choice from menu
#         if choice == 0:
#             print("Exiting...")
#             monitor.stop()
#             monitor_thread.join()
#             break
#         elif choice == 1:
#             print("Downloading file from server with input.txt with TCP")
#             c1 = clientCore.SocketClient()
#             c1.connect_to_server(filename)
#         elif choice == 2:
#             print("Downloading file from server with input.txt with UDP")
#             s1 = clientCoreUDP.SocketClientUDP()
#             s1.connect_to_server(filename)
#         else:
#             print("Invalid choice. Please try again.")

#     # -----------------------------------------------------------------------

#     # Keep the main thread alive to handle Ctrl+C
#     while monitor_thread.is_alive():
#         time.sleep(1)


# # Signal handler for graceful shutdown
# def signal_handler(monitor, monitor_thread):
#     print("\n[INFO] Signal received, stopping file monitor...")
#     monitor.stop()
#     monitor_thread.join()
#     print("[INFO] File monitor stopped. Exiting.")
#     exit(0)


# # -----------------SETTINGS UP CONSOLE-----------------#

# if __name__ == "__main__":
#     main()
import sys
import utils
import clientCore
import signal
import clientCoreUDP
import clientUDP


def main():
    # -----------------SETTINGS UP CONSOLE-----------------#
    screenWidth = 80
    screenHeigh = 25

    TITLE = "SOCKET FILES TRANSFER"
    filename = "input.txt"

    utils.clearScreen()

    print(utils.setTextColor("green"))
    print(screenWidth * "-")
    print(
        "|"
        + utils.setTextColor("cyan")
        + " " * ((screenWidth - len(TITLE)) // 2 - 1)
        + TITLE
        + " " * ((screenWidth - len(TITLE)) // 2 - 1)
        + utils.setTextColor("green")
        + "|"
    )
    print(screenWidth * "-", end="")
    print(utils.setTextColor("white"))

    print("0. Exit")
    print("1. Download file from server with input.txt with TCP")
    print("2. Download file from server with input.txt with UDP")

    # Processing users' choice
    print()
    print("Choose your option: ", end="")

    choice = int(input())

    # Select choice from menu
    if choice == 0:
        print("Exiting...")

    if choice == 1:
        print("Downloading file from server with input.txt with TCP")
        c1 = clientCore.SocketClient()
        # server_ip = input("Enter server IP: ")
        # download_dir = input("Enter download path: ")
        # c1.connect_to_server(filename, download_dir, server_ip)
        c1.connect_to_server(filename)

    if choice == 2:
        print("Downloading file from server with input.txt with UDP")
        
        client = clientUDP.SocketClientUDP()
        client.start()

        # try:
        #     s1.connect_to_server("input.txt")
        # except KeyboardInterrupt:
        #     print("\n[INFO] Client terminated by user (Ctrl + C).")
            

    # Press Ctrl + C to exit
    def handle_exit(signal, frame):
        print("\nCtrl+C detected. Exiting program...")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)

    print(
        "Các tệp đã được tải thành công! \n Nhấn CtrL+C để thoát khỏi chương trình..."
    )

    # ĐỢI NGƯỜI DÙNG NHẤN CTRL+C để thoát!!!!

    while True:
        pass


# -----------------SETTINGS UP CONSOLE-----------------#


if __name__ == "__main__":
    main()

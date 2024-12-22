import serverCore
import serverUDP
import signal
import sys
import threading

import t1

# Global flag to signal threads to stop
# Ctrl+C signal handler
# -------------------------------------------------------------------------------

stop_event = threading.Event()


def handle_exit(signal, frame):
    print("\n[STATUS] Ctrl+C detected. Stopping all servers...")
    stop_event.set()  # Signal threads to stop
    sys.exit(0)


# -------------------------------------------------------------------------------
"""
    Task for running the TCP server.
"""


def tcp_server_task():
    s1 = serverCore.SocketServer()
    try:
        s1.create_server()  # Run TCP server
    except Exception as e:
        print(f"[ERROR] TCP server error: {e}")
    finally:
        print("[STATUS] TCP server shutting down...")


"""
    Task for running the UDP server.
"""


def udp_server_task():
    server = t1.SocketServerUDP()
    try:
        server.start()  # Run UDP server
    except Exception as e:
        print(f"[ERROR] UDP server error: {e}")
    finally:
        print("[STATUS] UDP server shutting down...")


# -------------------------------------------------------------------------------


def main():
    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, handle_exit)

    print("0. Exit")
    print("1. Download file from server with input.txt using TCP")
    print("2. Download file from server with input.txt using UDP")

    print("\nChoose your option: ", end="")
    try:
        choice = int(input())
    except ValueError:
        print("[ERROR] Invalid input. Please enter a number.")
        sys.exit(1)

    if choice == 0:
        print("Exiting...")
        sys.exit(0)

    elif choice == 1:
        print("Starting TCP server...")
        tcp_thread = threading.Thread(target=tcp_server_task, daemon=True)
        tcp_thread.start()

    elif choice == 2:
        print("Starting UDP server...")
        udp_thread = threading.Thread(target=udp_server_task, daemon=True)
        udp_thread.start()

    else:
        print("[ERROR] Invalid choice.")
        sys.exit(1)

    # Keep the main thread running until Ctrl+C is detected
    while not stop_event.is_set():
        stop_event.wait(1)  # Wait for the signal to stop


if __name__ == "__main__":
    main()

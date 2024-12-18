import serverCore
import serverUDP
import socket

def main():
    print("0. Exit")
    print("1. Download file from server with input.txt with TCP")
    print("2. Download file from server with input.txt with UDP")

    # Processing users' choice
    print()
    print("Choose your option: ", end="")

    choice = int(input())

    if choice == 0:
        exit(0)

    elif choice == 1:
        s1 = serverCore.SocketServer()
        s1.create_server()

    elif choice == 2:
        server = serverUDP.SocketServerUDP()
        server.start()

if __name__ == "__main__":
    main()
    

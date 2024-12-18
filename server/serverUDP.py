import socket
import os
import zlib

class SocketServerUDP:
    def __init__(self, HOST="127.0.0.1", PORT=12345, RESOURCE_PATH="resources", BUFFER_SIZE=512, TIMEOUT=5):
        self.HOST = HOST
        self.PORT = PORT
        self.RESOURCE_PATH = RESOURCE_PATH
        self.BUFFER_SIZE = BUFFER_SIZE
        self.TIMEOUT = TIMEOUT
        os.makedirs(self.RESOURCE_PATH, exist_ok=True)

        self.CODE = {"LIST": "LIST", "GET": "GET", "SIZE": "SIZE", "CONNECT": "CONNECT", "RESEND": "RESEND"}

        print("[STATUS] Initializing the server...")

    def calculate_checksum(self, data):
        return zlib.crc32(data)

    def send_resources_list(self, server_socket, client_address):
        try:
            files = [f for f in os.listdir(self.RESOURCE_PATH) if os.path.isfile(os.path.join(self.RESOURCE_PATH, f))]
            response = f"{self.CODE['LIST']}|{','.join(files)}" if files else f"{self.CODE['LIST']}|NO_FILES"
            server_socket.sendto(response.encode(), client_address)
        except Exception as e:
            server_socket.sendto(f"{self.CODE['LIST']}|ERROR: {str(e)}".encode(), client_address)

    def send_file_size(self, server_socket, file_name, client_address):
        file_path = os.path.join(self.RESOURCE_PATH, file_name)
        if not os.path.exists(file_path):
            server_socket.sendto(b"ERROR|File not found.", client_address)
            return
        file_size = os.path.getsize(file_path)
        server_socket.sendto(f"SIZE|{file_size}".encode(), client_address)

    def send_file_chunk(self, server_socket, file_name, seq_num, client_address):
        file_path = os.path.join(self.RESOURCE_PATH, file_name)
        if not os.path.exists(file_path):
            server_socket.sendto(b"ERROR|File not found.", client_address)
            return

        chunk_size = self.BUFFER_SIZE - 20  
        offset = seq_num * chunk_size

        with open(file_path, "rb") as f:
            f.seek(offset)
            chunk = f.read(chunk_size)

            if not chunk:
                server_socket.sendto(b"EOF", client_address)
                return

            checksum = self.calculate_checksum(chunk)
            packet = f"{seq_num}:{checksum}:".encode() + chunk
            server_socket.sendto(packet, client_address)

    def resend_file_chunk(self, server_socket, file_name, seq_num, client_address):
        file_path = os.path.join(self.RESOURCE_PATH, file_name)
        if not os.path.exists(file_path):
            server_socket.sendto(b"ERROR|File not found.", client_address)
            return

        chunk_size = self.BUFFER_SIZE - 20  
        offset = seq_num * chunk_size

        with open(file_path, "rb") as f:
            f.seek(offset)
            chunk = f.read(chunk_size)

            if not chunk:
                server_socket.sendto(b"EOF", client_address)
                return

            checksum = self.calculate_checksum(chunk)
            packet = f"{seq_num}:{checksum}:".encode() + chunk
            server_socket.sendto(packet, client_address)

        print(f"Resent chunk {seq_num} for {file_name}")

    def handle_requests(self, server_socket):
        print("[STATUS] Waiting for client connection...")

        while True:
            try:
                data, client_address = server_socket.recvfrom(self.BUFFER_SIZE)
                message = data.decode().strip()

                if message == self.CODE["CONNECT"]:
                    print(f"[STATUS] Client {client_address} connected!")
                    server_socket.sendto(b"WELCOME", client_address)

                elif message.startswith(self.CODE["LIST"]):
                    self.send_resources_list(server_socket, client_address)

                elif message.startswith(self.CODE["SIZE"]):
                    file_name = message.split("|")[1]
                    self.send_file_size(server_socket, file_name, client_address)

                elif message.startswith(self.CODE["GET"]):
                    _, file_name, seq_num = message.split("|")
                    seq_num = int(seq_num)
                    self.send_file_chunk(server_socket, file_name, seq_num, client_address)
                
                elif message.startswith(self.CODE["RESEND"]): 
                    _, file_name, seq_num = message.split("|")
                    seq_num = int(seq_num)
                    self.resend_file_chunk(server_socket, file_name, seq_num, client_address)

                else:
                    server_socket.sendto(b"ERROR|Unknown command.", client_address)

            except socket.timeout:
                print("No client activity. Server is still waiting...")

    def start(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
            server_socket.bind((self.HOST, self.PORT))
            server_socket.settimeout(self.TIMEOUT)

            print(f"[STATUS] Server started at {self.HOST}:{self.PORT}")
            self.handle_requests(server_socket)

# if __name__ == "__main__":
#     host = "127.0.0.1"
#     server = SocketServerUDP(HOST=host)
#     server.start()

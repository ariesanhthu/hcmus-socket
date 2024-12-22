import socket
import os
import zlib
from threading import Thread
import logging

class SocketServerUDP:
    def __init__(self, HOST=socket.gethostbyname(socket.gethostname()), BASE_PORT=12345, RESOURCE_PATH="resources", BUFFER_SIZE=10000, TIMEOUT=5):
        self.HOST = HOST
        self.BASE_PORT = BASE_PORT
        self.PORTS = [BASE_PORT + i for i in range(4)]  # 4 cổng cho tải đa luồng
        self.RESOURCE_PATH = RESOURCE_PATH
        self.BUFFER_SIZE = BUFFER_SIZE
        self.TIMEOUT = TIMEOUT
        os.makedirs(self.RESOURCE_PATH, exist_ok=True)

        self.CODE = {"LIST": "LIST", "GET": "GET", "SIZE": "SIZE", "CONNECT": "CONNECT", "RESEND": "RESEND", "CHECK": "CHECK"}

        # Lưu trạng thái
        self.state_cache = {"LIST": None, "SIZE": {}}

        # Thiết lập logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.logger = logging.getLogger("SocketServerUDP")
        self.logger.info("Initializing the server...")

    def calculate_checksum(self, data):
        return zlib.crc32(data)

    def send_resources_list(self, server_socket, client_address):
        """Gửi danh sách tài nguyên, chỉ cập nhật log khi có thay đổi."""
        try:
            files = [f for f in os.listdir(self.RESOURCE_PATH) if os.path.isfile(os.path.join(self.RESOURCE_PATH, f))]
            if files != self.state_cache["LIST"]:
                self.state_cache["LIST"] = files
                self.logger.info(f"Updated file list: {files}")
            response = f"{self.CODE['LIST']}|{','.join(files)}" if files else f"{self.CODE['LIST']}|NO_FILES"
            server_socket.sendto(response.encode(), client_address)
        except Exception as e:
            server_socket.sendto(f"{self.CODE['LIST']}|ERROR: {str(e)}".encode(), client_address)

    def send_file_size(self, server_socket, file_name, client_address):
        """Gửi kích thước file, cache lại để tránh log lặp."""
        file_path = os.path.join(self.RESOURCE_PATH, file_name)
        if not os.path.exists(file_path):
            server_socket.sendto(b"ERROR|File not found.", client_address)
            return

        file_size = os.path.getsize(file_path)
        if self.state_cache["SIZE"].get(file_name) != file_size:
            self.state_cache["SIZE"][file_name] = file_size
            self.logger.info(f"File size for {file_name}: {file_size} bytes")

        server_socket.sendto(f"SIZE|{file_size}".encode(), client_address)

    def send_file_chunk(self, server_socket, file_name, seq_num, client_address):
        """Gửi một phần file."""
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
        self.logger.info(f"Sent chunk {seq_num} of file {file_name} to {client_address}")

    def handle_requests(self, server_socket):
        """Xử lý yêu cầu từ client."""
        self.logger.info("[STATUS] Waiting for client connection...")

        while True:
            try:
                data, client_address = server_socket.recvfrom(self.BUFFER_SIZE)
                message = data.decode().strip()

                if message == self.CODE["CONNECT"]:
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
                    self.send_file_chunk(server_socket, file_name, seq_num, client_address)
                else:
                    server_socket.sendto(b"ERROR|Unknown command.", client_address)

            except socket.timeout:
                self.logger.info("No client activity. Server is still waiting...")

    def start_server_on_port(self, port):
        """Khởi chạy server trên cổng cụ thể."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
            server_socket.bind((self.HOST, port))
            server_socket.settimeout(self.TIMEOUT)
            self.logger.info(f"Server started on {self.HOST}:{port}")
            self.handle_requests(server_socket)

    def start(self):
        """Khởi chạy server trên tất cả các cổng."""
        threads = []
        for port in self.PORTS:
            thread = Thread(target=self.start_server_on_port, args=(port,))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

if __name__ == "__main__":
    server = SocketServerUDP()
    server.start()

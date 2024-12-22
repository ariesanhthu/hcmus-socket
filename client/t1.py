import logging
import os
import socket
import threading
import time
import zlib
from tqdm import tqdm


class SocketClientUDP:
    """UDP Client for downloading files from a server with multi-threading."""

    def __init__(
        self,
        HOST="192.168.137.1",
        PORTS=[12345, 12346, 12347, 12348],
        INPUT_FILE="input.txt",
        DOWNLOAD_FOLDER="files_received_udp",
        BUFFER_SIZE=10000,
        TIMEOUT=5,
        PIPE=1,
    ):
        self.HOST = HOST
        self.PORTS = PORTS
        self.INPUT_FILE = INPUT_FILE
        self.DOWNLOAD_FOLDER = DOWNLOAD_FOLDER
        self.BUFFER_SIZE = BUFFER_SIZE
        self.TIMEOUT = TIMEOUT
        self.PIPE = PIPE
        os.makedirs(self.DOWNLOAD_FOLDER, exist_ok=True)

        self.CODE = {
            "LIST": "LIST",
            "GET": "GET",
            "SIZE": "SIZE",
            "CONNECT": "CONNECT",
            "RESEND": "RESEND",
        }

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.logger = logging.getLogger("SocketClientUDP")

    def calculate_checksum(self, data):
        """Calculate CRC32 checksum for data."""
        return zlib.crc32(data)

    def get_input_file_list(self):
        """Read file list from the input file."""
        try:
            with open(self.INPUT_FILE, "r") as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            self.logger.error(f"Input file '{self.INPUT_FILE}' not found.")
            return []

    def list_files(self, client_socket, server_address):
        """Request the list of files from the server."""
        client_socket.sendto(f"{self.CODE['LIST']}".encode(), server_address)
        try:
            response, _ = client_socket.recvfrom(self.BUFFER_SIZE)
            files = response.decode().split("|", 1)[1]

            if files == "NO_FILES":
                self.logger.info("No files available on server.")
                return []

            # Remove duplicates
            file_list = list(set(files.split(",")))
            self.logger.info(f"Available files on server: {file_list}")
            return file_list

        except socket.timeout:
            self.logger.warning("Server not responding.")
            return []

    def download_file_parallel(self, client_socket, file_name, server_address):
        """Download a file in parallel using multiple threads."""
        client_socket.sendto(f"{self.CODE['SIZE']}|{file_name}".encode(), server_address)
        size_data, _ = client_socket.recvfrom(self.BUFFER_SIZE)

        if not size_data.startswith(b"SIZE|"):
            self.logger.error("Unable to fetch file size.")
            return

        total_size = int(size_data.decode().split("|")[1])
        self.logger.info(f"Starting download for {file_name}. Total size: {total_size} bytes")

        chunk_size = (total_size // self.PIPE) + 1
        threads = []
        results = [None] * self.PIPE

        progress_bars = [
            tqdm(total=chunk_size, desc=f"Pipe {i+1}", unit="B", unit_scale=True)
            for i in range(self.PIPE)
        ]

        def download_chunk(thread_id, start_byte, end_byte):
            nonlocal progress_bars
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(self.TIMEOUT)
                downloaded_data = []
                seq_num = start_byte // (self.BUFFER_SIZE - 20)

                while start_byte < end_byte:
                    try:
                        sock.sendto(f"{self.CODE['GET']}|{file_name}|{seq_num}".encode(), server_address)
                        data, _ = sock.recvfrom(self.BUFFER_SIZE)

                        if data == b"EOF":
                            break

                        seq_received, checksum, chunk = data.split(b":", 2)

                        if int(seq_received) == seq_num and self.calculate_checksum(chunk) == int(checksum):
                            downloaded_data.append(chunk)
                            progress_bars[thread_id].update(len(chunk))
                            start_byte += len(chunk)
                            seq_num += 1
                        else:
                            sock.sendto(f"{self.CODE['RESEND']}|{file_name}|{seq_num}".encode(), server_address)
                    except socket.timeout:
                        sock.sendto(f"{self.CODE['RESEND']}|{file_name}|{seq_num}".encode(), server_address)

                results[thread_id] = b"".join(downloaded_data)

        for i in range(self.PIPE):
            start_byte = i * chunk_size
            end_byte = min(start_byte + chunk_size, total_size)
            thread = threading.Thread(target=download_chunk, args=(i, start_byte, end_byte))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        with open(os.path.join(self.DOWNLOAD_FOLDER, file_name), "wb") as f:
            for chunk_data in results:
                if chunk_data:
                    f.write(chunk_data)

        for pb in progress_bars:
            pb.close()

        self.logger.info(f"File {file_name} downloaded successfully to {self.DOWNLOAD_FOLDER}")

    def run_client_on_port(self, file_list, port):
        """Run client logic on a specific port."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
                client_socket.settimeout(self.TIMEOUT)
                server_address = (self.HOST, port)

                client_socket.sendto(f"{self.CODE['CONNECT']}".encode(), server_address)
                response, _ = client_socket.recvfrom(self.BUFFER_SIZE)

                if response.decode() == "WELCOME":
                    list_files = self.list_files(client_socket, server_address)
                    self.logger.info(f"Number of unique files on server for port {port}: {len(list_files)}")

                    for file_name in file_list:
                        file_path = os.path.join(self.DOWNLOAD_FOLDER, file_name)
                        if not os.path.exists(file_path):
                            self.download_file_parallel(client_socket, file_name, server_address)

        except socket.timeout:
            self.logger.warning(f"Server timeout on port {port}.")

    def start(self):
        """Start the client to process file downloads."""
        try:
            while True:
                file_list = self.get_input_file_list()

                if not file_list:
                    self.logger.info("No files to download. Waiting 5 seconds...")
                    time.sleep(5)
                    continue

                threads = []
                for port in self.PORTS:
                    thread = threading.Thread(target=self.run_client_on_port, args=(file_list, port))
                    threads.append(thread)
                    thread.start()

                for thread in threads:
                    thread.join()

                self.logger.info("All files processed. Rechecking input in 5 seconds...")
                time.sleep(5)

        except KeyboardInterrupt:
            self.logger.info("Client stopped by user (Ctrl + C).")


if __name__ == "__main__":
    client = SocketClientUDP(
        HOST="172.19.201.41",
        PORTS=[12345, 12346, 12347, 12348],
        INPUT_FILE="input.txt",
        DOWNLOAD_FOLDER="files_received_udp",
        BUFFER_SIZE=512,
        TIMEOUT=5,
        PIPE=1,
    )
    client.start()

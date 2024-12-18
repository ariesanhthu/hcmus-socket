import socket
import os
import zlib
import threading
from tqdm import tqdm

class SocketClientUDP:
    def __init__(self, HOST="127.0.0.1", PORT=12345, DOWNLOAD_FOLDER="files_received_udp", BUFFER_SIZE=512, TIMEOUT=5, PIPE=4):
        self.HOST = HOST
        self.PORT = PORT
        self.DOWNLOAD_FOLDER = DOWNLOAD_FOLDER
        self.BUFFER_SIZE = BUFFER_SIZE
        self.TIMEOUT = TIMEOUT
        self.PIPE = PIPE
        os.makedirs(self.DOWNLOAD_FOLDER, exist_ok=True)

        self.CODE = {"LIST": "LIST", "GET": "GET", "SIZE": "SIZE", "CONNECT": "CONNECT"}

        # Lock to synchronize progress bar updates across threads
        self.lock = threading.Lock()
        self.progress_bars = {}

    def calculate_checksum(self, data):
        return zlib.crc32(data)

    def list_files(self, client_socket, server_address):
        client_socket.sendto(f"{self.CODE['LIST']}".encode(), server_address)
        try:
            response, _ = client_socket.recvfrom(self.BUFFER_SIZE)
            files = response.decode().split("|", 1)[1]
            if files == "NO_FILES":
                print("No files available on server.")
                return []

            file_list = files.split(",")
            print("Available files on server:")
            for file in file_list:
                print(f"- {file}")
            return file_list
        except socket.timeout:
            print("Error: Server not responding.")
            return []

    def download_file_parallel(self, client_socket, file_name, server_address):
        client_socket.sendto(f"{self.CODE['SIZE']}|{file_name}".encode(), server_address)
        size_data, _ = client_socket.recvfrom(self.BUFFER_SIZE)
        if not size_data.startswith(b"SIZE|"):
            print("Error: Unable to fetch file size.")
            return

        total_size = int(size_data.decode().split("|")[1])
        print(f"Starting parallel download for {file_name}. Total size: {total_size} bytes")

        chunk_size = (total_size // self.PIPE) + 1
        threads = []
        results = [None] * self.PIPE

        for i in range(self.PIPE):
            self.progress_bars[i] = tqdm(
                total=min(chunk_size, total_size - i * chunk_size),
                desc=f"Thread-{i+1} for {file_name}",
                position=i,
                unit="B",
                unit_scale=True,
                leave=True,
            )

        def download_chunk(thread_id, seq_start, progress_bar):
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(self.TIMEOUT)
                downloaded_data = []

                seq_num = seq_start
                while True:
                    try:
                        sock.sendto(f"{self.CODE['GET']}|{file_name}|{seq_num}".encode(), server_address)
                        data, _ = sock.recvfrom(self.BUFFER_SIZE)

                        if data == b"EOF":
                            break

                        seq_received, checksum, chunk = data.split(b":", 2)

                        if int(seq_received) == seq_num and self.calculate_checksum(chunk) == int(checksum):
                            downloaded_data.append(chunk)
                            with self.lock:  
                                progress_bar.update(len(chunk))  
                            seq_num += 1
                        else:
                            sock.sendto(f"{self.CODE['RESEND']}|{file_name}|{seq_num}".encode(), server_address)
                            print(f"Thread-{thread_id+1}: Corrupted packet detected, resending request for seq {seq_num}")
                    except socket.timeout:
                        sock.sendto(f"{self.CODE['RESEND']}|{file_name}|{seq_num}".encode(), server_address)
                        print(f"Thread-{thread_id+1}: Timeout, resending request for seq {seq_num}")

                results[thread_id] = b"".join(downloaded_data)
            progress_bar.close() 

        for i in range(self.PIPE):
            start_seq = i * (chunk_size // (self.BUFFER_SIZE - 20))
            thread = threading.Thread(target=download_chunk, args=(i, start_seq, self.progress_bars[i]))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        with open(os.path.join(self.DOWNLOAD_FOLDER, file_name), "wb") as f:
            for chunk_data in results:
                if chunk_data:
                    f.write(chunk_data)

        print(f"File {file_name} downloaded successfully to {self.DOWNLOAD_FOLDER}")

    def start(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
            client_socket.settimeout(self.TIMEOUT)
            server_address = (self.HOST, self.PORT)

            client_socket.sendto(f"{self.CODE['CONNECT']}".encode(), server_address)
            try:
                response, _ = client_socket.recvfrom(self.BUFFER_SIZE)
                if response.decode() == "WELCOME":
                    print("Connected to server.")

                    all_files = self.list_files(client_socket, server_address)

                    if all_files:
                        for file_name in all_files:
                            self.download_file_parallel(client_socket, file_name, server_address)

            except socket.timeout:
                print("Error: Server timeout.")

# if __name__ == "__main__":
#     client = SocketClientUDP()
#     client.start()

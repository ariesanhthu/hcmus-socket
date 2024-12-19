import socket
import os
import zlib
import threading
import time
from tqdm import tqdm

class SocketClientUDP:
    # *********************************************************************************************** # 
    """ ============================================================
        args: 
            HOST: server ip  
            PORT: server port   
            INPUT_FILE: file input các file muốn tải về
            DOWNLOAD_FOLDER: folder tải về
            BUFFER_SIZE: thông tin nhận được 
            TIMEOUT: thời gian chờ ACK 
            PIPE: số thread
    ============================================================ """
    def __init__(self, HOST="127.0.0.1", PORT=12345, INPUT_FILE="input.txt", DOWNLOAD_FOLDER="files_received_udp", BUFFER_SIZE=512, TIMEOUT=5, PIPE=4):
        self.HOST = HOST
        self.PORT = PORT
        self.INPUT_FILE = INPUT_FILE
        self.DOWNLOAD_FOLDER = DOWNLOAD_FOLDER
        self.BUFFER_SIZE = BUFFER_SIZE
        self.TIMEOUT = TIMEOUT
        self.PIPE = PIPE
        os.makedirs(self.DOWNLOAD_FOLDER, exist_ok=True)

        self.CODE = {"LIST": "LIST", 
                     "GET": "GET", 
                     "SIZE": "SIZE", 
                     "CONNECT": "CONNECT", 
                     "RESEND": "RESEND"}
        self.lock = threading.Lock()  # Đảm bảo thread an toàn
    # *********************************************************************************************** # 
    """ ============================================================
        Tính toán giá trị băm (checksum) của dữ liệu đã chọn.

        Args:
            data: Dữ liệu đầu vào để tính toán checksum.

        Returns:
            checksum: Giá trị băm (checksum) đã tính toán.
    ============================================================ """
    def calculate_checksum(self, data):
        return zlib.crc32(data)
    
    # *********************************************************************************************** # 
    """ ============================================================
        Hàm lấy các file muốn tải 

        Args:
            file_path: Đường dẫn file input 

        Returns:
            file_list: Danh sách tập tin tại file input dưới dạng list
    ============================================================ """
    def get_input_file_list(self):
        try:
            with open(self.INPUT_FILE, "r") as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"Error: Input file '{self.INPUT_FILE}' not found.")
            return []

    # *********************************************************************************************** # 
    """ ============================================================
        Hàm lấy tất cả src trong server 

        Args:
            client_socket: socket udp 
            server_address: Địa chỉ server

        Returns:
            file_list: Danh sách tập tin tại server dưới dạng list 
    ============================================================ """
    def list_files(self, client_socket, server_address):
        # Gửi thông điệp LIST để nhận về danh sách file
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
        
     # *********************************************************************************************** # 
    """ ============================================================
    Hàm kiểm tra file có tồn tại trên server hay không.

    Args:
        client_socket: socket udp
        server_address: Địa chỉ server
        file_name: Tên file cần kiểm tra

    Returns:
        exists: True nếu file tồn tại, False nếu không.
    ============================================================ """
    def check_file(self, client_socket, server_address, file_name):
        # gửi thông điệp check file
        client_socket.sendto(f"{self.CODE['CHECK']}|{file_name}".encode(), server_address)
        try:
            response, _ = client_socket.recvfrom(self.BUFFER_SIZE)
            if response.decode() == "EXISTS":
                print(f"File '{file_name}' exists on server.")
                return True
            elif response.decode() == "NOT_FOUND":
                print(f"File '{file_name}' does not exist on server.")
                return False
            else:
                print("Error: Unexpected response from server.")
                return False
        except socket.timeout:
            print("Error: Server not responding.")
            return False

     # *********************************************************************************************** # 
    """ ============================================================
        Hàm kiểm tra file đã tải về folder client chưa.

        Args:
            file_name: Tên file cần kiểm tra.

        Returns:
            exists: True nếu file đã tồn tại, False nếu không.
    ============================================================ """
    def check_file_downloaded(self, file_name):
        file_path = os.path.join(self.DOWNLOAD_FOLDER, file_name)
        if os.path.exists(file_path):
            print(f"File '{file_name}' already exists in '{self.DOWNLOAD_FOLDER}'.")
            return True
        else:
            print(f"File '{file_name}' does not exist in '{self.DOWNLOAD_FOLDER}'.")
            return False

    # *********************************************************************************************** #

    """ ============================================================
        Hàm tải song song 4 luồng thread để download file

        Args:
            client_socket: socket udp 
            file_name: tên tập tin 
            server_address: Địa_chi server
    ============================================================ """
    def download_file_parallel(self, client_socket, file_name, server_address):
        # Gửi thông điệp SIZE để nhận về list size
        client_socket.sendto(f"{self.CODE['SIZE']}|{file_name}".encode(), server_address)
        size_data, _ = client_socket.recvfrom(self.BUFFER_SIZE)
        if not size_data.startswith(b"SIZE|"):
            print("Error: Unable to fetch file size.")
            return

        # Thể hiện size, file
        total_size = int(size_data.decode().split("|")[1])
        print(f"Starting download for {file_name}. Total size: {total_size} bytes")

        # Tính toán size cho 1 luồng
        chunk_size = (total_size // self.PIPE) + 1
        threads = []
        results = [None] * self.PIPE

        # Progress bars cho mỗi luồng
        progress_bars = [tqdm(total=chunk_size, desc=f"Pipe {i+1}", unit="B", unit_scale=True) for i in range(self.PIPE)]

        """ ============================================================
            Hàm download 1 chunk 

            Args:
                thread_id: thứ tự luồng
                start_byte: Byte bắt đầu
                end_byte: Byte kết thúc
        ============================================================ """
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

        # Tạo 4 luồng thread
        for i in range(self.PIPE):
            start_byte = i * chunk_size
            end_byte = min(start_byte + chunk_size, total_size)
            thread = threading.Thread(target=download_chunk, args=(i, start_byte, end_byte))
            threads.append(thread)
            thread.start()

        # active 4 luồng
        for thread in threads:
            thread.join()

        # kết hợp 4 luồng thành 1 file hoàn chỉnh
        with open(os.path.join(self.DOWNLOAD_FOLDER, file_name), "wb") as f:
            for chunk_data in results:
                if chunk_data:
                    f.write(chunk_data)

        for pb in progress_bars:
            pb.close()

        print(f"File {file_name} downloaded successfully to {self.DOWNLOAD_FOLDER}")

    # *********************************************************************************************** # 

    """ ============================================================
        Hàm chạy client
    ============================================================ """
    def start(self):
        while True:
            file_list = self.get_input_file_list()
            if not file_list:
                print("No files to download. Waiting 5 seconds...")
                time.sleep(5)
                continue

            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
                client_socket.settimeout(self.TIMEOUT)
                server_address = (self.HOST, self.PORT)

                client_socket.sendto(f"{self.CODE['CONNECT']}".encode(), server_address)
                try:
                    response, _ = client_socket.recvfrom(self.BUFFER_SIZE)

                    if response.decode() == "WELCOME":

                        list_files = self.list_files(client_socket, server_address)
                        print("Number of files on server:", len(list_files))

                        print("Connected to server.")

                        for file_name in file_list:
                            # nếu chưa tồn tại thì mởi tải file
                            if self.check_file_downloaded(file_name) == False:
                                self.download_file_parallel(client_socket, file_name, server_address)

                except socket.timeout:
                    print("Error: Server timeout.")

            print("All files processed. Rechecking input in 5 seconds...")
            time.sleep(5)

    # *********************************************************************************************** # 

"""
    Test nếu cần thì chạy file nây.
"""
if __name__ == "__main__":
    host = "127.0.0.1"
    client = SocketClientUDP(HOST=host)
    client.start()
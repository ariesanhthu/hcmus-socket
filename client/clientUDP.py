import socket
import os
import zlib
import threading
import time
from tqdm import tqdm


class SocketClientUDP:
    # *********************************************************************************************** #
    """============================================================
        args:
            HOST: server ip
            PORT: server port
            INPUT_FILE: file input các file muốn tải về
            DOWNLOAD_FOLDER: folder tải về
            BUFFER_SIZE: thông tin nhận được
            TIMEOUT: thời gian chờ ACK
            PIPE: số thread
    ============================================================"""

    def __init__(
        self,
        HOST="192.168.137.1",
        PORT=12345,
        INPUT_FILE="input.txt",
        DOWNLOAD_FOLDER="files_received_udp",
        BUFFER_SIZE=512,
        TIMEOUT=5,
        PIPE=1,
    ):
        self.HOST = HOST
        self.PORT = PORT
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
            # Nhận thông báo từ server
            response, _ = client_socket.recvfrom(self.BUFFER_SIZE)
            files = response.decode().split("|", 1)[1]

            # Nếu thông báo là no-file thì trả về null
            if files == "NO_FILES":
                print("No files available on server.")
                return []
            
            # in ra tất cả các file trong server nhận được
            file_list = files.split(",")
            print("Available files on server:")
            for file in file_list:
                print(f"- {file}")
            
            # return
            return file_list
        
        # Nếu chờ lệnh response quả timeout thì trả về null
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

        # Nhận size
        size_data, _ = client_socket.recvfrom(self.BUFFER_SIZE)
        if not size_data.startswith(b"SIZE|"):
            print("Error: Unable to fetch file size.")
            return

        # Thể hiện size, file
        total_size = int(size_data.decode().split("|")[1])
        print(f"Starting download for {file_name}. Total size: {total_size} bytes")

        # Tính toán size cho 1 luồng
        # gồm 4 luồng để tải 1 file  
        chunk_size = (total_size // self.PIPE) + 1
        # Kho lưu tiểu trình
        threads = []
        # Kết quả 
        results = [None] * self.PIPE

        # Progress bars cho mỗi luồng
        # total = chunk_size
        progress_bars = [
            
            tqdm(total=chunk_size, 
                desc=f"Pipe {i+1}", 
                unit="B", 
                unit_scale=True)
            
            for i in range(self.PIPE)
        ]

        """ ============================================================
            Hàm download 1 chunk 

            Args:
                thread_id: thứ tự luồng
                start_byte: Byte bắt đầu
                end_byte: Byte kết thúc
        ============================================================ """

        def download_chunk(thread_id, start_byte, end_byte):

            nonlocal progress_bars

            # Mở tiểu trình
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                # thiết lập thời gian chở message
                sock.settimeout(self.TIMEOUT)
                # Các chunk được tải xong lưu vào một list
                downloaded_data = []
                # tính toán seg num, mỗi chunk tương ứng với 1 seg num
                seq_num = start_byte // (self.BUFFER_SIZE - 20)

                # bắt đầu gửi byte
                while start_byte < end_byte:
                    try:
                        # gửi GET đến server bao gồm file name và seq num
                        sock.sendto(
                            f"{self.CODE['GET']}|{file_name}|{seq_num}".encode(),
                            server_address,
                        )

                        # Nhận data
                        data, _ = sock.recvfrom(self.BUFFER_SIZE)

                        # Nếu data là EOF thì break
                        if data == b"EOF":
                            break

                        # Lấy seq num, checksum, chunk từ data
                        seq_received, checksum, chunk = data.split(b":", 2)

                        # Kiểm tra check sum, seq num nếu thỏa thì tiếp tục tải file
                        if int(seq_received) == seq_num and self.calculate_checksum(chunk) == int(checksum):
                            # Tải xong thi thêm vào list
                            downloaded_data.append(chunk)
                            # cập nhật tiểu trình
                            progress_bars[thread_id].update(len(chunk))
                            # tăng byte lên len(chunk) để chuẩn bị cho đợt tải tiếp theo
                            start_byte += len(chunk)
                            # tăng seq num lên 1
                            seq_num += 1
                        else:
                            # Kiểm tra mất gói tin thì gửi lệnh resend đến server
                            sock.sendto(
                                f"{self.CODE['RESEND']}|{file_name}|{seq_num}".encode(),
                                server_address,
                            )
                    except socket.timeout:
                        # Nếu quá thời gian timout mà vẫn chưa nhận được data thì gửi lệnh resend đến server
                        sock.sendto(
                            f"{self.CODE['RESEND']}|{file_name}|{seq_num}".encode(),
                            server_address,
                        )

                # result thứ i sẽ có data là download chunk size        
                results[thread_id] = b"".join(downloaded_data)

        # Tạo 4 luồng thread
        for i in range(self.PIPE):
            # tính toán end byte, start byte
            start_byte = i * chunk_size
            end_byte = min(start_byte + chunk_size, total_size)

            # một luồng bằng 1 download_chunk
            thread = threading.Thread(target=download_chunk, args=(i, start_byte, end_byte))

            # thêm luồng vào danh sách luồng 
            threads.append(thread)

            # chạy 4 luồng 
            thread.start()

        # active 4 luồng
        for thread in threads:
            thread.join()

        # kết hợp kết quả từ 4 luồng thành 1 file hoàn chỉnh
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
        try:
            while True:

                # Nhận các tên file cần tải về qua input.txt
                file_list = self.get_input_file_list()

                # nếu không nhận được file nào, thì chờ 5s đọc lại input.txt
                if not file_list:
                    print("No files to download. Waiting 5 seconds...")
                    time.sleep(5)
                    continue

                # Bắt đầu client
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
                    # thiết lập thời gian chờ nhận 1 message từ server
                    client_socket.settimeout(self.TIMEOUT)

                    # Địa chỉ server = HOST lấy từ __init__
                    server_address = (self.HOST, self.PORT)

                    # Không cần bind mà send trực tiếp đến server
                    # dữ liệu phải encode dưới dạng byte để gửi
                    client_socket.sendto(f"{self.CODE['CONNECT']}".encode(), server_address)

                    try:
                        # Nhận thông báo từ server
                        response, _ = client_socket.recvfrom(self.BUFFER_SIZE)

                        # Kiểm tra kết nối
                        if response.decode() == "WELCOME":

                            # Lấy danh sách file có thể tải từ server
                            list_files = self.list_files(client_socket, server_address)
                            print("Number of files on server:", len(list_files))

                            print("Connected to server.")

                            for file_name in file_list:
                                # nếu chưa tồn tại trong client thì mởi tải file
                                if self.check_file_downloaded(file_name) == False:
                                    # tiến hành gửi 1 file
                                    self.download_file_parallel(client_socket, file_name, server_address)

                    # Nếu thời gian nhận tin nhắn vượt timeout hay không nhận được lệnh WELCOME thì báo không kết nối server được
                    except socket.timeout:
                        print("Error: Server timeout.")

                print("All files processed. Rechecking input in 5 seconds...")

                time.sleep(5)

        except KeyboardInterrupt:
            print("Client stopped by user (Ctrl + C).")
            return

    # *********************************************************************************************** #


"""
    Test nếu cần thì chạy file nây.
"""
if __name__ == "__main__":
    host = "127.0.0.1"
    client = SocketClientUDP(HOST=host)
    client.start()

# Tại sao là BUFFER_SIZE - 20

"""
    Tại sao là BUFFER_SIZE - 20?
    Trong giao thức UDP, mỗi gói tin đều có phần dữ liệu tiêu đề (header). 
    Header của UDP dài 8 byte, nhưng thường có thêm dữ liệu từ các tầng thấp hơn (ví dụ: IP header dài 20 byte).
    Việc trừ 20 đảm bảo dữ liệu payload thực tế không vượt quá giới hạn tối đa của gói tin 
    (thường là 65,535 byte, bao gồm cả header). Do đó, sử dụng BUFFER_SIZE - 20 để chắc chắn phần dữ liệu vừa với gói tin.
"""

# Tại sao lại tín toán offset như vậy 

"""
    Start Byte: Điểm bắt đầu của đoạn (i * chunk_size).
    End Byte: Điểm kết thúc được tính bằng kích thước tệp hoặc giới hạn của đoạn (start_byte + chunk_size).
"""

# Hiện tại vấn đề resend đang gặp là gì 

# Tại sao khi thay đổi BUFFER size thì tốc độ tải khác nhau
"""
Khi BUFFER_SIZE lớn:
Số lượng gói tin cần gửi ít hơn, giảm overhead từ header và độ trễ mạng, giúp tốc độ tải nhanh hơn.
Khi BUFFER_SIZE nhỏ:
Số lượng gói tin tăng lên, tăng overhead và giảm hiệu quả truyền tải.
"""

# MAX buffer là bao nhiêu
"""
MAX BUFFER_SIZE là bao nhiêu?
Giới hạn lý thuyết của UDP là 65,507 byte (65,535 - 8 byte cho UDP header - 20 byte cho IP header).
"""

# Tại sao lại đọc cả chunk size ???


# cơ chế checksum là gì 
"""
Checksum là một hàm toán học dùng để kiểm tra tính toàn vẹn của dữ liệu. 
"""


# học lại cơ chế gửi seq num, kiểm tra lại resend
"""
Sequence Number (seq_num):

Xác định vị trí của đoạn dữ liệu hiện tại trong tệp.
Tăng giá trị sau mỗi đoạn nhận thành công để đảm bảo dữ liệu được truyền tải đúng thứ tự.
"""


# nonlocal progress bar
"""
Từ khóa nonlocal trong Python cho phép một hàm lồng nhau (nested function) thay đổi biến trong phạm vi bao quanh nó.
Trong mã này, 
progress_bars được khai báo bên ngoài hàm download_chunk nhưng được cập nhật trong hàm để theo dõi tiến độ của mỗi luồng.
"""

#Làm thế nào để cải thiện tốc độ tải file trong trường hợp mạng không ổn định?
"""
Tăng Buffer size
điều chỉnh số luồng 
"""

# Khi client gửi lệnh LIST, server phản hồi dữ liệu theo định dạng nào?
"""
LIST|file1,file2,file3,...,fileN
"""


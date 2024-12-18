import os
import utils

import socket
import time
import math
import threading


class SocketClient:
    HOST = socket.gethostbyname(socket.gethostname())
    PORT = 6969
    INPUT_UPDATE_INTERVAL = 5
    PIPES = 4
    METADATA_SIZE = 1024

    CHUNK_SIZE = 1048576  # 1 MB
    HEADER_SIZE = 8
    DELIMETER_SIZE = 2  # for \r\n
    MESSAGE_SIZE = 256

    DOWNLOAD_DIR = "./"

    # def connect_to_server(self, filename, download_dir, server_ip):
    def connect_to_server(self, filename):
        """
        Kết nối tới máy chủ và gửi yêu cầu tải xuống tệp.
        - filename: tên tệp đầu vào chứa danh sách tệp cần tải.
        - download_dir: thư mục đích lưu tệp tải xuống.
        - server_ip: địa chỉ IP máy chủ.
        """

        # self.HOST = server_ip
        # self.DOWNLOAD_DIR = download_dir

        # Connect to the main server port
        server_address = (self.HOST, self.PORT)

        main_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            main_socket.connect(server_address)
        except Exception as e:
            print(utils.setTextColor("red"), end="")
            print(f"[ERROR] An error occurred: {e}")
            print(utils.setTextColor("white"), end="")
            return

        self.handle_server_connection(filename, main_socket)

        main_socket.close()

    # =============================================== nhớ check những cái đã tồn tại ===============================================
    def save_resource_list_to_file(self, list_file, file_path="receiveList.txt"):
        """
        Ghi danh sách tài nguyên vào tệp tin.
        - list_file: danh sách tài nguyên (list).
        - file_path: đường dẫn tệp tin (mặc định là 'receiveList.txt').
        """
        # remove previous file
        

        try:
            with open(file_path, "w") as file:
                for file_entry in list_file:

                    file_name, file_size = file_entry
                    file_name = file_name.split('/')[-1] # only save name of file
                    file.write(f"{file_name} {file_size}\n")

            print(utils.setTextColor("green"), end="")
            print(f"[STATUS] Saved resource list to {file_path}")
            print(utils.setTextColor("white"), end="")
        except Exception as e:
            print(utils.setTextColor("red"), end="")
            print(f"[ERROR] Could not write to {file_path}: {e}")
            print(utils.setTextColor("white"), end="")

    def handle_server_connection(self, filename, main_socket):

        # Receive a list of available resources from server can be downloaded
        list_file = self.receive_resource_list(main_socket)

        # Remove the spaces
        list_file = list_file.strip()
        list_file = eval(list_file)  # Convert to list

        # HÀM NÀY ĐỂ TỰ ĐỘNG SAVE CÁC INPUT TỪ SERVER -> LƯU VÀO FILE INPUT CỦA CLIENT
        # xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        # Save the list to input.txt
        self.save_resource_list_to_file(list_file) # chỉ dùng để test
        # xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

        print(utils.setTextColor("green"), end="")
        print(f"[RESPONE] List of available resources:")
        print(utils.setTextColor("white"), end="")

        for file in list_file:
            print(f"[LIST] |----------{file}----------|")
        print("Press Enter to continue...")

        input()  # enter to continue

        # Create 4 pipes for data transfer
        socket_list = self.create_pipes(main_socket)

        received_files = []

        # Read the input file
        # needed_files = self.parse_input_file(filename, received_files)

        # while len(received_files) < len(needed_files):
        while True:
            # Reupdate list of files needed to download
            # KIỂM TRA LẠI CÁC FILE TRONG INPUT
            needed_files = self.parse_input_file(filename, received_files)

            cur_index = 0
            while cur_index < len(needed_files):
                # file_info = needed_files[cur_index]
                # Check if the file is already downloaded
                if utils.check_file_exist(needed_files[cur_index]["name"]):
                    print(utils.setTextColor("green"), end="")
                    str_file = needed_files[cur_index]["name"]
                    print(
                        f"[STATUS] File {str_file} has already been downloaded"
                    )
                    print(utils.setTextColor("white"), end="")
                    received_files.append(needed_files[cur_index]["name"])
                    cur_index += 1
                    continue

                time.sleep(5)

                # Receive the chunk from the server
                self.receive_chunk(needed_files, cur_index, main_socket, socket_list)

                # Check file size to ensure file is transferred successfully
                cur_index += self.check_file_integrity(
                    cur_index, needed_files, received_files
                )
            # Chờ 5 giây trước khi quét lại file input.txt
            print("[INFO] Checking for updates in input.txt...")
            time.sleep(5)

            # 5s check và đọc lại file input 1 lần
            # time.sleep(5)

            # Confirmation
            # isCompleted = self.confirm_download(needed_files, received_files)

    def receive_resource_list(self, main_socket):
        """
        - Gửi message đến server yêu cầu nhận LIST các file resource
        - Nhận danh sách các file từ server
        """

        # ---------- GỬI YÊU CẦU CẦN DANH SÁCH CÁC FILE ĐẾN SERVER ----------

        message = "LIST\r\n"
        message = message.ljust(self.MESSAGE_SIZE)

        main_socket.sendall(message.encode())

        # ---------- NHẬN CÁC FILE TRẢ VỀ ----------
        list_file = main_socket.recv(self.MESSAGE_SIZE * 2).decode()

        print(utils.setTextColor("white"), end="")
        print(list_file)
        return list_file

    def create_pipes(self, main_socket):
        # Receive the additional port numbers
        message = "OPEN\r\n"
        message = message.ljust(self.MESSAGE_SIZE)

        main_socket.sendall(message.encode())

        master_port = main_socket.recv(self.MESSAGE_SIZE).decode()

        print(utils.setTextColor("green"), end="")
        print(
            f"[STATUS] We will connect to 4 streams of data at {self.HOST} by requesting on port {master_port} on the server"
        )
        print(utils.setTextColor("white"), end="")

        # ----------------------------------------------------
        # Connect to master port to create 4 pipe
        # ----------------------------------------------------
        socket_list = []
        for i in range(self.PIPES):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.HOST, int(master_port)))
            socket_list.append(sock)
        print(f"[STATUS] Connected to server {self.HOST} on 4 new ports")
        return socket_list

    def receive_chunk(self, needed_files, cur_index, main_socket, socket_list):
        """
        Receive a chunk from the server.
        """
        # Send the chunk message which client want to download from server
        cur_file_size = needed_files[cur_index]["size_bytes"]

        self.CHUNK_SIZE = math.ceil(cur_file_size / self.PIPES)
        
        number_of_chunk = math.ceil(cur_file_size / self.CHUNK_SIZE)

        threads_list = []

        # ============================================================
        #                XỬ LÝ GỬI CÁC CHUNK DỮ LIỆU
        # ============================================================
        # lặp qua các chunk để gửi các request đến server và đăng ký id
        for chunk in range(number_of_chunk):

            start_offset = chunk * self.CHUNK_SIZE
            end_offset = (chunk + 1) * self.CHUNK_SIZE - 1

            if end_offset > cur_file_size - 1:
                end_offset = cur_file_size - 1
            # ------------------------- Send message to server -------------------------
            """
                Cấu trúc message:
                - Tên file cần tải hiện tại
                - kích thước file
                - Offset bắt đầu
                - Offset kết thúc
            """
            message = [
                needed_files[cur_index]["name"],
                cur_file_size,
                start_offset,
                end_offset,
            ]

            print(f"[REQUEST] Requesting chunk {message}")

            # Make the message len MESSAGE_SIZE
            # GIAO THỨC GET
            message = ("GET\r\n" + str(message)).ljust(self.MESSAGE_SIZE)

            # GỬI REQUEST
            main_socket.sendall(message.encode())

            # -----------------------------------------------------------

            # Receive the chunk from server through 4 pipes
            # Xác định pipes
            id = start_offset // self.CHUNK_SIZE % self.PIPES  # ???????????

            # đăng ký và thêm vào danh sách các luồng
            t = threading.Thread(
                target=self.handle_receive_chunk, args=(id, socket_list)
            )

            t.start()
            threads_list.append(t)

        # KHỞI CHẠY CÁC LUỒNG
        for t in threads_list:
            t.join()
        print("[STATUS] All chunks has been received: 100%")

        # Concatenate those files
        for id in range(self.PIPES):
            received_dir = os.path.join(os.getcwd(), "files_received")
            os.makedirs(received_dir, exist_ok=True)  # Tạo thư mục nếu chưa tồn

            path = os.path.join(received_dir, needed_files[cur_index]["name"])

            with open(path, "ab") as file:

                chunk_path = os.path.join(
                    received_dir, f"{needed_files[cur_index]['name']}_{id}"
                )
                if os.path.exists(chunk_path):
                    with open(chunk_path, "rb") as chunk_file:
                        file.write(chunk_file.read())
                    os.remove(chunk_path)
                else:
                    print(f"[ERROR] Chunk file not found: {chunk_path}")
                # with open(f"{path}_{id}", "rb") as chunk_file:

                #     # đọc dữ liệu từ chunk_file vừa mở
                #     # ghi dữ liệu vừa đọc vào cuối file đã mở

                #     file.write(chunk_file.read())

                # # xóa chunk_file vừa tạo
                # os.remove(f"{path}_{id}")

    # ============================================================
    #                XỬ LÝ NHẬN DỮ LIỆU TỪ CÁC CHUNK
    # ============================================================
    def handle_receive_chunk(
        self,
        id,
        socket_list,
    ):
        # Khởi tạo path và thư mục nhận dữ liệu
        received_dir = os.path.join(os.getcwd(), "files_received")
        os.makedirs(received_dir, exist_ok=True)  # Tạo thư mục nếu chưa tồn tại
        # -----------------------------------------------------

        data = socket_list[id].recv(
            self.MESSAGE_SIZE + self.DELIMETER_SIZE + self.CHUNK_SIZE
        )

        if data:
            # giải mã message
            message, chunk_data = data.split(b"\r\n", 1)
            filename, file_size, start_offset, end_offset = eval(message.strip())

            # Progress bar
            print(
                f"Downloading file {filename} part {id} .... {int(utils.count_files_with_prefix(received_dir, filename) / self.PIPES * 100)}%"
            )

            print(f"[RESPOND] Received chunk {message.strip()}")

            # ---------------------------------------------------------------------
            # Thêm các tệp vào folder disc
            with open(os.path.join(received_dir, f"{filename}_{id}"), "wb") as file:
                file.write(chunk_data)

            # ---------------------------------------------------------------------

    def check_file_integrity(self, cur_index, needed_files, received_files):

        received_dir = os.path.join(os.getcwd(), "files_received")
        path = os.path.join(received_dir, needed_files[cur_index]["name"])

        if utils.get_file_size(path) == needed_files[cur_index]["size_bytes"]:
            print(utils.setTextColor("green"), end="")
            print(
                f"[SUCCESS] File {needed_files[cur_index]} has been downloaded successfully"
            )
            print(utils.setTextColor("white"), end="")
            received_files.append(needed_files[cur_index]["name"])
            return 1
        else:
            print(utils.setTextColor("green"), end="")
            print(
                f"[FAIL] File {needed_files[cur_index]} has been downloaded unsuccessfully"
            )
            print(
                f"[DETAIL] Expected file size: {needed_files[cur_index]['size_bytes']} bytes"
            )
            print(
                f"[DETAIL] Received file size: {utils.get_file_size(needed_files[cur_index]['name'])} bytes"
            )
            print(utils.setTextColor("red"), end="")
            print(
                f"id: {cur_index} bytes"
            )
            print(utils.setTextColor("white"), end="")
            return 0

    def confirm_download(self, needed_files, received_files):

        print(utils.setTextColor("green"), end="")
        print(f"Downloads successfully {len(received_files)}/{len(needed_files)} files")
        print(utils.setTextColor("white"), end="")

        if len(received_files) / len(needed_files) == 1:
            return True
        else:
            return False

    def parse_input_file(self, file_path, received_files):
        """
        Reads a file with image data and returns a list of dictionaries with the parsed data.

        Args:
            file_path (str): The path to the file containing the image data.
            received_files (list): A list of file names already received.

        Returns:
            list: A list of dictionaries with keys 'name', 'size', and 'size_bytes'.
        """
        data = []

        try:
            with open(file_path, "r+") as file:
                for line in file:
                    line = line.strip()
                    if line:
                        with open("receiveList.txt", "r+") as recvfile:
                            for recvline in recvfile:
                                if recvline:
                                    parts = recvline.split()
                                    # Split the line into components
                                    if len(parts) == 2:
                                        name, size = parts

                                        # Parse size in bytes
                                        size_bytes = int(size)

                                        # Check if the file has already been received
                                        if name not in received_files and name == line:
                                            # Append the data as a dictionary
                                            data.append(
                                                {
                                                    "name": name,
                                                    "size": size,
                                                    "size_bytes": size_bytes,
                                                }
                                            )
        except Exception as e:
            print(utils.setTextColor("red"), end="")
            print(f"[ERROR] An error occurred: {e}")
            print(utils.setTextColor("white"), end="")

        return data
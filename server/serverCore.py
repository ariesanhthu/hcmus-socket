import utils
import socket
import threading


class SocketServer:
    HOST = socket.gethostbyname(socket.gethostname())
    PORT = 6969
    HEADER_SIZE = 8
    PIPES = 4
    RESOURCE_PATH = "./resources/"
    MESSAGE_SIZE = 1024

    CODE = {"LIST": "LIST", "OPEN": "OPEN", "GET": "GET"}

    def __init__(self):
        print("[STATUS] Initializing the server...")
        self.stop_event = threading.Event()

    def create_server(self):
        """
        Create a server that listens for incoming connections.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            """
            Create a server socket.

                - socket.AF_INET: Chỉ định loại địa chỉ sử dụng IPv4.
                - socket.SOCK_STREAM: Chỉ định kiểu socket là TCP

            """
            try:
                # Bind the socket to the address
                server_socket.bind((self.HOST, self.PORT))
            except Exception as e:
                print(f"[ERROR] {e}")
                return

            try:
                """
                SERVER LUÔN CHẠY ĐỂ LẮNG NGHE CÁC KẾT NỐI TỪ CLIENT
                """
                while not self.stop_event.is_set():
                    # ----------------------------------------------------------------------------------
                    # Listen for incoming connections

                    # Tham số hàng đợi (số kết nối mặc định được phép kêt nối) phụ thuộc vào hệ thống
                    server_socket.listen()

                    print(f"[STATUS] Server listening on {self.HOST}:{self.PORT}")

                    """
                        Chấp nhận kết nối từ một client
                            - master: Một socket mới dành riêng để giao tiếp với client.
                            - addr: Địa chỉ của client (bao gồm IP và cổng).
                    """
                    master, addr = server_socket.accept()

                    # Đặt timeout (thời gian chờ tối đa) cho kết nối với client là 100 giây
                    # Nếu sau thời gian này không có hoạt động, kết nối sẽ tự động đóng
                    master.settimeout(100)

                    print("[STATUS] Connected by", addr)

                    # ----------------------------------------------------------------------------------

                    # Tạo các thread để xử lý các kết nối từ client

                    client_thread = threading.Thread(
                        target=self.handle_client_connection, args=(master, addr)
                    )

                    client_thread.start()

            except Exception as e:
                print(f"[ERROR] {e}")

            finally:
                print("[STATUS] Server shutting down...")
                server_socket.close()

    def handle_client_connection(self, master, addr):
        pipes_list = []

        while not self.stop_event.is_set():
            try:
                data = master.recv(self.MESSAGE_SIZE)
                if not data:
                    break
                data = data.decode().strip()
                message = data.split("\r\n")[0]

                if message == self.CODE["LIST"]:
                    self.send_resources_list(master)
                elif message == self.CODE["OPEN"]:
                    pipes_list = self.create_pipes(master)
                elif message == self.CODE["GET"]:
                    payload = data.split("\r\n")[1]
                    self.send_chunk(master, payload, addr, pipes_list)
            except socket.timeout:
                print("[STATUS] Connection timed out.")
                break
            except Exception as e:
                print(f"[ERROR] {e}")
                break

    def send_resources_list(self, master):
        list_file = utils.list_all_file_in_directory(self.RESOURCE_PATH)
        list_file = utils.standardize_str(str(list_file), self.MESSAGE_SIZE)
        master.sendall(f"{list_file}".encode())

    def create_pipes(self, master):
        master_port = utils.find_free_port(self.HOST)

        master.sendall(f"{master_port}".encode())

        master_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        master_socket.bind((self.HOST, master_port))
        pipes_list = []
        for _ in range(self.PIPES):
            master_socket.listen(1)
            pipe_conn, addr = master_socket.accept()
            pipe_conn.settimeout(10)
            print(f"[STATUS] Listening on master port {addr}")
            pipes_list.append(pipe_conn)
        return pipes_list

    def send_chunk(self, master, message, addr, pipes_list):
        if not message:
            print("[STATUS] Client disconnected")

        print(f"[REQUEST] Received request for chunk {message.strip()} from {addr}")

        t = threading.Thread(target=self.handle_send_chunk, args=(message, pipes_list))
        t.start()
        t.join()

    def handle_send_chunk(self, message, pipes_list):

        filename, file_size, start_offset, end_offset = eval(message.strip())

        with open(self.RESOURCE_PATH + filename, "rb") as file:
            file.seek(start_offset)
            chunk = file.read(end_offset - start_offset + 1)
            data = f"{message}\r\n".encode() + chunk

            self.CHUNK_SIZE = end_offset - start_offset + 1
            id = (start_offset // self.CHUNK_SIZE) % self.PIPES
            pipes_list[id].sendall(data)
            print(f"[RESPOND] Sent chunk {message.strip()} to {pipes_list[id]}")

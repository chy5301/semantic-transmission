"""中继传输模块：发送端到接收端的数据传输。

支持两种传输模式：
    - LocalRelay：内存传递，单机调试用
    - SocketRelaySender / SocketRelayReceiver：TCP socket 传输，双机演示用

传输协议（length-prefixed framing）：
    每个字段由 4 字节大端 uint32 长度头 + 原始数据组成，依次为：
    [edge_image_length][edge_image][text_length][text][metadata_length][metadata]
"""

import json
import queue
import socket
import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TransmissionPacket:
    """传输数据包：边缘图 + prompt 文本 + 元数据。"""

    edge_image: bytes
    prompt_text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _serialize_packet(packet: TransmissionPacket) -> bytes:
    """将 TransmissionPacket 序列化为二进制帧。"""
    text_bytes = packet.prompt_text.encode("utf-8")
    metadata_bytes = json.dumps(packet.metadata, ensure_ascii=False).encode("utf-8")

    parts = []
    for data in (packet.edge_image, text_bytes, metadata_bytes):
        parts.append(struct.pack(">I", len(data)))
        parts.append(data)

    return b"".join(parts)


def _recv_exactly(sock: socket.socket, n: int) -> bytes:
    """从 socket 精确读取 n 字节。"""
    chunks = []
    remaining = n
    while remaining > 0:
        chunk = sock.recv(min(remaining, 65536))
        if not chunk:
            raise ConnectionError("连接在数据传输中断开")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _deserialize_packet(data: bytes) -> TransmissionPacket:
    """从二进制帧反序列化 TransmissionPacket。"""
    offset = 0

    def read_field() -> bytes:
        nonlocal offset
        (length,) = struct.unpack(">I", data[offset : offset + 4])
        offset += 4
        field_data = data[offset : offset + length]
        offset += length
        return field_data

    edge_image = read_field()
    prompt_text = read_field().decode("utf-8")
    metadata = json.loads(read_field().decode("utf-8"))

    return TransmissionPacket(
        edge_image=edge_image, prompt_text=prompt_text, metadata=metadata
    )


def _receive_packet_from_socket(sock: socket.socket) -> TransmissionPacket:
    """从 socket 连接读取一个完整的 TransmissionPacket。"""
    parts = []
    for _ in range(3):
        header = _recv_exactly(sock, 4)
        (length,) = struct.unpack(">I", header)
        field_data = _recv_exactly(sock, length)
        parts.append(field_data)

    edge_image, text_bytes, metadata_bytes = parts
    return TransmissionPacket(
        edge_image=edge_image,
        prompt_text=text_bytes.decode("utf-8"),
        metadata=json.loads(metadata_bytes.decode("utf-8")),
    )


class BaseRelay(ABC):
    """中继传输抽象基类。"""

    @abstractmethod
    def send(self, packet: TransmissionPacket) -> None:
        """发送数据包。"""

    @abstractmethod
    def receive(self, timeout: float | None = None) -> TransmissionPacket:
        """接收数据包。

        Args:
            timeout: 超时秒数。None 表示无限等待。

        Raises:
            TimeoutError: 超时未收到数据。
        """


class LocalRelay(BaseRelay):
    """内存中继：使用队列在同一进程内传递数据。"""

    def __init__(self) -> None:
        self._queue: queue.Queue[TransmissionPacket] = queue.Queue()

    def send(self, packet: TransmissionPacket) -> None:
        self._queue.put(packet)

    def receive(self, timeout: float | None = None) -> TransmissionPacket:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError("LocalRelay 接收超时")


class SocketRelaySender:
    """Socket 中继发送端：连接到接收端并发送数据。"""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self._socket: socket.socket | None = None

    def connect(self) -> None:
        """建立到接收端的 TCP 连接。"""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect((self.host, self.port))

    def send(self, packet: TransmissionPacket) -> None:
        """发送数据包。如未连接则自动连接。"""
        if self._socket is None:
            self.connect()
        data = _serialize_packet(packet)
        self._socket.sendall(data)

    def close(self) -> None:
        """关闭连接。"""
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def __enter__(self) -> "SocketRelaySender":
        self.connect()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class SocketRelayReceiver:
    """Socket 中继接收端：监听端口并接收数据。"""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self._server: socket.socket | None = None
        self._conn: socket.socket | None = None

    def start(self) -> None:
        """启动监听。"""
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((self.host, self.port))
        self._server.listen(1)

    def accept(self, timeout: float | None = None) -> None:
        """等待发送端连接。

        Args:
            timeout: 超时秒数。None 表示无限等待。

        Raises:
            TimeoutError: 超时未收到连接。
        """
        if self._server is None:
            self.start()
        self._server.settimeout(timeout)
        try:
            self._conn, _ = self._server.accept()
        except socket.timeout:
            raise TimeoutError("SocketRelayReceiver 等待连接超时")

    def receive(self, timeout: float | None = None) -> TransmissionPacket:
        """接收一个数据包。

        如未建立连接则先等待连接。

        Args:
            timeout: 超时秒数。None 表示无限等待。

        Raises:
            TimeoutError: 超时未收到数据。
            ConnectionError: 连接断开。
        """
        if self._conn is None:
            self.accept(timeout=timeout)
        self._conn.settimeout(timeout)
        try:
            return _receive_packet_from_socket(self._conn)
        except socket.timeout:
            raise TimeoutError("SocketRelayReceiver 接收数据超时")

    def close(self) -> None:
        """关闭连接和服务端。"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        if self._server is not None:
            self._server.close()
            self._server = None

    def __enter__(self) -> "SocketRelayReceiver":
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

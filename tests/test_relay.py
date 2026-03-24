"""中继传输模块测试。"""

import threading
import time

import pytest

from semantic_transmission.pipeline.relay import (
    LocalRelay,
    SocketRelayReceiver,
    SocketRelaySender,
    TransmissionPacket,
    _deserialize_packet,
    _serialize_packet,
)


# ── TransmissionPacket ──


class TestTransmissionPacket:
    def test_basic_creation(self):
        packet = TransmissionPacket(
            edge_image=b"\x89PNG\r\n",
            prompt_text="A red car on a highway",
            metadata={"width": 1024, "height": 768},
        )
        assert packet.edge_image == b"\x89PNG\r\n"
        assert packet.prompt_text == "A red car on a highway"
        assert packet.metadata == {"width": 1024, "height": 768}

    def test_default_metadata(self):
        packet = TransmissionPacket(edge_image=b"img", prompt_text="text")
        assert packet.metadata == {}

    def test_metadata_independence(self):
        p1 = TransmissionPacket(edge_image=b"a", prompt_text="t1")
        p2 = TransmissionPacket(edge_image=b"b", prompt_text="t2")
        p1.metadata["key"] = "value"
        assert "key" not in p2.metadata


# ── 序列化/反序列化 ──


class TestSerialization:
    def test_roundtrip(self):
        packet = TransmissionPacket(
            edge_image=b"\x89PNG\r\nfake image data" * 100,
            prompt_text="A scenic mountain landscape with snow-capped peaks",
            metadata={"timestamp": 1234567890, "size": [1024, 768]},
        )
        data = _serialize_packet(packet)
        restored = _deserialize_packet(data)
        assert restored.edge_image == packet.edge_image
        assert restored.prompt_text == packet.prompt_text
        assert restored.metadata == packet.metadata

    def test_empty_fields(self):
        packet = TransmissionPacket(edge_image=b"", prompt_text="", metadata={})
        data = _serialize_packet(packet)
        restored = _deserialize_packet(data)
        assert restored.edge_image == b""
        assert restored.prompt_text == ""
        assert restored.metadata == {}

    def test_unicode_text(self):
        packet = TransmissionPacket(
            edge_image=b"img",
            prompt_text="山间小路，阳光透过树叶",
            metadata={"描述": "中文元数据"},
        )
        data = _serialize_packet(packet)
        restored = _deserialize_packet(data)
        assert restored.prompt_text == "山间小路，阳光透过树叶"
        assert restored.metadata["描述"] == "中文元数据"

    def test_large_image(self):
        large_image = b"\x00\xff" * 500_000  # 1MB
        packet = TransmissionPacket(edge_image=large_image, prompt_text="large test")
        data = _serialize_packet(packet)
        restored = _deserialize_packet(data)
        assert restored.edge_image == large_image


# ── LocalRelay ──


class TestLocalRelay:
    def test_send_receive(self):
        relay = LocalRelay()
        packet = TransmissionPacket(edge_image=b"edge", prompt_text="hello")
        relay.send(packet)
        received = relay.receive(timeout=1.0)
        assert received.edge_image == packet.edge_image
        assert received.prompt_text == packet.prompt_text

    def test_fifo_order(self):
        relay = LocalRelay()
        for i in range(5):
            relay.send(
                TransmissionPacket(edge_image=bytes([i]), prompt_text=f"msg-{i}")
            )
        for i in range(5):
            received = relay.receive(timeout=1.0)
            assert received.prompt_text == f"msg-{i}"
            assert received.edge_image == bytes([i])

    def test_receive_timeout(self):
        relay = LocalRelay()
        with pytest.raises(TimeoutError):
            relay.receive(timeout=0.1)

    def test_threaded_send_receive(self):
        relay = LocalRelay()
        packet = TransmissionPacket(edge_image=b"data", prompt_text="threaded")

        def sender():
            time.sleep(0.1)
            relay.send(packet)

        t = threading.Thread(target=sender)
        t.start()
        received = relay.receive(timeout=2.0)
        t.join()
        assert received.prompt_text == "threaded"


# ── SocketRelay ──


def _find_free_port() -> int:
    """获取一个可用的临时端口。"""
    import socket as _socket

    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestSocketRelay:
    def test_send_receive(self):
        port = _find_free_port()
        packet = TransmissionPacket(
            edge_image=b"\x89PNG fake data",
            prompt_text="Socket relay test",
            metadata={"test": True},
        )
        received_packets = []
        errors = []

        def receiver_thread():
            try:
                with SocketRelayReceiver("127.0.0.1", port) as receiver:
                    received = receiver.receive(timeout=5.0)
                    received_packets.append(received)
            except Exception as e:
                errors.append(e)

        t = threading.Thread(target=receiver_thread)
        t.start()
        time.sleep(0.2)  # 等待 receiver 启动

        with SocketRelaySender("127.0.0.1", port) as sender:
            sender.send(packet)

        t.join(timeout=5.0)
        assert not errors, f"接收端出错: {errors}"
        assert len(received_packets) == 1
        received = received_packets[0]
        assert received.edge_image == packet.edge_image
        assert received.prompt_text == packet.prompt_text
        assert received.metadata == packet.metadata

    def test_large_data(self):
        port = _find_free_port()
        large_image = b"\xab\xcd" * 500_000  # 1MB
        packet = TransmissionPacket(
            edge_image=large_image,
            prompt_text="Large data test " * 100,
            metadata={"size": len(large_image)},
        )
        received_packets = []

        def receiver_thread():
            with SocketRelayReceiver("127.0.0.1", port) as receiver:
                received_packets.append(receiver.receive(timeout=10.0))

        t = threading.Thread(target=receiver_thread)
        t.start()
        time.sleep(0.2)

        with SocketRelaySender("127.0.0.1", port) as sender:
            sender.send(packet)

        t.join(timeout=10.0)
        assert len(received_packets) == 1
        assert received_packets[0].edge_image == large_image
        assert received_packets[0].metadata["size"] == len(large_image)

    def test_multiple_packets(self):
        port = _find_free_port()
        packets = [
            TransmissionPacket(edge_image=bytes([i]), prompt_text=f"pkt-{i}")
            for i in range(3)
        ]
        received_packets = []

        def receiver_thread():
            with SocketRelayReceiver("127.0.0.1", port) as receiver:
                for _ in range(3):
                    received_packets.append(receiver.receive(timeout=5.0))

        t = threading.Thread(target=receiver_thread)
        t.start()
        time.sleep(0.2)

        with SocketRelaySender("127.0.0.1", port) as sender:
            for pkt in packets:
                sender.send(pkt)

        t.join(timeout=5.0)
        assert len(received_packets) == 3
        for i, received in enumerate(received_packets):
            assert received.prompt_text == f"pkt-{i}"

    def test_receiver_accept_timeout(self):
        port = _find_free_port()
        receiver = SocketRelayReceiver("127.0.0.1", port)
        receiver.start()
        try:
            with pytest.raises(TimeoutError):
                receiver.accept(timeout=0.1)
        finally:
            receiver.close()

    def test_sender_connect_error(self):
        port = _find_free_port()
        sender = SocketRelaySender("127.0.0.1", port)
        with pytest.raises(ConnectionRefusedError):
            sender.connect()

    def test_context_manager_cleanup(self):
        port = _find_free_port()
        receiver = SocketRelayReceiver("127.0.0.1", port)
        with receiver:
            assert receiver._server is not None
        assert receiver._server is None

        sender = SocketRelaySender("127.0.0.1", port)
        sender.close()  # close 未连接状态不应报错
        assert sender._socket is None

    def test_unicode_over_socket(self):
        port = _find_free_port()
        packet = TransmissionPacket(
            edge_image=b"edge",
            prompt_text="高速公路上的红色汽车",
            metadata={"场景": "户外"},
        )
        received_packets = []

        def receiver_thread():
            with SocketRelayReceiver("127.0.0.1", port) as receiver:
                received_packets.append(receiver.receive(timeout=5.0))

        t = threading.Thread(target=receiver_thread)
        t.start()
        time.sleep(0.2)

        with SocketRelaySender("127.0.0.1", port) as sender:
            sender.send(packet)

        t.join(timeout=5.0)
        assert received_packets[0].prompt_text == "高速公路上的红色汽车"
        assert received_packets[0].metadata["场景"] == "户外"

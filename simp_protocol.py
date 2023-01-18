from __future__ import annotations

import socket

from enum import IntFlag, auto
from dataclasses import dataclass
from result import as_result, Ok, Err

from typing import Protocol, TypeVar, Generic, Type as T


Self = TypeVar("Self")


class BytesConvertible(Protocol):
    """
    Generic protocol for objects that can be converted to and from bytes.
    """
    def into_bytes(self) -> bytes:
        ...

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        ...


B = TypeVar("B", bound=BytesConvertible)


class parse(Generic[B]):
    """
    Takes a byte-stream and parses it into a tuple of the remaining data and the parsed object.
    """
    def __new__(cls, data: bytes, length: int, t: T[B], /) -> tuple[bytes, B]:
        return data[length:], t.from_bytes(data[:length])


class Type(IntFlag):
    """
    Type of message.

    Control: Control message, carries information about the connection and commands.
    Chat: Chat message, carries message content about the chat.
    """
    CONTROL = auto()
    CHAT = auto()

    def into_bytes(self) -> bytes:
        return self.value.to_bytes(1, "big")

    @classmethod
    def from_bytes(cls, data: bytes) -> Type:
        return cls(int.from_bytes(data, "big"))


class Operation(IntFlag):
    """
    Kind of operation of the message.

    ERR: Error, the message contains an error.
    SYN: Initialise connection, the message is the first message of the connection.
    ACK: Acknowledge, the message is an acknowledgement of a previous message.
    FIN: Terminate connection, the message is the last message of the connection.
    """
    ERR = 0x1
    SYN = 0x2
    ACK = 0x4
    FIN = 0x8

    def __str__(self) -> str:
        return self.name

    def into_bytes(self) -> bytes:
        return self.value.to_bytes(1, "big")

    @classmethod
    def from_bytes(cls, data: bytes) -> Operation:
        return cls(int.from_bytes(data, "big"))


class Sequence(IntFlag):
    """
    Signals if the message is a retransmission or not.

    RE: Retransmission, the message is a retransmission of a previous message.
    NORE: Not a retransmission, the message is not a retransmission of a previous message.
    """
    RE = auto()
    NORE = auto()

    def into_bytes(self) -> bytes:
        return self.value.to_bytes(1, "big")

    @classmethod
    def from_bytes(cls, data: bytes) -> Sequence:
        return cls(int.from_bytes(data, "big"))


@dataclass
class Header:
    """
    SIMP Header
    
    type: Type of message.
    operation: Kind of operation of the message.
    sequence: Signals if the message is a retransmission or not.
    user: Username of the sender.
    length: Length of the message.
    """
    type: Type
    operation: Operation
    sequence: Sequence
    user: str
    length: int

    def into_bytes(self) -> bytes:
        return (
            self.type.into_bytes()
            + self.operation.into_bytes()
            + self.sequence.into_bytes()
            + self.user.encode()
            + self.length.to_bytes(4, "big")
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> Header:
        data, _type = parse[Type](data, 1, Type)
        data, _operation = parse[Operation](data, 1, Operation)
        data, _sequence = parse[Sequence](data, 1, Sequence)
        _user, data = data[:32].decode(), data[32:]
        _length = int.from_bytes(data[:4], "big")
        return cls(_type, _operation, _sequence, _user, _length)


@dataclass
class Message:
    """
    SIMP Message

    header: Header of the message.
    data: Data of the message.
    """
    header: Header
    data: str

    @property
    def is_control(self) -> bool:
        return self.header.type == Type.CONTROL

    @property
    def is_chat(self) -> bool:
        return self.header.type == Type.CHAT

    @property
    def operation(self) -> Operation:
        return self.header.operation

    @property
    def type(self) -> Type:
        return self.header.type

    def into_bytes(self) -> bytes:
        return self.header.into_bytes() + self.data.encode()

    @classmethod
    def from_bytes(cls, data: bytes) -> Message:
        _header = Header.from_bytes(data[:39])
        _data = data[39:].decode()
        return cls(_header, _data)

    @classmethod
    def chat(cls, user: str, content: str, *, resend: bool = False) -> Message:
        """
        Send a chat message.

        user: Username of the sender.
        content: Content of the message.
        resend: Signals if the message is a retransmission or not.
        """

        # pad and crop the user str to be exactly 32 bytes
        user = user.ljust(32, "\0")[:32]

        _header = Header(
            Type.CHAT,
            Operation.ERR,
            Sequence.RE if resend else Sequence.NORE,
            user,
            len(content),
        )

        return cls(_header, content)

    @classmethod
    def control(
        cls, user: str, operation: Operation, *, resend: bool = False, message: str = ""
    ) -> Message:
        """
        Send a control message.

        user: Username of the sender.
        operation: Kind of operation of the message.
        resend: Signals if the message is a retransmission or not.
        message: Content of the message. (Only meant to be used with ERR messages)
        """
        # pad and crop the user str to be exactly 32 bytes
        user = user.ljust(32, "\0")[:32]

        if operation != Operation.ERR and message:
            raise ValueError(
                "[SIMP ERROR]: Message can only be set for ERR operations!"
            )

        _header = Header(
            Type.CONTROL,
            operation,
            Sequence.RE if resend else Sequence.NORE,
            user,
            len(message),
        )

        return cls(_header, message)


class ConnectionRefused(Exception):
    """
    Raised when the connection is refused.
    """
    pass


@dataclass
class SimpCommunication:
    """
    A SIMP server/client communication implementation.

    host: Host of the server/client.
    port: Port of the server/client.
    username: Username of the client.
    connection: Connection of the server/client.
    busy: Signals if the connection is busy or not.
    """
    host: str
    port: int
    username: str
    connection: socket.socket | None = None
    busy: bool = False

    def connect(self) -> None:
        """
        Connect to the server/client.
        Defaults to blanket empty implementation.
        """
        ...

    def run(self) -> None:
        """
        Main loop of the server/client.
        """
        self.connect()

        latest_message: Message | None = None

        while True:
            try:
                data, address = self.connection.recvfrom(1024)
            except RuntimeError:
                if latest_message is not None:
                    print(f"LATEST MESSAGE: {latest_message}")
                    repeat = latest_message
                    repeat.header.sequence = Sequence.RE
                    self.connection.sendto(repeat.into_bytes(), address)
                else:
                    print("No message to resend")
                continue

            decoded_message = Message.from_bytes(data)

            response = self.handle_message(decoded_message)

            match response:
                case Ok(message):
                    if message.type == Type.CHAT:
                        # If the user input is quit, then quit the connection
                        if message.data == "quit":
                            self.connection.sendto(Message.control(self.username, Operation.FIN).into_bytes(), address)
                            break

                        # After a message is sent, the connection will set a timeout of 5 seconds
                        # After 5 seconds, the connection will resend the message
                        self.connection.settimeout(5)

                    latest_message = message

                    self.connection.sendto(message.into_bytes(), address)

                    if message.type == Type.CONTROL and message.operation == Operation.ERR:
                        self.connection.sendto(Message.control(self.username, Operation.FIN).into_bytes(), address)

                case Err(error):
                    # If an error occurs, then quit the connection
                    print(f"<ERROR> ABORTING CONNECTION.\n{repr(error)}")
                    break

    @as_result(ConnectionRefused)
    def handle_message(self, message: Message) -> Message:
        """
        Handle a message.

        message: Message to handle.
        """
        match message.type:
            case Type.CONTROL:
                match message.operation:
                    case Operation.SYN:
                        # If the connection busy, then refuse the connection
                        if self.busy:
                            return Message.control(
                                self.username,
                                Operation.ERR,
                                message=f"User already in another chat",
                            )
                        else:
                            # Decide if the connection is accepted or not (default Yes)
                            response = input("Accept connection? [Y/n] ").lower()

                            match response:
                                case "n":
                                    return Message.control(self.username, Operation.FIN)
                                case "y" | "":
                                    # Send a SYN+ACK message, second part of the handshake
                                    return Message.control(
                                        self.username, Operation.SYN ^ Operation.ACK
                                    )
                    case Operation.ACK:
                        # If the connection is accepted, then set the connection to busy
                        self.busy = True
                        print(f"Connected! with {message.header.user}")
                        response = input(f"[{self.username}]: ")
                        return Message.chat(f"({self.host}:{self.port}){self.username}", response)
                    case Operation.FIN:
                        # If the connection is closed, then quit the connection
                        self.busy = False
                        raise ConnectionRefused("Connection closed")
                    case Operation.ERR:
                        # If an error occurs, then quit the connection
                        self.busy = False
                        raise ConnectionRefused(message.data)
                    # Python match case doesn't allow for XOR operations
                    # This fallback is the only other possible case
                    case _:  # SYN-ACK
                        # If the user is busy, then send an error message
                        if self.busy:
                            return Message.control(
                                self.username,
                                Operation.ERR,
                                message=f"{self.username} is busy",
                            )
                        else:
                            # Complete the three-way handshake by sending the final ACK
                            self.busy = True
                            print(f"Connecting with {message.header.user}...")
                            return Message.control(self.username, Operation.ACK)
            # If a chat message was sent
            case Type.CHAT:
                # If the user is in a chat, then print the message and send a response
                if self.busy:
                    print(f"[{message.header.user}]: {message.data}")
                    response = input(f"[{self.username}]: ")
                    return Message.chat(f"({self.host}:{self.port}){self.username}", response)
                # If the user is not in a chat, then send an error message
                else:
                    return Message.control(
                        self.username,
                        Operation.ERR,
                        message=f"{self.username} is not in a chat",
                    )

    def bind(self) -> None:
        """
        Bind a server/client to a port and a host.
        Defaults to blanket empty implementation.
        """
        ...

    def __enter__(self) -> SimpCommunication:
        """
        Allows us to write:
            ```
            with SimpCommunication(...) as simp:
                ...
            ```
        """
        self.connection = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.bind()
        return self

    def __exit__(self, *_) -> None:
        """
        Second part of the context manager protocol.

        Closes the connection.
        """
        self.connection.close()

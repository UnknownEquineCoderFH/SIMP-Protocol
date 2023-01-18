from __future__ import annotations

import time

from dataclasses import dataclass
from argparse import ArgumentParser

from simp_protocol import *


@dataclass
class Client(SimpCommunication):
    """
    SIMP Client

    A client is a communication endpoint that can send and receive messages,
    and initialises the connection with the server.
    """
    def connect(self) -> None:
        while (connect := input("Connect to server? [Y/n] ").lower()) not in (
            "y",
            "n",
            "",
        ):
            print("Invalid input")

        match connect:
            case "n":
                return 0
            case "y" | "":
                # Send a SYN message to the server (first part of the handshake)
                self.connection.sendto(
                    Message.control(self.username, Operation.SYN).into_bytes(),
                    (self.host, self.port),
                )
   


def main(host: str, port: int) -> Client:
    username = input("Insert username: ")

    client = Client(host, port, username)

    return client


if __name__ == "__main__":
    parser = ArgumentParser()

    parser.add_argument("--host", default="localhost", help="The host to listen on")
    parser.add_argument("--port", type=int, default=8745, help="The port to listen on")

    args = parser.parse_args()

    try:
        with main(args.host, args.port) as client:
            client.run()

        raise SystemExit(0)
    except KeyboardInterrupt:
        print("Exiting...")
        time.sleep(1)
        raise SystemExit(0)

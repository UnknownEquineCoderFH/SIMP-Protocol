from __future__ import annotations

import time

from dataclasses import dataclass
from argparse import ArgumentParser

from simp_protocol import *


@dataclass
class Server(SimpCommunication):
    """
    SIMP Server
    
    A server is a communication endpoint that can send and receive messages,
    and is bound to a specific port and host.
    """
    def bind(self) -> None:
        self.connection.bind((self.host, self.port))
        self.connection.settimeout(None)



def main(host: str, port: int) -> Server:
    server = Server(host, port, "Server")

    return server


if __name__ == "__main__":
    parser = ArgumentParser()

    parser.add_argument("--host", default="localhost", help="The host to listen on")
    parser.add_argument("--port", type=int, default=8745, help="The port to listen on")

    args = parser.parse_args()

    try:
        with main(args.host, args.port) as server:
            server.run()

        raise SystemExit(0)
    except KeyboardInterrupt:
        print("Exiting...")
        time.sleep(1)
        raise SystemExit(0)

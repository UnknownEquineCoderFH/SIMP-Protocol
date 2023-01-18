# SIMP Protocol Implementation

## AUTHORS: Antonino Rossi, Bertold Vincze

## How to Use

* Install Dependencies

```bash
pip install -r requirements.txt
```

* Run the server

```bash
python simp_server.py
```

* Run the client

```bash
python simp_client.py
```

## The server will send the first message in the conversation
## TIMEOUT time is set to 5 seconds for both client and server, after that it will send the message again
## with sequence number 1

### Most of the implementation can be found in the simp_protocol.py file
### Especially, Server and Client only differ by a single method implementation
### Please review `SimpCommunication` class for understanding implementation details

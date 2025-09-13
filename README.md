# AnyPC Server

AnyPC is a software application that enables users to gain full control of computers remotely. This repository contains the server version of AnyPC, implemented in Python.

Server created by Ilai Keinan.
Client created by Alon Horesh.

Client is at [AlonHor/AnyPC](https://github.com/AlonHor/AnyPC).

## Table of Contents

- [Description](#description)
- [Features](#features)
- [Technologies](#technologies)
- [Protocol](#protocol)
- [Setup](#setup)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)

## Description

AnyPC allows users to remotely access and control computers from anywhere in the world. This client version connects to the AnyPC server, providing a seamless and secure remote control experience.

## Features

- Remote desktop control (30fps)
- File transfer between client and server
- Secure communication with encryption
- Cross-platform support

## Technologies

- **Python**: The entire client application is developed using Python.

## Protocol
WRPC is the protocol we've designed and implemented to allow for a smooth experience of controlling remote computers over the network.

The protocol documentation can be found [here](https://github.com/K9Developer/AnyPC/blob/main/WRPC.pdf).

## Setup

To set up the project locally, follow these steps:

1. Clone the repository:
   ```bash
   git clone https://github.com/K9Developer/AnyPC.git
   ```

2. Navigate to the project directory:
   ```bash
   cd AnyPC
   ```

3. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

4. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

To start using the AnyPC server, run the main application script:

```bash
python server.py
```

After that you'll see:
```
Initializing screen control sockets...

   ▄████████ ███▄▄▄▄   ▄██   ▄          ▄███████▄  ▄████████           _______
  ███    ███ ███▀▀▀██▄ ███   ██▄       ███    ███ ███    ██           |.-----.|
  ███    ███ ███   ███ ███▄▄▄███       ███    ███ ███    █▀           ||x . x||
  ███    ███ ███   ███ ▀▀▀▀▀▀███       ███    ███ ███                 ||_.-._||
▀███████████ ███   ███ ▄██   ███     ▀█████████▀  ███                 `--)-(--`
  ███    ███ ███   ███ ███   ███       ███        ███    █▄          __[=== o]___
  ███    █▀   ▀█   █▀   ▀█████▀       ▄████▀      ████████▀         |:::::::::::|\
                                                                    `-=========-` ()

Starting server...
Initializing server socket...
Server started on port 40003
Adding event listeners...
14 event listeners added!
Server started successfully!

Waiting for clients to connect...
```
And then you'll need to wait for clients to connect.

## Contributing

We welcome contributions to the AnyPC project. To contribute, please follow these steps:

1. Fork the repository.
2. Create a new branch with a descriptive name:
   ```bash
   git checkout -b my-feature-branch
   ```
3. Make your changes.
4. Commit your changes with a meaningful commit message:
   ```bash
   git commit -m "Add new feature"
   ```
5. Push your changes to your fork:
   ```bash
   git push origin my-feature-branch
   ```
6. Open a pull request to the `main` branch of the original repository.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.

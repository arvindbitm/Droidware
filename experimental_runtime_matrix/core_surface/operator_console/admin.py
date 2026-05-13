# #!/usr/bin/env python3
# import asyncio
# import ssl
# import logging
# import json

# # TLS Configuration
# USE_TLS = True
# TLS_CERT_FILE = "cert.pem"
# TLS_KEY_FILE = "key.pem"

# # Logging setup
# logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# async def authenticate(server_address, username, password):
#     host, port = server_address.split(":") if ":" in server_address else (server_address, "6000")
#     ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH) if USE_TLS else None
#     if USE_TLS:
#         ssl_context.load_verify_locations(cafile=TLS_CERT_FILE)# Load cert.pem as trusted CA
#     reader, writer = await asyncio.open_connection(host, port, ssl=ssl_context)
    
#     # Step 1: Send username/password
#     auth_message = f"AUTH_USERNAME|{username}|{password}\n"
#     writer.write(auth_message.encode())
#     await writer.drain()
#     logging.info(f"Sent AUTH_USERNAME: {auth_message.strip()}")  # CHANGED: Added logging

#     response = await reader.read(1024)
#     response_str = response.decode()
#     logging.info(f"Raw response to AUTH_USERNAME: {response!r}")  # CHANGED: Added raw response log
#     logging.info(f"Decoded response to AUTH_USERNAME: {response_str}")  # CHANGED: Added decoded log

#     if "OTP_SENT" not in response_str:
#         logging.error(f"Authentication failed: {response_str}")
#         writer.close()
#         await writer.wait_closed()
#         return None, None, None
    
#     # Step 2: Get OTP and TOTP
#     email = response_str.split("|")[1]
#     otp = input(f"Enter OTP sent to {email}: ").strip()
#     totp = input("Enter TOTP from authenticator app: ").strip()
    
#     # Step 3: Verify OTP and TOTP
#     # Send VERIFY_OTP (assumed original with changes)
#     verify_message = f"VERIFY_OTP|{username}|{otp}|{totp}\n"
#     writer.write(verify_message.encode())
#     await writer.drain()
#     logging.info(f"Sent VERIFY_OTP: {verify_message.strip()}")  # CHANGED: Log exact message sent

#     response = await reader.read(1024)
#     logging.info(f"Raw response to VERIFY_OTP: {response!r}")  # CHANGED: Log raw bytes
#     response_str = response.decode()
#     logging.info(f"Decoded response to VERIFY_OTP: {response_str}")  # CHANGED: Log decoded response
#     if "TOKEN_ISSUED" not in response_str:
#         logging.error(f"OTP/TOTP verification failed: {response_str}")
#         writer.close()
#         await writer.wait_closed()
#         return None, None, None
    
#     parts = response_str.split("|")
#     token, refresh_token, hmac_key = parts[1], parts[2], parts[3]
#     admin_token = parts[4] if len(parts) > 4 else None
#     logging.info(f"Authentication successful: Token={token}, Admin Token={admin_token or 'N/A'}")

#     writer.close()
#     await writer.wait_closed()
#     return token, refresh_token, admin_token

# async def admin_command(server_address, token, admin_token, command, *args):
#     host, port = server_address.split(":") if ":" in server_address else (server_address, "6000")
#     ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH) if USE_TLS else None
#     reader, writer = await asyncio.open_connection(host, port, ssl=ssl_context)
    
#     request = f"{token}|{command}|dummy_signature|{'|'.join(args)}\n"
#     writer.write(request.encode())
#     await writer.drain()
    
#     response = await reader.read(4096)
#     response_str = response.decode()
#     logging.info(f"Server response: {response_str}")
#     writer.close()
#     await writer.wait_closed()
#     return response_str

# def admin_menu(server_address, token, admin_token):
#     while True:
#         print("\nAdmin Menu:")
#         print("1. Block IP")
#         print("2. Add User")
#         print("3. Delete User")
#         print("4. List Sessions")
#         print("5. Terminate Session")
#         print("6. Reset Model")
#         print("7. Get Logs")
#         print("8. Exit")
        
#         choice = input("Select option: ").strip()
#         if choice == "1":
#             ip = input("IP to block: ").strip()
#             asyncio.run(admin_command(server_address, token, admin_token, "ADMIN_BLOCK_IP", ip))
#         elif choice == "2":
#             username = input("New username: ").strip()
#             email = input("Email: ").strip()
#             password = input("Password: ").strip()
#             phone = input("Phone (optional): ").strip()
#             asyncio.run(admin_command(server_address, token, admin_token, "ADMIN_ADD_USER", username, email, password, phone or ""))
#         elif choice == "3":
#             username = input("Username to delete: ").strip()
#             asyncio.run(admin_command(server_address, token, admin_token, "ADMIN_DELETE_USER", username))
#         elif choice == "4":
#             response = asyncio.run(admin_command(server_address, token, admin_token, "ADMIN_LIST_SESSIONS"))
#             if "SESSIONS" in response:
#                 sessions = json.loads(response.split("|")[1])
#                 print("Active Sessions:", json.dumps(sessions, indent=2))
#         elif choice == "5":
#             target_token = input("Token to terminate: ").strip()
#             asyncio.run(admin_command(server_address, token, admin_token, "ADMIN_TERMINATE_SESSION", target_token))
#         elif choice == "6":
#             asyncio.run(admin_command(server_address, token, admin_token, "ADMIN_RESET_MODEL"))
#         elif choice == "7":
#             log_type = input("Log type (e.g., auth, audit): ").strip()
#             response = asyncio.run(admin_command(server_address, token, admin_token, "ADMIN_GET_LOGS", log_type))
#             if "LOGS" in response:
#                 print("Logs:", response.split("|")[1])
#         elif choice == "8":
#             break
#         else:
#             print("Invalid option")

# def main(server_address):
#     username = input("Admin Username: ").strip()
#     password = input("Admin Password: ").strip()
#     token, refresh_token, admin_token = asyncio.run(authenticate(server_address, username, password))
#     if not admin_token:
#         logging.error("Admin privileges required")
#         return
    
#     admin_menu(server_address, token, admin_token)

# if __name__ == "__main__":
#     server_address = input("Server address (e.g., 192.168.31.237:6000): ").strip() or "192.168.31.237:6000"
#     main(server_address)

#!/usr/bin/env python3
import asyncio
import ssl
import logging
import json
import hmac
import hashlib
import os
# TLS Configuration
USE_TLS = True
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))
TLS_CERT_FILE = os.path.join(PROJECT_ROOT, "cert.pem")
TLS_KEY_FILE = os.path.join(PROJECT_ROOT, "key.pem")

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def sign_request(request_data, hmac_key):
    """Generate an HMAC signature for the request using the provided key."""
    return hmac.new(hmac_key.encode(), request_data.encode(), hashlib.sha256).hexdigest()

async def authenticate(reader, writer, username, password):
    """Authenticate admin using an existing SSL connection."""
    auth_message = f"AUTH_USERNAME|{username}|{password}\n"
    writer.write(auth_message.encode())
    await writer.drain()

    response = await reader.read(1024)
    response_str = response.decode()
    logging.info(f"Server response: {response_str}")

       # ✅ FIX: Ignore unexpected KEEP_ALIVE messages before OTP verification
    while "KEEP_ALIVE" in response_str:
        logging.info("Ignoring KEEP_ALIVE response, waiting for actual authentication tokens...")
        response = await reader.read(1024)
        response_str = response.decode()
        logging.info(f"Updated server response: {response_str}")


    # ✅ FIX: Handle incorrect "OTP_SENT" response after OTP submission
    if "OTP_SENT" in response_str and "|" in response_str:
        parts = response_str.split("|")
        email = parts[1] if len(parts) > 1 else "Unknown Email"
        logging.info(f"OTP was already sent to {email}. Waiting for verification step...")
    elif "WAITING_FOR_OTP" in response_str:
        logging.info("OTP has been requested. Waiting for user input...")
        email = "Unknown Email"
    elif "ERROR" in response_str:
        logging.error(f"Authentication failed: {response_str}")
        return None, None, None, None
    
    logging.info("Waiting for user to enter OTP...")
    otp = input(f"Enter OTP sent to {email}: ").strip()
    totp = input("Enter TOTP from authenticator app: ").strip()

    logging.info("OTP entered. Sending to server...")

    verify_message = f"VERIFY_OTP|{username}|{otp}|{totp}\n"
    writer.write(verify_message.encode())
    await writer.drain()

    response = await reader.read(1024)
    response_str = response.decode()
    logging.info(f"Server response: {response_str}")
    # ✅ FIX: Handle unexpected KEEP_ALIVE after OTP verification
    while "KEEP_ALIVE" in response_str:
        logging.info("Ignoring KEEP_ALIVE response, waiting for authentication tokens...")
        response = await reader.read(1024)
        response_str = response.decode()
        logging.info(f"Updated server response after KEEP_ALIVE: {response_str}")


    if "TOKEN_ISSUED" not in response_str:
        logging.error(f"OTP/TOTP verification failed: {response_str}")
        return None, None, None, None

    parts = response_str.split("|")
    token, refresh_token, hmac_key = parts[1], parts[2], parts[3]
    admin_token = parts[4] if len(parts) > 4 else None

    logging.info(f"Authentication successful: Token={token}, Admin Token={admin_token or 'N/A'}")
    return token, refresh_token,hmac_key, admin_token

async def admin_command(reader, writer, token, admin_token,hmac_key, command, *args):
    """Send an admin command over an existing SSL connection."""
    request_data = "|".join([command] + list(args))
    signature = sign_request(request_data, hmac_key)
    request = f"{token}|{command}|{signature}"
    if args:
        request += "|" + "|".join(args)
    request += "\n"
    writer.write(request.encode())
    await writer.drain()
    logging.info(f"Sent admin command: {request.strip()}")

    response = await reader.read(4096)
    response_str = response.decode()
    while "KEEP_ALIVE" in response_str:
        logging.info("Ignoring KEEP_ALIVE, waiting for command response...")
        response = await reader.read(4096)
        response_str = response.decode()
    
    logging.info(f"Server response: {response_str}")
    
    return response_str

async def admin_menu(reader, writer, server_address, token, admin_token,hmac_key):
    """Admin menu to handle different admin commands."""
    while True:
        print("\nAdmin Menu:")
        print("1. Block IP")
        print("2. Add User")
        print("3. Delete User")
        print("4. List Sessions")
        print("5. Terminate Session")
        print("6. Reset Model")
        print("7. Get Logs")
        print("8. Exit")
        
        choice = input("Select option: ").strip()
        if choice == "1":
            ip = input("IP to block: ").strip()
            await admin_command(reader, writer, token, admin_token,hmac_key, "ADMIN_BLOCK_IP", ip)
        elif choice == "2":
            username = input("New username: ").strip()
            email = input("Email: ").strip()
            password = input("Password: ").strip()
            phone = input("Phone (optional): ").strip()
            await admin_command(reader, writer, token, admin_token, hmac_key, "ADMIN_ADD_USER", username, email, password, phone or "")
        elif choice == "3":
            username = input("Username to delete: ").strip()
            await admin_command(reader, writer, token, admin_token, hmac_key, "ADMIN_DELETE_USER", username)
        elif choice == "4":
            response = await admin_command(reader, writer, token, admin_token, hmac_key, "ADMIN_LIST_SESSIONS")
            if "SESSIONS" in response:
                sessions = json.loads(response.split("|")[1])
                print("Active Sessions:", json.dumps(sessions, indent=2))
        elif choice == "5":
            target_token = input("Token to terminate: ").strip()
            await admin_command(reader, writer, token, admin_token,hmac_key, "ADMIN_TERMINATE_SESSION", target_token)
        elif choice == "6":
            await admin_command(reader, writer, token, admin_token, hmac_key, "ADMIN_RESET_MODEL")
        elif choice == "7":
            log_type = input("Log type (e.g., auth, audit): ").strip()
            response = await admin_command(reader, writer, token, admin_token, hmac_key, "ADMIN_GET_LOGS", log_type)
            if "LOGS" in response:
                print("Logs:", response.split("|")[1])
        elif choice == "8":
            exit_signature = sign_request("EXIT", hmac_key)
            writer.write(f"{token}|EXIT|{exit_signature}\n".encode())
            await writer.drain()
            logging.info("Sent EXIT command to server")
            break
        else:
            print("Invalid option")

async def main(server_address):
    """Main function to handle admin authentication and menu."""
    username = input("Admin Username: ").strip()
    password = input("Admin Password: ").strip()

    host, port = server_address.split(":") if ":" in server_address else (server_address, "6000")
    ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH) if USE_TLS else None
    if USE_TLS:
        ssl_context.load_verify_locations(cafile=TLS_CERT_FILE)# Load cert.pem as trusted CA

    # # Open a single persistent SSL connection
    # reader, writer = await asyncio.open_connection(host, port, ssl=ssl_context)

    # # Authenticate the admin
    # token, refresh_token, admin_token = await authenticate(reader, writer, username, password)
    # if not admin_token:
    #     logging.error("Admin privileges required")
    #     writer.close()
    #     await writer.wait_closed()
    #     return
    
    # # Pass the persistent connection to the menu
    # await admin_menu(reader, writer, server_address, token, admin_token)

    # Open a single persistent SSL connection
    # CHANGED: Wrap connection and authentication in try-except to handle ConnectionAbortedError
    reader, writer = await asyncio.open_connection(host, port, ssl=ssl_context)
    
    try:
        
        token, refresh_token, hmac_key, admin_token = await authenticate(reader, writer, username, password)
        if not admin_token:
            logging.error("Admin privileges required")
            return
        
        await admin_menu(reader, writer, server_address, token, admin_token,hmac_key)
    except ConnectionAbortedError as e:
        logging.error(f"Connection aborted by server: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    # CHANGED: Ensure connection is closed gracefully even after an error
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception as e:
            logging.warning(f"Error closing connection: {e}")

if __name__ == "__main__":
    server_address = input("Server address (e.g., 127.0.0.1:6000): ").strip() or "127.0.0.1:6000"
    asyncio.run(main(server_address))

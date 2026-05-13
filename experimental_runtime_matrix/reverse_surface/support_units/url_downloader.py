import requests  # Importing the requests library for making HTTP requests
from requests.adapters import HTTPAdapter  # Importing a specific adapter for requests
from urllib3.util.retry import Retry  # Importing retry functionality from urllib3
import os  # Importing the os module for interacting with the operating system
from tqdm import tqdm  # Importing tqdm for progress bars
import threading  # Importing threading for multi-threading support
import time
import sys
from urllib.parse import urlparse





















# Function to download a chunk of the file
def download_chunk(url, start_byte, end_byte, filename, progress, session, max_retries=10):
    headers = {'Range': f'bytes={start_byte}-{end_byte}'}  # Specifying byte range for HTTP request
    retries = 0  # Initialize retries counter
    while retries < max_retries:  # Retry loop
        try:
            response = session.get(url, headers=headers, stream=True, timeout=20)  # Sending HTTP GET request with byte range
            response.raise_for_status()  # Raise an HTTPError for bad status codes (e.g., 404, 500)
            with open(filename, 'r+b') as file:  # Opening file in read-write binary mode
                file.seek(start_byte)  # Moving file pointer to start of the chunk
                for chunk in response.iter_content(chunk_size=1024):  # Iterating over response content in chunks
                    if chunk:  # Checking if chunk is not empty
                        file.write(chunk)  # Writing chunk to file
                        progress.update(len(chunk))  # Updating progress bar with chunk length
            break  # Exit retry loop if download successful
        except requests.exceptions.RequestException as e:  # Handling RequestException
            # print(f"Error downloading chunk: {e}. Retrying...")
            retries += 1  # Increment retries counter
            time.sleep(1)  # Pause before retrying
    # else:
    #     print(f"Max retries exceeded for downloading chunk. Skipping chunk.")

# Function to download the file using multiple threads
def download_file(url, filename, progress,num_threads=8 ,output_directory='output'):
    session = requests.Session()  # Creating a session object for HTTP requests
    retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])  # Configuring retry strategy
    session.mount('http://', HTTPAdapter(max_retries=retries))  # Mounting HTTP adapter with retry settings
    session.mount('https://', HTTPAdapter(max_retries=retries))  # Mounting HTTPS adapter with retry settings

    total_size = None  # Initialize the variable `total_size` to `None` initially.
    while total_size is None:  # Start a while loop that continues until `total_size` is not `None`.
        
            try:
                response = session.head(url,timeout=20)  # Send an HTTP HEAD request to the specified URL to get file metadata.
                response.raise_for_status()  # Raise an HTTPError for bad status codes (e.g., 404, 500).
                total_size = int(response.headers.get('content-length', 0))  # Extract the total file size from the response headers.
            except requests.exceptions.RequestException as e:  # If any requests exception occurs (e.g., connection error), handle it.
                for _ in tqdm(range(10), desc="Retrying... ⏳", position=0, leave=True):  # Start a loop to display a moving spinner for 10 iterations.
                    time.sleep(0.01)  # Pause for a short duration (0.1 seconds) to control the speed of the spinner.
                    sys.stdout.write('\b' * len("⏳"))  # Move the cursor back by the length of the spinner symbol to clear the previous spinner.
                    sys.stdout.flush()  # Flush the output buffer to ensure the spinner is displayed immediately.
                    sys.stdout.write("⏳")  # Write the spinner symbol to the terminal.
                    sys.stdout.flush()  # Flush the output buffer again to ensure the spinner is displayed immediately.

    chunk_size = total_size // num_threads  # Calculating chunk size for each thread

    # print(f"Downloading {filename}")
    # progress = tqdm(total=total_size, unit='B', unit_scale=True,desc="     ", dynamic_ncols=True,leave=True, position=0)  # Initializing progress bar
    progress.reset(total =total_size)


    threads = []  # List to store thread objects
    
    # Create the output directory if it doesn't exist10
    os.makedirs(output_directory, exist_ok=True)  # Creating output directory if it doesn't exist
    
    filepath = os.path.join(output_directory, filename)  # Constructing full file path
    
    with open(filepath, 'wb') as file:  # Opening file in write binary mode
        for i in range(num_threads):  # Looping over number of threads
            start_byte = chunk_size * i  # Calculating start byte for chunk
            end_byte = start_byte + chunk_size - 1 if i < num_threads - 1 else total_size - 1  # Calculating end byte for chunk
            thread = threading.Thread(target=download_chunk, args=(url, start_byte, end_byte, filepath, progress, session))  # Creating thread for downloading chunk
            thread.start()  # Starting thread
            threads.append(thread)  # Appending thread to list of threads
        for thread in threads:  # Looping over threads
            thread.join()  # Waiting for threads to complete
    progress.close()  # Closing progress bar




def is_valid_url(url):
    try:
        result = urlparse(url)
        # Check if the scheme and netloc are present
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def main():
    while True:
        try:    
            try:
                while True:
                    final_url = str(input("Enter URL: "))
                    if not is_valid_url(final_url):
                        print("Invalid URL\nTry Again")
                        continue
                    break


                filename = str(input("Enter file Name(Like: Name.apk): "))
                output_directory = str(input("Enter output directory: "))

            except Exception as e:
                print("Error: ", e)
                continue


            progress = tqdm(total=0, unit='B', unit_scale=True,desc=f"{filename}", dynamic_ncols=True,leave=True, position=0)
            download_file(final_url, filename,progress, num_threads=64, output_directory=output_directory)

            break
        except Exception as e:
            print("Error: ", e)

if __name__ == "__main__":
    main()
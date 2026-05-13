import csv
import pandas as pd
import requests  # Importing the requests library for making HTTP requests
from requests.adapters import HTTPAdapter  # Importing a specific adapter for requests
from urllib3.util.retry import Retry  # Importing retry functionality from urllib3
import os  # Importing the os module for interacting with the operating system
from tqdm import tqdm  # Importing tqdm for progress bars
import threading  # Importing threading for multi-threading support
import time
import sys
from urllib.parse import urlparse
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed,wait,ALL_COMPLETED
from datetime import datetime
import warnings
import decompile_of_data_collection as ddc

file_lock = threading.Lock()


warnings.filterwarnings('ignore')


def create_dir_if_not(output_directory):
    # Create the output directory if it doesn't exist
    os.makedirs(output_directory, exist_ok=True)


# append sha256
def append_sha256_to_file(text):
    year_for_file1 = str(year_for_file)
    name_of_txt =  year_for_file1 + '.txt'

    create_dir_if_not('sha256_with_con_of_dowload')

    file_path = os.path.join('sha256_with_con_of_dowload',name_of_txt)

    a = os.path.exists(file_path)

    with file_lock:         # Ensure thread-safe file operations
        if a == False:
            with open(file_path, 'w') as file:
                file.write('assume that sha256 count 1 = 0, 2=1 in csv \n\n')
        # Open the file in append mode ('a')
        with open(file_path, 'a') as file:
            # Write the text to the file
            file.write(text + '\n')

# Read the CSV file into a pandas DataFrame
def read_csv():
    df = pd.read_csv('latest.csv', usecols=[0, 4, 7, 8], header=None, skiprows=1)  # Reading CSV file into DataFrame skiprows=1
    # print("Original DataFrame:")
    # print(df)
    a = len(df[0])
    print(a)

    
    

    def filter_csv():

        try:
            vt_detection_value = int(input("Enter vt_detection value:"))
            dfBenign = df[df[7] == vt_detection_value]  # Assuming 'vt_detection' column index is 3
            # print("Filtered on vt_detection = 0:")
            # print(dfBenign)

            dfBenignSmall = dfBenign[(dfBenign[4].astype(float) < 26214400) & (dfBenign[4].astype(float) > 3145728)]   # Assuming 'apk_size' column index is 2
            # print("Filtered on apk_size:")
            # print(dfBenignSmall)

            vt_scan_date_start = str(input("Enter vt_scan_date starting Date [yyyy-mm-dd]:"))
            vt_scan_date_end = str(input("Enter vt_scan_date Ending Date [yyyy-mm-dd]:"))
            print(vt_scan_date_start,vt_scan_date_end)

            global year_for_file
            year_for_file = vt_scan_date_start[:4]
            text2 = f"vt_scan_date_start , vt_scan_date_end = {vt_scan_date_start } , {vt_scan_date_end }"
            append_sha256_to_file(text2)

            dfBenignSmallNew = dfBenignSmall[(pd.to_datetime(dfBenignSmall[8]) > vt_scan_date_start) & 
                                            (pd.to_datetime(dfBenignSmall[8]) < vt_scan_date_end)]  # Assuming 'vt_scan_date' column index is 3
            size_of_apk = dfBenignSmallNew[[4]].copy()
            size_of_apk = size_of_apk.values.flatten()
            data = dfBenignSmallNew[[0]].copy()  # Assuming 'sha256' column index is 0
            all_values = data.values.flatten()  # Flattening DataFrame values into a 1D array

            print(len(all_values), ' sha256 Found with given condition')

            return all_values, vt_scan_date_start ,size_of_apk

        except KeyboardInterrupt as e:
            print("Keyboard Interrupted")
            return filter_csv()

        except ValueError as e:
            print("Invalid input: ",e)
            return filter_csv()

        except Exception as e:
            print("Error accurs while filtering sha256: ",e)
            return filter_csv()

    # dfBenignSmallNew = filter_csv()



    # data = dfBenignSmallNew[[0]].copy()  # Assuming 'sha256' column index is 0
    # all_values = data.values.flatten()  # Flattening DataFrame values into a 1D array

    # print(len(all_values), ' sha256 Found with given condition')

    return filter_csv()



# Function to read API key from file
def read_api_key(filename="api_key.txt"):
    with open(filename, 'r') as file:  # Opening file in read mode
        return file.read().strip()  # Reading API key from file and stripping any whitespace

# Function to download a chunk of the file
def download_chunk(url, start_byte, end_byte, filename, progress, session, max_retries=10):
    headers = {'Range': f'bytes={start_byte}-{end_byte}'}  # Specifying byte range for HTTP request
    retries = 0  # Initialize retries counter
    while retries < max_retries:  # Retry loop
        try:
            response = session.get(url, headers=headers, stream=True, timeout = 60)  # Sending HTTP GET request with byte range
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
    retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[429,500, 502, 503, 504])  # Configuring retry strategy
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




def download(i,final_url, filename, output_directory):
    # print(f"Downloading {filename}")
    progress = tqdm(total=0, unit='B', unit_scale=True,desc=f"Downloading {i+1}", dynamic_ncols=True,leave=True, position=0)
    download_file(final_url, filename,progress, num_threads=64, output_directory=output_directory)


def convert_bytes(size_in_bytes):
    # 1 Kilobyte = 1024 Bytes
    kilobyte = 1024
    megabyte = kilobyte * 1024
    gigabyte = megabyte * 1024
    terabyte = gigabyte * 1024

    size_in_megabytes = size_in_bytes / megabyte
    size_in_gigabytes = size_in_bytes / gigabyte
    size_in_terabytes = size_in_bytes / terabyte
    
    if size_in_bytes < megabyte:
        return (f"{size_in_bytes} bytes")
    elif size_in_bytes < gigabyte:
        # print(f"{size_in_bytes} bytes")
        return (f"{size_in_megabytes:.2f} MB")
    elif size_in_bytes < terabyte:
        # print(f"{size_in_bytes} bytes")
        # print(f"{size_in_megabytes:.2f} MB")
        return (f"{size_in_gigabytes:.2f} GB")
    else:
        # print(f"{size_in_bytes} bytes")
        # print(f"{size_in_megabytes:.2f} MB")
        # print(f"{size_in_gigabytes:.2f} GB")
        return (f"{size_in_terabytes:.2f} TB")

    
def main():
    url = "https://androzoo.uni.lu/api/download"  # Setting download URL
    api_key = read_api_key()  # Reading API key from file

    sha256_all, vt_scan_date_start, size_of_apk = read_csv()

    global year_for_file
    year_for_file = vt_scan_date_start[:4]

    # output_apk_file_name = 'APK'
    output_directory_path = str(input("Enter output Directory Path: "))
    output_directory = os.path.join(output_directory_path,year_for_file)

    while True:
        try:
            while True:
                try:
                    start_range = int(input("Enter download Starting range: "))  # Reading starting range from user input
                    end_range = int(input("Enter download End range: "))  # Reading ending range from user input
                    if (start_range >= end_range):
                        print("Must Ending range > Starting range")
                        continue
                    else:
                        # print('111')
                        # print("Size of apk:",size_of_apk)
                        # a = size_of_apk[start_range]
                        # print(a)
                        # print("before")
                        sum_of_apk_size = 0
                        for i in range(start_range,end_range):

                            sum_of_apk_size += size_of_apk[i]



                        # print(f"Sum of APK sizes from {start_range} to {end_range}: {convert_bytes(sum_of_apk_size)}")


                        # print(size_of_apk[start_range])


                        print(f"Size of all APK {start_range} - {end_range} = {convert_bytes(sum_of_apk_size)} ")
                        print("1. Downlod Continue \n2. Re-enter Range \n")
                        try:
                            choice = int(input("Enter your choice: "))
                            if choice == 1:
                                break
                            elif choice == 2:
                                continue
                        except ValueError as e:
                            print("Invalid choice")
                            continue
                        except Exception as e:
                            print(f"Error: {e}")
                            continue
                except ValueError as e:
                    print("Enter valid values")
                    continue
                except Exception as e:
                    print(f"Error in Input range: {e}")

            text = f"\nStarting Range = {start_range} and Ending Range = {end_range}"
            append_sha256_to_file(text)

            start_time = datetime.now()
                # Define the text you want on the left side
            left_text = "Process started at:"
            # Define the width of the line (total characters per line)
            line_width = 100
            # Format the line with left text and start_time on the right
            formatted_line = f"\n{left_text:<{line_width - len(str(start_time))}}{start_time}"
            append_sha256_to_file(formatted_line)

            batch_size = 10  # Size of each batch            
            for batch_start in range(start_range, end_range, batch_size):
                batch_end = min(batch_start + batch_size, end_range)


                feature_download=[]

                try:


                    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                        for i in range(batch_start, batch_end):
                        
                            sha256 = sha256_all[i]  # Accessing SHA256 hash from the list
                            final_url = f"{url}?apikey={api_key}&sha256={sha256}"  # Constructing final download URL
                            name = sha256
                            filename = f"{name}.apk"  # Constructing filename
                            feature = executor.submit(download,i,final_url, filename, output_directory=output_directory)  # Calling function to download file

                            feature_download.append(feature)
                            text = f'{i+1} {sha256}'
                            append_sha256_to_file(text) #appending sha256 with count assume that sha256 count 1 = 0, 2=1 in csv

                            # print(f"Downloded {batch_start} to {batch_end}")
                        # Use wait() to wait for all tasks to complete
                        # wait(feature, return_when=ALL_COMPLETED)
                        for future in as_completed(feature_download):
                            try:
                                future.result()
                            except Exception as e:
                                print(f"An error occurred in downloding: {e}")

                except Exception as e:
                    print(f"Error in downloading: {e}")
                    # end_time = datetime.now()
                    #     # Define the text you want on the left side
                    # left_text = "Process End with error at:"
                    # # Define the width of the line (total characters per line)
                    # line_width = 100
                    # # Format the line with left text and start_time on the right
                    # formatted_line = f"\n{left_text:<{line_width - len(str(end_time))}}{end_time}"
                    # append_sha256_to_file(formatted_line)
                    # text = f"Error :{e}"
                    # append_sha256_to_file(text)

                
                try:
                    ddc.main(folder_name=output_directory,year=year_for_file)

                except Exception as e:
                    print(f"Error in Decompile of data collection(ddc): {e}")



            end_time = datetime.now()
                # Define the text you want on the left side
            left_text = "Process End at:"
            # Define the width of the line (total characters per line)
            line_width = 100
            # Format the line with left text and start_time on the right
            formatted_line = f"\n{left_text:<{line_width - len(str(end_time))}}{end_time}"
            append_sha256_to_file(formatted_line)

            text = '\n\n'
            append_sha256_to_file(text)

        except KeyboardInterrupt as e:
            print('Error: Keybord Intrupted',e)
            end_time = datetime.now()
                # Define the text you want on the left side
            left_text = "Process End at:"
            # Define the width of the line (total characters per line)
            line_width = 100
            # Format the line with left text and start_time on the right
            formatted_line = f"\n{left_text:<{line_width - len(str(end_time))}}{end_time}"
            append_sha256_to_file(formatted_line)

            text = '\n\n'
            append_sha256_to_file(text)

if __name__ == "__main__":
    main()
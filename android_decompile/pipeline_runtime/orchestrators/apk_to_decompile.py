import contextlib
import os
import psutil
import tqdm
import zipfile
import subprocess
import re
from time import time
import cut_and_past_for_decompilation as cp
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed,wait,ALL_COMPLETED
import warnings
from datetime import datetime
import time
from tqdm import tqdm
import shutil
import function_call_graph
import java_keyword_find6
import permission3
from art import text2art  # Importing text2art function from art module for ASCII art generation
from colorama import init, Fore, Style  # Importing colorama for colored text output
import win32api # type: ignore
import win32process # type: ignore
import win32con # type: ignore
import signal
from logging_config import get_logger
logger = get_logger(__name__)
logger.info("module_loaded")



def set_high_priority():
    """Set the current process to high priority."""
       # Get current process
    p = psutil.Process(os.getpid())
    
    # Set priority to high
    p.nice(psutil.HIGH_PRIORITY_CLASS)
    
    # Alternatively, use win32api to set priority
    handle = win32api.GetCurrentProcess()
    win32process.SetPriorityClass(handle, win32process.REALTIME_PRIORITY_CLASS)









def create_dir_if_not(output_directory):
    # Create the output directory if it doesn't exist
    os.makedirs(output_directory, exist_ok=True)
 


# Defining a function called `get_file_path` that takes a `file_name` argument.
def get_file_path(file_name):
    try:
        file_path = os.path.abspath(file_name)  # Getting the absolute path of the file.
        return file_path  # Returning the absolute path.
    except FileNotFoundError:
        return f"File '{file_name}' not found."  # Returning a message if the file is not found.

# Defining a function called `add_to_path` that takes a `directory` argument.
def add_to_path(directory):
    path = os.environ.get('PATH', '')  # Getting the current system path.
    path_list = path.split(os.pathsep)  # Splitting the path into a list based on the separator.

    # Checking if the directory is not already in the system path.
    if directory not in path_list:
        path_list.insert(0, directory)  # Adding the directory to the beginning of the path list.
        new_path = os.pathsep.join(path_list)  # Joining the path list elements with the separator.
        os.environ['PATH'] = new_path  # Updating the system path.
        print(f"Directory '{directory}' added to the system path.")  # Printing a success message.
    else:
        print(f"Directory '{directory}' is already in the system path.")  # Printing a message if the directory is already in the system path.



#apk to zip extract and get path of classes*.dex and AndroidManifest.xml

def extreact_and_find_classdex_mnf(name):

    
    def find_class_files(directory):
        class_files_dex = []
        mnf_file_path = None  # Initialize mnf_file_path

        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.startswith("classes") and file.endswith(".dex"):
                    full_path = os.path.join(root, file)
                    class_files_dex.append(full_path)

                if file == 'AndroidManifest.xml':
                    full_path = os.path.join(root, file)
                    mnf_file_path = full_path

        return class_files_dex, mnf_file_path

    # Original path of the APK file
    apk_filename = f'{name}.apk'
    old_path = os.path.join('APK', year_for_file, apk_filename)

    # Target year and filename for the ZIP file
    # year_for_file = '2024'
    zipfilename = f"{name}.zip"

    # New path for the ZIP file
    new_path = os.path.join("apk_zip", year_for_file)
    create_dir_if_not(new_path)
    new_path_with_file = os.path.join(new_path, zipfilename)

    try:
        # Rename the APK file to a ZIP file
        os.rename(old_path, new_path_with_file)
        print(f'Renamed {apk_filename} to {zipfilename}')
    except Exception as e:
        print(f"Error occurs while renaming file: {e}")

    # Path to extract the contents of the ZIP file
    extract_path = os.path.join("apk_zip_extracted", year_for_file, name)
    create_dir_if_not(extract_path)

    try:
        # Open the ZIP file for reading
        with zipfile.ZipFile(new_path_with_file, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
            print(f'Extracted {zipfilename} to {extract_path}')
    except zipfile.BadZipFile:
        print(f"Error: The file {new_path_with_file} is not a zip file or it is corrupted.")
    except FileNotFoundError:
        print(f"Error: The file {new_path_with_file} does not exist.")
    except Exception as e:
        print(f"Error occurs while extracting zip file: {e}")

    # Search for .dex files and AndroidManifest.xml
    try:
        class_files_found, mnf_path = find_class_files(extract_path)
        return class_files_found, mnf_path
    except Exception as e:
        print("Error occurs while searching for .dex files:", e)





#decompile apk to java
def decompile_apk(name,progress_bar,apk_path):
    # Full path to the JADX binary
    jadx_bin_path = r'jadx-1.5.0\bin\jadx.bat'
    
    # Output directory for the decompiled Java files
    java_path = os.path.join('JAVA', year_for_file)
    path_parts = apk_path.split("\\")

    # Get the last part
    last_part = path_parts[-1]
    last_part = last_part.split('.')
    last_part = last_part[0]
    print(last_part)

    output_dir = os.path.join(java_path, str(name),last_part)
    
    # Path to the APK file to be decompiled
    # apk_dir = os.path.join('APK', year_for_file)
    # apk_path = os.path.join(apk_dir, f'{name}.apk')

    total_steps = None
    # progress_bar = None

    try:
        # Execute the command using subprocess.Popen to capture real-time output
        process = subprocess.Popen(
            [jadx_bin_path, '-d', output_dir, apk_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )


        

        # Process output line by line
        # print("Loading...")
        for line in process.stdout:
            # print(line.strip())  # Uncomment this line if you want to see the actual output in the console

            # Match the line that indicates the total number of steps
            total_steps_match = re.match(r'INFO\s+-\s+progress:\s+0\s+of\s+(\d+)\s+\(0%\)', line)
            if total_steps_match and total_steps is None:
                total_steps = int(total_steps_match.group(1))

                # print(f"Decompiling APK {name}")
                # progress_bar = tqdm(total=total_steps, unit="step", desc="     ")
                progress_bar.reset(total =total_steps)
                

            # Match lines indicating progress
            progress_match = re.match(r'INFO\s+-\s+progress:\s+(\d+)\s+of\s+(\d+)\s+\(\d+%\)', line)
            if progress_match and progress_bar:
                current_progress = int(progress_match.group(1))
                progress_bar.n = current_progress  # Update progress bar to the current progress
                progress_bar.refresh()

        process.wait()  # Wait for the process to complete

        if progress_bar:
            progress_bar.close()

        if process.returncode == 0:
            # print("Decompiled successfully (.apk - .java): ",name)
            zzzzzzz = None
        else:
            print(f"Error decompiling APK: Process returned non-zero exit code {process.returncode}")

    except subprocess.CalledProcessError as e:
        if progress_bar:
            progress_bar.close()
        print(f"Error decompiling APK: {e.stderr}")
    except Exception as e:
        if progress_bar:
            progress_bar.close()
        print(f"Exception occurred while decompiling APK: {e}")





# Defining a function called `mnf` that takes an argument `z`.
def mnf(z,path_of_axmlprinter2,apk_path):
    name = str(z)  # Converting the argument `z` to a string and assigning it to the variable `name`.
    apk_name = f"{name}.apk"  # Creating a string with the `.apk` extension and assigning it to `apk_name`.

    # apk_path = os.path.join('APK', year_for_file, apk_name)  # Generating the path to the APK file using `os.path.join()` and assigning it to `apk_path`.
    mnf_name = name  # Assigning the value of `name` to `mnf_name`.

    # File paths for stdout and stderr
    # stdout_file_path = os.path.join(output_dir, f"{mnf_name}_output.txt")
    # stderr_file_path = os.path.join(output_dir, f"{mnf_name}_error.txt")

    year = str(year_for_file)
    # print("Loading...")
    
    output_dir = f"MNF/{year}"  # Generate the output directory path

    # Ensure the directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, f"{name}.xml")  # Full path to the output XML file


    # output_dir = f"MNF/{year}/{mnf_name}.xml"
    # # create_dir_if_not(output_dir)
    # # output_dir = os.path.join(output_d, mnf_name, '.xml')

    a = time.time()
    # Trying to open files for stdout and stderr and writing the output to these files.
    try:
        # with open(f"./MNF/{mnf_name}_output.txt", "w") as stdout_file, \
        #      open(f"./MNF/{mnf_name}_error.txt", "w") as stderr_file:
        #     # Running a subprocess with the given command and arguments.
        #     result = subprocess.run(
        #         ["java","-jar",path_of_axmlprinter2, apk_path, ">", f"MNF/{year}/{mnf_name}.xml"],
        #         stdout=subprocess.PIPE,  # Redirecting the standard output to a pipe.
        #         stderr=subprocess.PIPE,  # Redirecting the standard error to a pipe.
        #         stdin=subprocess.PIPE,   # Redirecting the standard input to a pipe.
        #         text=True                # Decoding the input and output as text.
        #     )

        #     # output_lines = result.stdout.splitlines()
        #     # total_lines = len(output_lines)

        #     # # Create progress bar with total lines
        #     # with tqdm(total=total_lines, desc=f"Decompiling MNF {name}") as pbar:
        #     #     for line in output_lines:
        #     #         if line.strip() == "Press any key to continue . . .":
        #     #             break
        #     #         # Write line to stdout file
        #     #         stdout_file.write(line + '\n')
        #     #         pbar.update(1)

        #     # # Write stderr to stderr file
        #     # stderr_file.write(result.stderr)
        # # Checking if the return code of the subprocess is 0 (indicating success).
        # if result.returncode == 0:
        #     print("\n Decompilation MNF successful! : ", mnf_name )  # Printing a success message.
        #     b = time.time()
        #     print(f"Time taken: {b - a} seconds")
        # else:
        #     print(f"Error occurred while decompiling MNF of  {apk_name}. See error log.")
        #     # Printing the output in case of an error.
        #     for line in result.stdout:
        #          print(line, end='')
        os.system(f"java -jar {path_of_axmlprinter2} {apk_path} > {output_file}")

        print("\nDecompilation MNF successful! : ", mnf_name)  # Printing a success message.

        b = time.time()
        print(f"Time taken: {b - a} seconds")
    # Handling exceptions.
    except Exception as e:
        print(f"Error occurs while creating MNF file: {e}")  # Printing an error message.
 

def create_dir_if_not(output_directory):
    # Create the output directory if it doesn't exist
    os.makedirs(output_directory, exist_ok=True)



def append_sha256_to_file_for_decompile(text):
    year_for_file1 = str(year_for_file)
    name_of_txt =  year_for_file1 + '.txt'

    create_dir_if_not("sha256_with_con_of_decompile")

    file_path = os.path.join('sha256_with_con_of_decompile',name_of_txt)

    a = os.path.exists(file_path)
    if a == False:
        with open(file_path, 'w') as file:
            file.write('assume that sha256 count 1 = 0, 2=1 in csv \n\n')
    # Open the file in append mode ('a')
    with open(file_path, 'a') as file:
        # Write the text to the file
        file.write(text + '\n')




def decompile_call(name,i,path_of_axmlprinter2):
    set_high_priority()
    
    classes_dex , androidmanifes_xml = extreact_and_find_classdex_mnf(name)

    print(f"Decompiling APK {name}")
    
    for dex_path in classes_dex:
        progress_bar = tqdm(total=0, unit="step", desc=f"Decompiling {i+1}",dynamic_ncols=True,leave=True, position=0)
        decompile_apk(name,progress_bar,dex_path)

    print("Decompiled successfully (.apk - .java): ",name)

    mnf(str(name),path_of_axmlprinter2,apk_path=androidmanifes_xml)

    # text = f'{i+1} {sha256}'
    # append_sha256_to_file_for_decompile(text) #appending sha256 with count assume that sha256 count 1 = 0, 2=1 in csv


    # text = f'{i+1} {sha256}'
    # append_sha256_to_file(text) #appending sha256 with count assume that sha256 count 1 = 0, 2=1 in csv


def convert_time(seconds):
    if seconds >= 60:
        minutes = seconds // 60
        seconds = seconds % 60
        if minutes >= 60:
            hours = minutes // 60
            minutes = minutes % 60
            return f"{hours} hours, {minutes} minutes, and {seconds} seconds"
        else:
            return f"{minutes} minutes and {seconds} seconds"
    else:
        return f"{seconds} seconds"



def count_files_in_directory(folder_name):
    file_count = 0
    for root, dirs, files in os.walk(folder_name):
        for file in files:
            if file.endswith(".apk"):
                file_count += 1  # Count the number of files in each directory
                
    return file_count



# check that csv file is open or not
def check_csv_open():
    def clear_lines(num_lines):
                """ Clear the specified number of lines in the terminal """
                for _ in range(num_lines):
                    print("\033[F\033[K", end="")

    def countdown_timer(seconds):
        init(autoreset=True)
        colors = Fore.RED
        for remaining in range(seconds, 0, -1):
            print(colors+f"{remaining} seconds remaining", end='\r')
            time.sleep(1)
        print("Time's up! " )



    def is_file_open(file_path):
        # Get a list of all processes
        processes = psutil.process_iter(['pid', 'name'])

        for proc in processes:
            try:
                # Iterate over open files of the process
                open_files = proc.open_files()
                for item in open_files:
                    if item.path == file_path:
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except psutil.ZombieProcess:
                continue
            
        return False



    def clear_terminal():
        # For Windows
        if os.name == 'nt':
            os.system('cls')
        # For Unix-based systems (Linux, macOS)
        else:
            os.system('clear')

    def check_csv_is_open_or_not(csv_file_path,csv_file_name):
        a = True
        while a == True:
            if is_file_open(csv_file_path):
                init(autoreset=True)
                colors = Fore.RED
            # print(colors + Style.BRIGHT + design_text)
                warning_message = text2art('WARNING!!')
                print(colors+Style.BRIGHT+warning_message+f"\nCSV File {csv_file_name} is open. CLOSE it")
                countdown_timer(30)
                clear_terminal()
            else:
            # clear_lines(warning_message.count('\n') + 1)
                clear_terminal()
                # print('File is closed')
                a = False
    

    filename = 'csv'
    csv_file_path_a = get_file_path(filename)

    csv_file_name = ['function_call_graph.csv','permission.csv','java_keyword.csv']

    for i in csv_file_name:

        csv_file_path = os.path.join(csv_file_path_a,i)
        print(csv_file_path)
        
        check_csv_is_open_or_not(csv_file_path,i)



def copy_apk_file(file_name_for_copy):
    absolute_source_path = get_file_path("APK")
    absolute_destination_path = get_file_path("APK_fcg")

    source_path = os.path.join(absolute_source_path,year_for_file,file_name_for_copy)
    # source_path = source_path.replace("\\","\\\\")
    destination_path = os.path.join(absolute_destination_path,year_for_file,file_name_for_copy)
    # destination_path = destination_path.replace("\\","\\\\")
    try:

        print(f"Source Path: {source_path}")
        print(f"Destination Path: {destination_path}")
        
        # Check if the source file exists
        if not os.path.exists(source_path):
            print("Error: Source file does not exist.")
            return
        
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)

        shutil.copy(source_path, destination_path)
        print(f"File '{source_path}' has been copied to '{destination_path}'.")
    except FileNotFoundError:
        print(f"Source file '{source_path}' not found.")
    except PermissionError:
        print(f"Permission denied: Unable to copy '{source_path}'.")
    except Exception as e:
        print(f"Error: {e}")



def append_sha256_to_file_for_of_csv_of_mnf_java_fcg(text):
    year_for_file1 = str(year_for_file)
    name_of_txt =  year_for_file1 + '.txt'

    create_dir_if_not("sha256_with_con_of_csv")

    file_path = os.path.join('sha256_with_con_of_csv',name_of_txt)

    a = os.path.exists(file_path)
    if a == False:
        with open(file_path, 'w') as file:
            file.write('assume that sha256 count 1 = 0, 2=1 in csv \n\n')
    # Open the file in append mode ('a')
    with open(file_path, 'a') as file:
        # Write the text to the file
        file.write(text + '\n')






# Call the function using ProcessPoolExecutor for better isolation
def run_callfunction(sha256, year_for_file):
    try:
        print("Entering run_callfunction")  # Debugging start of function
        with open(os.devnull, 'w') as f, contextlib.redirect_stdout(f):
            result = java_keyword_find6.main(sha256=sha256, year_for_file=year_for_file)  # Call the function directly
            result = 1
        print("Exiting run_callfunction")  # Debugging end of function
        return result
    except Exception as e:
        print(f"Error in run_callfunction: {e}")
        return None





# Use ProcessPoolExecutor to isolate the function execution in a separate process.
def run_with_timeout(sha256, year_for_file, timeout_duration=900):
    print("Starting run_with_timeout")  # Debugging start of timeout function
    with concurrent.futures.ProcessPoolExecutor() as executor:  # Use ProcessPoolExecutor instead of ThreadPoolExecutor
        future = executor.submit(run_callfunction, sha256, year_for_file)
        try:
            # Set a timeout for the future and catch any timeouts or process failures
            result = future.result(timeout=timeout_duration)
            print("run_callfunction completed successfully")  # Function finished in time
            return result
        except concurrent.futures.TimeoutError:
            print(f"Execution timed out after {timeout_duration} seconds.")
            return None  # Handle timeout
        except Exception as e:
            print(f"Unexpected error during execution: {e}")
            return None
        finally:
            # Check if the process is alive or was killed
            if future.cancelled():
                print("Future was cancelled.")
            if future.running():
                # The process is running too long, and we may need to kill it
                print("Process is still running, possibly stuck.")
                executor.shutdown(wait=False)
            if future.done():
                if future.exception() is not None:
                    print(f"Process was killed or failed with exception: {future.exception()}")
                else:
                    print("Process finished successfully.")




# This function will handle process termination signals, ensuring the script doesn't get stuck.
def timeout_handler(signum, frame):
    raise TimeoutError("Function execution exceeded time limit or was killed by CPU/OS.")




def csv_of_mnf_java_fcg(sha256, progress_barr_mnf_java_fcg_csv,i):
    set_high_priority()

    start_time_csv = datetime.now()
            # Define the text you want on the left side
    left_text = "Process Started at:"
    # Define the width of the line (total characters per line)
    line_width = 100
    # Format the line with left text and start_time on the right
    formatted_line = f"\n{left_text:<{line_width - len(str(start_time_csv))}}{start_time_csv}"
    append_sha256_to_file_for_of_csv_of_mnf_java_fcg(formatted_line)                                          




    callfunction0 = 'function_call_graph.main'
    # print("Enter in  FCG")


    try:
                        # print("Before function call")  # Debug statement
                        # Call the function
        with open(os.devnull, 'w') as f, contextlib.redirect_stdout(f):
            result =  eval(callfunction0)(sha256=sha256,year_for_file=year_for_file)

        text = f"fcg doen {sha256}"

        append_sha256_to_file_for_of_csv_of_mnf_java_fcg(text)

        # print("Exit in  FCG")  

    except ValueError as e:
        print("Error on F_C_G_csv:", e)
    except PermissionError as e:
        print(f"Permission Denied on F_C_G_csv: {e}")
    except Exception as e:
                        # Restore stdout and stderr before printing any other errors
        print(f"Unexpected error on F_C_G_csv: {e}")


    callfunction = 'permission3.main'
    try:
        print("Enter in  Permission")
                        # print("Before function call")  # Debug statement
                        # Call the function
        with open(os.devnull, 'w') as f, contextlib.redirect_stdout(f):
            result =  eval(callfunction)(sha256=sha256,year_for_file=year_for_file)

        text = f"Permission doen{sha256}"
        append_sha256_to_file_for_of_csv_of_mnf_java_fcg(text)


        print("Exit in  Pernission")
                        # print("After function call")
    except ValueError as e:
        print("Error on permission_csv:", e)
    except PermissionError as e:
        print(f"Permission Denied on permission_csv: {e}")
    except Exception as e:
                        # Restore stdout and stderr before printing any other errors
        print(f"Unexpected error on permission_csv: {e}")


    # callfunction2 = 'java_keyword_find6.main'
    # try:
    #     print("Enter in  java")
    #                     # print("Before function call")  # Debug statement
    #     #                 # Call the function
    #     # with open(os.devnull, 'w') as f, contextlib.redirect_stdout(f):
    #     #     result =  eval(callfunction2)(sha256=sha256,year_for_file=year_for_file)


    #     def run_callfunction(sha256, year_for_file, callfunction2):
    #         with open(os.devnull, 'w') as f, contextlib.redirect_stdout(f):
    #             result = eval(callfunction2)(sha256=sha256, year_for_file=year_for_file)
    #             return result

    #     def run_with_timeout(sha256, year_for_file, callfunction2, timeout_duration=360):
    #         with concurrent.futures.ThreadPoolExecutor() as executor:
    #             future = executor.submit(run_callfunction, sha256, year_for_file, callfunction2)
    #             try:
    #                 result = future.result(timeout=timeout_duration)
    #                 return result
    #             except concurrent.futures.TimeoutError:
    #                 print(f"Execution timed out after {timeout_duration} seconds.")
    #                 return None  # Handle as necessary

        
    #     result = run_with_timeout(sha256=sha256, year_for_file=year_for_file, callfunction2=callfunction2, timeout_duration=360)


    #     text = f"java doen {sha256}"
    #     append_sha256_to_file_for_of_csv_of_mnf_java_fcg(text)
    #     print("Exit in  Java")
    #                     # print("After function call")
    # except ValueError as e:
    #     print("Error on java_csv:", e)
    # except PermissionError as e:
    #     print(f"Permission Denied on java_csv: {e}")
        # except Exception as e:
        #                     # Restore stdout and stderr before printing any other errors
        #     print(f"Unexpected error on java_csv: {e}")
    # import os
    # import contextlib
    # import concurrent.futures
    # import signal
    # import java_keyword_find6  # Import your module here

    # This function will handle process termination signals, ensuring the script doesn't get stuck.
    # import os
    # import contextlib
    # import concurrent.futures
    # import psutil  # To check process status if needed
    # import java_keyword_find6  # Import your module here





    # Main script with error handling and timeout control
    try:
    #     signal.signal(signal.SIGTERM, timeout_handler)  # Catch SIGTERM signal (for process termination)
    #     signal.signal(signal.SIGKILL, timeout_handler)  # Catch SIGKILL signal (for forceful process kill)

        print("Before calling run_with_timeout")  # Debugging before timeout
        result = run_with_timeout(sha256=sha256, year_for_file=year_for_file, timeout_duration=900)

        if result is not None:
            print(f"Result obtained: {result}")  # Debugging after function completes
            text = f"java done {sha256}"
            append_sha256_to_file_for_of_csv_of_mnf_java_fcg(text)
        else:
            print("No result obtained, continuing main script...")  # If no result due to timeout or error

        print("Exit in Java")
    except ValueError as e:
        print("Error on java_csv:", e)
    except PermissionError as e:
        print(f"Permission Denied on java_csv: {e}")
    except Exception as e:
        print(f"Unexpected error on java_csv: {e}")




    text = f'{i} {sha256}'
    append_sha256_to_file_for_of_csv_of_mnf_java_fcg(text)
        

    progress_barr_mnf_java_fcg_csv.update(1)




def delete_non_empty_folder(folder_name):
    apk_path = get_file_path(folder_name)
    folder_path = os.path.join(apk_path,year_for_file)
    # Check if the folder exists and is a directory
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        try:
            # Use shutil.rmtree to delete the folder and its contents
            shutil.rmtree(folder_path)
            print(f"Successfully deleted {folder_path}")
        except Exception as e:
            print(f"Error deleting {folder_path}: {e}")
    else:
        print(f"The folder {folder_path} does not exist or is not a directory")

# def set_high_priority():
#     """Set the current process to high priority."""
#     p = psutil.Process(os.getpid())
#     p.nice(psutil.HIGH_PRIORITY_CLASS)
#     print(f"Process with PID {p.pid} set to high priority.")


# Main function
def main():
    warnings.filterwarnings('ignore')

    # Get current process
    p = psutil.Process(os.getpid())

    # Set priority to high
    p.nice(psutil.HIGH_PRIORITY_CLASS)

    # Alternatively, use win32api to set priority
    handle = win32api.GetCurrentProcess()
    win32process.SetPriorityClass(handle, win32process.REALTIME_PRIORITY_CLASS)


    # check_csv_open()

    file_name = 'AXMLPrinter2'  # Assigning the name of the file.
    file_path = get_file_path(file_name)  # Getting the absolute path of the file.
    print("File path:", file_path)  # Printing the absolute path of the file.

    # Adding the directory containing apktool to the system path.
    directory_to_add = os.path.dirname(file_path)  # Getting the directory name from the file path.
    add_to_path(directory_to_add)  # Adding the directory to the system path.

    # Geting of apktool.bat and adding '\\' 
    path_of_axmlprinter2 = os.path.join(file_path, 'AXMLPrinter2.jar')
    # Replace single backslashes with double backslashes
    path_of_axmlprinter2 = path_of_axmlprinter2.replace('\\', '\\\\')




    global year_for_file
    name_of_file, year_for_file, output_dir = cp.main_for_cut()

    count_file_in_apk_dir = count_files_in_directory(output_dir)



    count_file_in_apk_dir = int(count_file_in_apk_dir)


    # for name in name_of_file:
    #     decompile_call(name,0,path_of_axmlprinter2,hashlib.sha256(name.encode

    # count_decopiled = 0
    # count_file_in_apk_dir = int(count_file_in_apk_dir)    
 
    start_time = datetime.now()
            # Define the text you want on the left side
    left_text = "Process Started at:"
    # Define the width of the line (total characters per line)
    line_width = 100
    # Format the line with left text and start_time on the right
    formatted_line = f"\n{left_text:<{line_width - len(str(start_time))}}{start_time}"
    append_sha256_to_file_for_decompile(formatted_line)                                          

    decompilation_start_time = time.time()
    try:
        batch_size = 10
        for batch_start in range(0,count_file_in_apk_dir,batch_size):
            batch_end = min(batch_start + batch_size, count_file_in_apk_dir)

            feature_csv = []
            feature_decompile =[] 


            for i in range(batch_start,batch_end):
                name = name_of_file[i]
                file_name_for_copy = f"{name}.apk"
                # source_file = os.path.join("APK",year_for_file,file_name_for_copy)
                # destination_file =  os.path.join("APK_fcg",year_for_file,file_name_for_copy)
                copy_apk_file(file_name_for_copy)


            # try:

            #     progress_barr_fcg = tqdm(total=batch_size, unit="step", desc=f"F_C_G csv {batch_start+1} - {batch_end}",dynamic_ncols=True,leave=True, position=0)#F_C_G = function call graph

            #     for i in range(batch_start,batch_end):
            #         sha256 = name_of_file[i]
            #         callfunction0 = 'function_call_graph.main'


            #         try:
            #             # print("Before function call")  # Debug statement
            #             # Call the function
            #             with open(os.devnull, 'w') as f, contextlib.redirect_stdout(f):
            #                 result =  eval(callfunction0)(sha256=sha256,year_for_file=year_for_file)
                            

            #         except ValueError as e:
            #             print("Error on F_C_G_csv:", e)
            #         except PermissionError as e:

            #             print(f"Permission Denied on F_C_G_csv: {e}")
            #         except Exception as e:
            #             # Restore stdout and stderr before printing any other errors
            #             print(f"Unexpected error on F_C_G_csv: {e}")

            #         progress_barr_fcg.update(1)


            #     progress_barr_fcg.close()

            # except Exception as e:
            #     print("Error Occures in F_C_F: ",e)
    
            
            decompilation_start_time = time.time()
            try:

                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                    for i in range(batch_start,batch_end) :
                    

                        # sha256 = sha256_all[i]  # Accessing SHA256 hash from the list
                        # text = f'{i+1} {sha256}'
                        # append_sha256_to_file(text) #appending sha256 with count assume that sha256 count 1 = 0, 2=1 in csv
                        name = name_of_file[i]
                        text = f'{i+1} {name}'
                        append_sha256_to_file_for_decompile(text) #appending sha256 with count assume that sha256 count 1 = 0, 2=1 in csv
                        # name = sha256
                        # count_decopiled +=1
                        
                        feature = executor.submit(decompile_call,name,i,path_of_axmlprinter2=path_of_axmlprinter2)  # Calling function to
                        feature_decompile.append(feature)
                    for s in as_completed(feature_decompile):
                        try:
                            s.result()
                        except Exception as e:
                            print(f"An error occurred in decompile: {e}")

            except Exception as e:
                print("Error in Decompiling: " ,e)


            try:

                progress_barr_mnf_java_fcg_csv = tqdm(total=batch_size, unit="step", desc=f"MNF,JAVA & FCG csv {batch_start+1} - {batch_end}",dynamic_ncols=True,leave=True, position=0)#F_C_G = function call graph
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:

                    for i in range(batch_start,batch_end):
                        sha256 = name_of_file[i]

                        feature = executor.submit(csv_of_mnf_java_fcg,sha256,progress_barr_mnf_java_fcg_csv,i)
                        feature_csv.append(feature)

                    


                progress_barr_mnf_java_fcg_csv.close()

            except Exception as e:
                print("Error Occures in MNF & JAVA CSV: ",e)


            
            
            decompilation_end_time = time.time()
            dec_time_sec = decompilation_end_time-decompilation_start_time
            dec_time = convert_time(dec_time_sec)
            # Print the elapsed time
            print(f"Time Taken to complete Decompile {batch_start+1} - {batch_end}: {dec_time}")
            print("\n")

            
                                
            apk_folder_name = 'APK_fcg' 
            delete_non_empty_folder(apk_folder_name)
            mnf_folder_name = 'MNF' 
            delete_non_empty_folder(mnf_folder_name)
            apk_zip_folder_name = 'apk_zip'
            delete_non_empty_folder(apk_zip_folder_name)
            apk_zip_extracted_folder_name = 'apk_zip_extracted'
            delete_non_empty_folder(apk_zip_extracted_folder_name)
            java_folder_name = 'JAVA'
            delete_non_empty_folder(java_folder_name)

    except Exception as e:
        print("Error Ocures: ",e )
            
    
    end_time = datetime.now()
    # Define the text you want on the left side
    left_text = "Process End at:"
    # Define the width of the line (total characters per line)
    line_width = 100
    # Format the line with left text and start_time on the right
    formatted_line = f"\n{left_text:<{line_width - len(str(end_time))}}{end_time}"
    append_sha256_to_file_for_decompile(formatted_line)
    text = '\n\n'
    append_sha256_to_file_for_decompile(text)



if __name__ == "__main__" :
    main()



import os
import shutil
from tqdm import tqdm
import time
from logging_config import get_logger
logger = get_logger(__name__)
logger.info("module_loaded")

mb = "MB"


def convert_bytes(size_in_bytes):
    kilobyte = 1024
    megabyte = kilobyte * 1024
    gigabyte = megabyte * 1024
    terabyte = gigabyte * 1024

    size_in_megabytes = size_in_bytes / megabyte
    size_in_gigabytes = size_in_bytes / gigabyte
    size_in_terabytes = size_in_bytes / terabyte
    
    if size_in_bytes < megabyte:
        return size_in_bytes, "B"
    elif size_in_bytes < gigabyte:
        return size_in_megabytes, "MB"
    elif size_in_bytes < terabyte:
        return size_in_gigabytes, "GB"
    else:
        return size_in_terabytes, "TB"


def calculate_total_apk_size(folder_name):
    total_size = 0
    for root, dirs, files in os.walk(folder_name):
        for file in files:
            if file.endswith(".apk"):
                full_file_path = os.path.join(root, file)
                total_size += os.path.getsize(full_file_path)
    return total_size 

def get_file_size_with_retry(file_path, retries=5, delay=0.5):
    """Retries getting the file size if it's initially 0 bytes."""
    for _ in range(retries):
        size = os.path.getsize(file_path)
        if size > 0:
            return size
        time.sleep(delay)  # Wait before retrying
    return size  # Return whatever size was found after retries

def count_files_in_directory(folder_name):
    file_count = 0
    for root, dirs, files in os.walk(folder_name):
        for file in files:
            if file.endswith(".apk"):
                file_count += 1  # Count the number of files in each directory
                
    return file_count

def extract_apk_files(folder_name):
    # Check if the provided folder exists
    if not os.path.exists(folder_name):
        print(f"The folder '{folder_name}' does not exist.")
        return
    
    total_file = count_files_in_directory(folder_name) 
    total_size = calculate_total_apk_size(folder_name) / 1024*1024
    # total_size,unitss = convert_bytes(total_size_in_mb)

    count_of_moved_file = 0
    size_of_moved_file_all = 0
    print(f"\rMoving [{count_of_moved_file}|{total_file}] :  [{size_of_moved_file_all} | { total_size:.2f} {mb}]", end="")
    
    # Create a directory for the extracted .apk files
    output_dir = os.path.join("APK", year_for_file)
    os.makedirs(output_dir, exist_ok=True)

    apk_name = []
    
    # Walk through the directory and extract .apk files
    for root, dirs, files in os.walk(folder_name):
        for file in files:
            if file.endswith(".apk"):
                full_file_path = os.path.join(root, file)
                destination_file_path = os.path.join(output_dir, file)

                path_parts = destination_file_path.split("\\")
                last_part = path_parts[-1].split('.')[0]
                apk_name.append(last_part)

                # Check if the file already exists in the output directory
                if os.path.exists(destination_file_path):
                    print(f"Duplicate found and ignored: {destination_file_path}")
                    continue
                
                # Move the file and update the progress bar
                shutil.move(full_file_path, destination_file_path)
                   # Retry to get correct file size
                size_of_moved_file = get_file_size_with_retry(destination_file_path) / 1024*1024
                # size_of_moved_file,unit  = convert_bytes(size_of_moved_file)


                size_of_moved_file = round(size_of_moved_file,2) if size_of_moved_file is not None else 0.00
                # print(size_of_moved_file)


                if size_of_moved_file is None or size_of_moved_file <= 0:
                    print(f"Warning: Could not determine the size for {destination_file_path}, skipping progress update.")
                    continue
                count_of_moved_file += 1
                size_of_moved_file_all += size_of_moved_file

                print(f"\rMoving [{count_of_moved_file}|{total_file}] :  [{size_of_moved_file_all} | { total_size:.2f} {mb}]",end ="")
                # size_of_moved_file = float(size_of_moved_file)
                # try:
                
                # print(f"Moved {last_part}: {size_of_moved_file:.2f} {unit}")
                # except Exception as e:
                #     print(f"Error updating progress bar: {e}")
                #     continue
                # else:
                #     print(f"Warning: Could not determine the size for {destination_file_path}")

    # progress_bar.close()
    
    print(f"\nAll .apk files have been extracted to: {output_dir}")
    # total_file_in_ouyput_dir = count_files_in_directory
    # total_file_in_ouyput_dir = int(total_file_in_ouyput_dir)
    return apk_name , output_dir


def main_for_cut():
    # Prompt the user to input the folder name
    folder_name = input("Enter the folder name (file path or Absolute path): ")
    global year_for_file
    year_for_file = input("Enter the year for the file (If it is not specific, enter folder name): ")

    # # Calculate the total size of the .apk files for progress bar initialization
    # total_size_in_mb = calculate_total_apk_size(folder_name)
    # total_size,unitss = convert_bytes(total_size_in_mb)
    # print(f"Total size of .apk files: {total_size} {unitss}")

    # # Initialize the progress bar and force unit_scale to 1024 to use MB consistently
    # progress_bar_apk_moved = tqdm(total=total_size, unit=unitss, desc="Moving Files",bar_format='{l_bar}{bar}| {n:.2f}/{total:.2f} {unit} [{elapsed}, {rate_fmt}]')

    # Call the function to extract .apk files
    apk_name, output_dir= extract_apk_files(folder_name)

    # count_files_in_output_dir = int(count_files_in_output_dir)

    # Print the list of extracted APK names
    # print(apk_name)
    return apk_name , year_for_file,output_dir


if main_for_cut == __name__:
    main_for_cut
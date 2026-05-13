# print# Get current process
import os
# from time import sleep
import psutil
import time
import psutil
import win32api # type: ignore
import win32process # type: ignore
import win32con # type: ignore
import psutil
import os
import subprocess
from art import text2art
from colorama import init, Fore, Style
import random
import sys
import msvcrt
import threading
from art import aprint, art, randart
import apk_to_decompile as atd
import url_downloader as ud
import andr_download as andrd
import data_collection_download_and_decompile as dcdd
import ctypes
from ctypes import wintypes


def is_admin():
    """Check if the script is running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def set_high_priority():
    """Set the current process to high priority."""
    #    # Get current process
    p = psutil.Process(os.getpid())
    
    # Set priority to high
    p.nice(psutil.HIGH_PRIORITY_CLASS)
    
    # Alternatively, use win32api to set priority
    handle = win32api.GetCurrentProcess()
    win32process.SetPriorityClass(handle, win32process.REALTIME_PRIORITY_CLASS)

set_high_priority()


# show droidware
def blink_droidware():
    # Initialize colorama
    init(autoreset=True)

    def clear_lines(num_lines):
        """ Clear the specified number of lines in the terminal """
        for _ in range(num_lines):
            print("\033[F\033[K", end="")

    def blink_text(stop_event):
        fonts = ["standard"]

        colors = [Fore.RED, Fore.GREEN, Fore.YELLOW, Fore.BLUE, Fore.MAGENTA, Fore.CYAN, Fore.WHITE]
        while not stop_event.is_set():
            # Choose a random color and font
            color = random.choice(colors)
            font = random.choice(fonts)

            # Create the text art with the selected font
            design_text = text2art("Droidware", font)

            # Print the text in the selected color and bold
            print(color + Style.BRIGHT + design_text)
            time.sleep(0.7)
            clear_lines(design_text.count('\n') + 1)

            time.sleep(0.5)
        # Clear the console after stopping
        clear_lines(design_text.count('\n') + 1)
        print(color + Style.BRIGHT + design_text)

    def wait_for_keypress_or_timeout(stop_event, timeout):
        """ Wait for user to press any key or for the timeout to occur """
        start_time = time.time()
        while time.time() - start_time < timeout:
            if stop_event.is_set():
                return
            if sys.platform.startswith('win') and msvcrt.kbhit():
                stop_event.set()
                return
            elif not sys.platform.startswith('win'):
                import termios
                import tty
                import select

                def is_data():
                    return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])

                old_settings = termios.tcgetattr(sys.stdin)
                try:
                    tty.setcbreak(sys.stdin.fileno())
                    if is_data():
                        stop_event.set()
                        return
                finally:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

            time.sleep(0.1)
        stop_event.set()

    print(Fore.RED+Style.BRIGHT+"Press any key or wait for the timeout to stop blinking...\n")

    stop_event = threading.Event()
    timeout = 5  # 5 seconds timeout

    blink_thread = threading.Thread(target=blink_text, args=(stop_event,))
    input_thread = threading.Thread(target=wait_for_keypress_or_timeout, args=(stop_event, timeout))

    input_thread.start()
    blink_thread.start()

    # Wait for the input thread to finish
    input_thread.join()
    blink_thread.join()



def take_input_in_int(start_choice,end_choice):
    while True:
        try:
            print(Fore.YELLOW+"Enter your choice: ",end="")
            choice = int(input())
            if type(choice)== int:
                if (start_choice <= choice <= end_choice):
                    print("")
                    return(choice)
                else:
                    wrong_choice = (f"Please choose Choise between {start_choice} - {end_choice}.")
                    print(Fore.RED+Style.BRIGHT+wrong_choice)
                    continue
        except ValueError as e:
            error_text = ("Invalid input. Please enter a number.")
            print(Fore.RED+Style.BRIGHT+error_text)
            continue    

def main():
    # Set priority for the current process
    set_high_priority()

    blink_droidware()

    print("1. Download\n2. Decompile\n3. Download and Decompile\n")
    input_of_first_choice = take_input_in_int(1,3)

    if input_of_first_choice == 1:
        try:
            print("1. Downlod by URL\n2. Downlod from Androzoo")
            input_of_downlod = take_input_in_int(1,2)
            if input_of_downlod == 1:

                message = "Download From URL"
                print(Fore.YELLOW + Style.BRIGHT + "=" * len(message))
                print(Fore.MAGENTA+message)
                print(Fore.YELLOW + Style.BRIGHT +"=" * len(message))

                ud.main()
            elif input_of_downlod == 2:
                message = "Download From Androzoo"
                print(Fore.YELLOW + Style.BRIGHT + "=" * len(message))
                print(Fore.MAGENTA+message)
                print(Fore.YELLOW + Style.BRIGHT +"=" * len(message))
                andrd.main() 
            
        except Exception as e:
            print(Fore.RED+Style.BRIGHT+f"Error!! Download From URL: {e}")
        


    elif input_of_first_choice == 2:
        # print("1. Decompile by APKTool\n2. Decompile by Jadx")
        try:
            # print(Fore.YELLOW+Style.BRIGHT+Style.__sizeof__+"Decompiling and Creating CSV")
            message = "Decompiling and Creating CSV"
            print(Fore.YELLOW + Style.BRIGHT + "=" * len(message))
            print(Fore.MAGENTA+message)
            print(Fore.YELLOW + Style.BRIGHT +"=" * len(message))
            atd.main()
        
        except Exception as e:
            print(Fore.RED+Style.BRIGHT+f"Error!! Decompiling and Creating CSV: {e}")
        

    elif input_of_first_choice == 3:
        # print("1. Download by URL\n2. Download from Androzoo")
        try:
            message = "Download From Androzoo and Decompile"
            print(Fore.YELLOW + Style.BRIGHT + "=" * len(message))
            print(Fore.MAGENTA+message)
            print(Fore.YELLOW + Style.BRIGHT +"=" * len(message))
            dcdd.main() 
        
        except Exception as e:
            print(Fore.RED+Style.BRIGHT+f"Error!! Download From Androzoo and Decompile: {e}")




    

if __name__ == "__main__":
    main()

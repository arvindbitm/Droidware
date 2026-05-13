import csv
from collections import defaultdict
from androguard.misc import AnalyzeAPK
import os
import sys
import logging
import warnings
from tqdm import tqdm
import time
import threading as Thread
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from loguru import logger
import pandas as pd
from datetime import datetime
from multiprocessing import Pool, Manager, cpu_count
from concurrent.futures import ThreadPoolExecutor
import cProfile
import pstats
import psutil
import win32api # type: ignore
import win32process # type: ignore
import win32con # type: ignore
# import cupy as cp  # Importing CuPy for GPU processing


def set_high_priority():
    """Set the current process to high priority."""
       # Get current process
    p = psutil.Process(os.getpid())
    
    # Set priority to high
    p.nice(psutil.HIGH_PRIORITY_CLASS)
    
    # Alternatively, use win32api to set priority
    handle = win32api.GetCurrentProcess()
    win32process.SetPriorityClass(handle, win32process.REALTIME_PRIORITY_CLASS)



logger.remove()

# Set up logging
logging.basicConfig(filename='errors.log', level=logging.ERROR, 
                    format='%(asctime)s:%(levelname)s:%(message)s')

# List of methods to track (in the desired format)
methods_to_track = [
    "ACCESS_NETWORK_STATE", "ACCESS_FINE_LOCATION", "ACCESS_COARSE_LOCATION", "ACCESS_WIFI_STATE", "CHANGE_WIFI_STATE", "CHANGE_NETWORK_STATE", "INTERNET", "READ_PHONE_STATE", "READ_CONTACTS", "WRITE_CONTACTS", "READ_SMS", "SEND_SMS", "RECEIVE_SMS", "READ_EXTERNAL_STORAGE", "WRITE_EXTERNAL_STORAGE", "BLUETOOTH", "BLUETOOTH_ADMIN", "RECORD_AUDIO", "CAMERA", "GET_TASKS", "READ_LOGS", "SYSTEM_ALERT_WINDOW", "KILL_BACKGROUND_PROCESSES", "MANAGE_DOCUMENTS", "REQUEST_IGNORE_BATTERY_OPTIMIZATIONS", "REQUEST_INSTALL_PACKAGES", "BIND_ACCESSIBILITY_SERVICE", "BIND_VPN_SERVICE", "BIND_DEVICE_ADMIN", "ACCESS_NOTIFICATION_POLICY", "USE_FINGERPRINT", "USE_BIOMETRIC", "BIND_REMOTEVIEWS", "BIND_INPUT_METHOD", "BIND_TEXT_SERVICE", "BIND_TV_INPUT", "BIND_AUTOFILL", "BIND_AUTOFILL_SERVICE", "BIND_INCALL_SERVICE", "BIND_NOTIFICATION_LISTENER_SERVICE", "BIND_PRINT_SERVICE", "BIND_SCREENING_SERVICE", "BIND_QUICK_SETTINGS_TILE", "BIND_WALLPAPER", "BIND_WEATHER_PROVIDER", "BIND_WEARABLE_MESSAGES", "BIND_VR_LISTENER_SERVICE", "BIND_VISUAL_VOICEMAIL_SERVICE", "BIND_AUTOFILL_SERVICE", "BIND_CARRIER_SERVICES", "BIND_JOB_SERVICE", "BIND_NFC_SERVICE", "BIND_SCREENING_SERVICE", "BIND_ROUTE_PROVIDER", "BIND_ROUTE_MANAGEMENT", "BIND_ROUTE_PROVIDER", "BIND_SPELL_CHECKER_SERVICE", "BIND_TELECOM_CONNECTION_SERVICE", "BIND_TV_INPUT", "BIND_NOTIFICATION_RANKER_SERVICE", "BIND_TV_INPUT", "BIND_PRINT_SERVICE", "BIND_CARRIER_SERVICES", "BIND_AUTOFILL_SERVICE", "BIND_INPUT_METHOD", "BIND_SCREENING_SERVICE", "BIND_REMOTEVIEWS", "BIND_AUTOFILL_SERVICE", "BIND_CARRIER_SERVICES", "BIND_NOTIFICATION_LISTENER_SERVICE", "BIND_ROUTE_PROVIDER", "BIND_NOTIFICATION_LISTENER_SERVICE", "BIND_PRINT_SERVICE", "BIND_SCREENING_SERVICE", "BIND_TEXT_SERVICE", "BIND_SCREENING_SERVICE", "BIND_TELECOM_CONNECTION_SERVICE", "BIND_ROUTE_PROVIDER", "BIND_AUTOFILL_SERVICE", "BIND_INPUT_METHOD", "BIND_TELECOM_CONNECTION_SERVICE", "BIND_QUICK_SETTINGS_TILE", "BIND_VISUAL_VOICEMAIL_SERVICE", "BIND_AUTOFILL_SERVICE", "BIND_ROUTE_PROVIDER", "BIND_SCREENING_SERVICE", "BIND_SPELL_CHECKER_SERVICE", "BIND_TV_INPUT", "BIND_CARRIER_SERVICES", "BIND_AUTOFILL_SERVICE", "BIND_TV_INPUT", "BIND_PRINT_SERVICE", "BIND_TELECOM_CONNECTION_SERVICE", "BIND_QUICK_SETTINGS_TILE", "BIND_ROUTE_PROVIDER", "BIND_AUTOFILL_SERVICE", "BIND_CARRIER_SERVICES", "BIND_SCREENING_SERVICE", "BIND_QUICK_SETTINGS_TILE", "BIND_ROUTE_PROVIDER", "getSystemService", "getDeviceId", "getSubscriberId", "getSimSerialNumber", "getLine1Number", "exec", "Runtime.getRuntime()", "ProcessBuilder", "openConnection", "FileOutputStream", "FileInputStream", "delete", "mkdir", "sendTextMessage", "startActivity", "startService", "bindService", "ContentResolver.query", "Settings.System", "checkPermission", "checkCallingPermission", "checkCallingOrSelfPermission", "checkSelfPermission", "HttpURLConnection", "HttpsURLConnection", "Socket", "DatagramSocket", "URL.openConnection", "URLConnection", "org.apache.http", "Class.forName", "getMethod", "getDeclaredMethod", "invoke", "dexClassLoader", "pathClassLoader", "loadClass", "loadDex", "Binder", "Parcel", "Service", "BroadcastReceiver", "Intent", "Messenger", "SharedPreferences", "openFileOutput", "openFileInput", "getExternalStorageDirectory", "Environment.getExternalStorageDirectory", "SQLiteDatabase", "Cipher", "MessageDigest", "KeyGenerator", "Signature", "KeyPairGenerator", "SecretKeySpec", "sendTextMessage", "sendMultipartTextMessage", "sendDataMessage", "TelephonyManager", "SmsManager", "Build", "Build.VERSION", "Build.MODEL", "Build.MANUFACTURER", "Build.SERIAL", "Log.d", "Log.e", "Log.i", "Log.v", "Log.w", "Runtime.exec", "ProcessBuilder", "System.loadLibrary", "System.load", "System.exit", "File.createNewFile", "File.delete", "File.mkdirs", "File.renameTo", "File.listFiles", "FileWriter", "FileReader", "ClipboardManager", "getPrimaryClip", "setPrimaryClip", "MediaRecorder", "setAudioSource", "setVideoSource", "startRecording", "Camera Access:", "Camera.open", "takePicture", "startPreview", "stopPreview", "LocationManager", "getLastKnownLocation", "requestLocationUpdates", "GPS_PROVIDER", "NETWORK_PROVIDER", "SensorManager", "getDefaultSensor", "registerListener", "unregisterListener", "ContactsContract", "SmsProvider", "query", "insert", "update", "delete", "WebView", "loadUrl", "evaluateJavascript", "addJavascriptInterface", "CallLog.Calls", "getContentResolver", "insertCallLog", "deleteCallLog", "queryCallLog", "PowerManager", "newWakeLock", "acquire", "release", "AlarmManager", "setRepeating", "setExact", "setInexactRepeating", "NotificationManager", "notify", "cancel", "PackageManager", "getInstalledPackages", "getPackageInfo", "queryIntentActivities", "AccountManager", "getAccounts", "addAccount", "removeAccount", "System.getProperty", "System.setProperty", "loadLibrary", "System.loadLibrary", "AsyncTask", "Thread", "Handler", "Looper", "su", "superuser", "root", "busybox", "AdView", "AdRequest", "setAdListener", "GoogleAnalytics", "FirebaseAnalytics", "Base64", "AES", "DES", "RSA", "Obfuscator", "ProGuard", "FirebaseMessagingService", "onMessageReceived", "send", "notification", "BluetoothAdapter", "BluetoothDevice", "connect", "pair", "discover", "WifiManager", "getWifiState", "setWifiEnabled", "getConnectionInfo", "NfcAdapter", "enableForegroundDispatch", "disableForegroundDispatch", "AccessibilityService", "onAccessibilityEvent", "performGlobalAction", "ProcessBuilder", "mount", "chmod", "chown", "ln", "dd", "try", "catch", "finally", "Exception", "Error", "Debug.isDebuggerConnected", "SharedPreferences", "Settings.Secure", "Settings.Global", "Settings.System", "MessageDigest", "DigestInputStream", "Cipher", "KeyGenerator", "SecretKeySpec", "KeyFactory", "Mac", "HmacSHA256", "PBKDF2WithHmacSHA1", "IvParameterSpec", "JSONObject", "JSONArray", "Gson", "JsonParser", "SSLContext", "X509TrustManager", "HttpsURLConnection", "SSLSession", "BroadcastReceiver", "onReceive", "registerReceiver", "unregisterReceiver", "Service", "IntentService", "startService", "stopService", "bindService", "unbindService", "ContentProvider", "ContentResolver", "query", "insert", "update", "delete", "checkPermission", "requestPermissions", "grantUriPermission", "revokeUriPermission", "SQLiteDatabase", "execSQL", "query", "insert", "update", "delete", "Instrumentation", "startInstrumentation", "sendKeySync", "sendPointerSync", "DexClassLoader", "PathClassLoader", "BaseDexClassLoader", "loadClass", "Sensor.TYPE_PROXIMITY", "Sensor.TYPE_ACCELEROMETER", "Sensor.TYPE_GYROSCOPE", "MediaPlayer", "MediaStore", "ExifInterface", "ActivityManager", "getRunningTasks", "getRunningAppProcesses", "killBackgroundProcesses", "WebSocket", "Socket", "ServerSocket", "SocketChannel", "FirebaseStorage", "AmazonS3", "GoogleDrive", "GoogleMap", "MapView", "Geocoder", "ViewGroup", "LayoutInflater", "ViewStub", "SurfaceView", "NotificationChannel", "createNotificationChannel", "deleteNotificationChannel", "DownloadManager", "enqueue", "query", "remove", "GarbageCollector", "Runtime.getRuntime", "freeMemory", "BluetoothLeScanner", "BluetoothGatt", "BluetoothGattCallback", "MotionEvent", "onTouchEvent", "dispatchTouchEvent", "Calendar", "Date", "SimpleDateFormat", "TimeUnit", "FingerprintManager", "BiometricPrompt", "authenticate", "Frida", "Xposed", "substrate", "ExecutorService", "ScheduledExecutorService", "FutureTask", "Messenger", "AIDL", "Binder", "Parcel", "Method", "Field", "Constructor", "setAccessible", "Log.d", "Log.e", "Log.i", "Log.w", "Log.v", "Locale", "getDefault", "setDefault", "AccessibilityNodeInfo", "performAction", "findAccessibilityNodeInfosByText", "ConnectivityManager", "NetworkInfo", "getActiveNetworkInfo", "TelephonyManager", "getDeviceId", "getSimSerialNumber", "UsbManager", "UsbDevice", "UsbInterface", "Vibrator", "vibrate", "cancel", "BackupManager", "restore", "Intent.ACTION_BATTERY_CHANGED", "Intent.ACTION_BOOT_COMPLETED", "Intent.ACTION_PACKAGE_ADDED", "onSaveInstanceState", "onRestoreInstanceState", "AppWidgetManager", "AppWidgetProvider", "KeyStore", "CipherOutputStream", "CipherInputStream", "InputMethodManager", "showSoftInput", "hideSoftInputFromWindow", "SessionManager", "getActiveSessions", "addOnActiveSessionsChangedListener", "GoogleAnalytics", "FirebaseAnalytics", "setUserId", "FirebaseRemoteConfig", "fetch", "activateFetched", "BillingClient", "queryPurchases", "launchBillingFlow", "onCreate", "onStart", "onResume", "onPause", "onStop", "onDestroy", "MediaProjection", "VirtualDisplay", "ImageReader", "AssetManager", "Resources", "getDrawable", "ObjectAnimator", "AnimatorSet", "ViewPropertyAnimator", "onClick", "onLongClick", "onTouch", "ProgressBar", "setProgress", "setIndeterminate", "ZipInputStream", "ZipOutputStream", "GZIPOutputStream", "GZIPInputStream", "RemoteCallbackList", "RemoteServiceException", "LoaderManager", "Loader", "CursorLoader", "LeakCanary", "WeakReference", "SoftReference", "HttpURLConnection", "SocketTimeoutException", "UnknownHostException", "LifecycleObserver", "onLifecycleEvent", "DynamicDelivery", "SplitInstallManager", "SplitInstallRequest", "AppUpdateManager", "AppUpdateInfo", "startUpdateFlow"
]



def create_dir_if_not(output_directory):
    # Create the output directory if it doesn't exist
    os.makedirs(output_directory, exist_ok=True)

def get_file_path(file_name):
    try:
        # Get the absolute path of the file
        file_path = os.path.abspath(file_name)
        return file_path
    except FileNotFoundError:
        return f"File '{file_name}' not found."
    
# def suppress_output(sha256,year_for_file):
#     # Save the current stdout and stderr
#     saved_stdout = sys.stdout
#     saved_stderr = sys.stderr
    
#     # Redirect stdout and stderr to devnull
#     sys.stdout = open(os.devnull, 'w')
#     sys.stderr = open(os.devnull, 'w')
    
#     try:
#         # Call the function
#         # result =  function_call_graph.main(sha256,year_for_file)
#     finally:
#         # Restore the original stdout and stderr
#         sys.stdout = saved_stdout
#         sys.stderr = saved_stderr
    
#     return result


# def analyze_apk(apk_path):
#     """Analyze the APK and return the APK object and DalvikVMFormat object."""
#     # a, _, dx = AnalyzeAPK(apk_path)

#     saved_stdout = sys.stdout
#     saved_stderr = sys.stderr
    
#     # Redirect stdout and stderr to devnull
#     sys.stdout = open(os.devnull, 'w')
#     sys.stderr = open(os.devnull, 'w')
  
#     # Get the root logger
#     root_logger = logging.getLogger()
    
#     # Create a no-op handler
#     class NullHandler(logging.Handler):
#         def emit(self, record):
#             pass
    
#     # Save the original handlers
#     original_handlers = root_logger.handlers[:]
    
#     try:
#         # Replace the handlers with the null handler
#         root_logger.handlers = [NullHandler()]
        
#         # Call the function
#         a, _, dx = AnalyzeAPK(apk_path)
#     finally:
#         # Restore the original stdout and stderr
#         sys.stdout = saved_stdout
#         sys.stderr = saved_stderr
        
#         # # Restore the original handlers
#         root_logger.handlers = original_handlers
#     return a, dx

class SuppressOutput:
    def __enter__(self):
        # Save original file descriptors
        self.stdout_fd = sys.stdout.fileno()
        self.stderr_fd = sys.stderr.fileno()

        # Save copies of original file descriptors so they can be restored
        self.saved_stdout_fd = os.dup(self.stdout_fd)
        self.saved_stderr_fd = os.dup(self.stderr_fd)

        # Redirect stdout and stderr to devnull
        self.devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(self.devnull, self.stdout_fd)
        os.dup2(self.devnull, self.stderr_fd)

    def __exit__(self, exc_type, exc_value, traceback):
        # Restore original stdout and stderr file descriptors
        os.dup2(self.saved_stdout_fd, self.stdout_fd)
        os.dup2(self.saved_stderr_fd, self.stderr_fd)

        # Close the file descriptors
        os.close(self.devnull)
        os.close(self.saved_stdout_fd)
        os.close(self.saved_stderr_fd)


def suppress_output():
    with open(os.devnull, 'w') as devnull:
        with redirect_stdout(devnull), redirect_stderr(devnull):
            yield
def analyze_apk(apk_path):
    
    # with SuppressOutput():
    try:
        
        # suppress_output()
        # Simulate the processing of the APK
        set_high_priority()
        a, _, dx = AnalyzeAPK(apk_path)
        
        # progress_bar.update(1)
        
      
    except ValueError as e:
        logging.error(f"ValueError: {e} - This might indicate a corrupted or invalid APK file.")
        return None, None
    except Exception as e:
        logging.error(f"Error occurred when analyzing APK: {e}")
        return None, None
        
    return a, dx



def extract_methods_and_calls(dx):
    """Extract methods and their call counts from the APK analysis."""
    method_occurrences = defaultdict(list)
    method_call_count = defaultdict(int)
    # print('extract')

    try:
        


        # Function to run in a thread
        def thread_function(method):
            process_method(method_occurrences, method_call_count, method)

        # for method in dx.get_methods():
            
        #     # process_method(method_occurrences, method_call_count, method)
        #     thread = threading.Thread(target=thread_function, args=(method,))
        #     threads.append(thread)
        #     thread.start()


        # Use ThreadPoolExecutor to limit the number of simultaneous threads
        # cp = Pool(cpu_count())
        # result = pool()
        with ThreadPoolExecutor(max_workers=1000) as executor:  # Adjust max_workers as needed
            for method in dx.get_methods():
                executor.submit(thread_function, method)
        
        # Ensure all methods in methods_to_track are included with default values
        for method in methods_to_track:
            if method not in method_occurrences:
                method_occurrences[method] = []
            if method not in method_call_count:
                method_call_count[method] = 0

    except Exception as e:
        logging.error(f"Error occurred when extracting methods and calls: {e}")
        return None, None
    
    return method_occurrences, method_call_count

def process_method(method_occurrences, method_call_count, method):
    method_name_full = method.method.get_class_name() + "." + method.method.get_name()
    method_name = method_name_full.split(";")[-1]
            
    count_of_fulstop = method_name.count('.')
    count_of_fulstop = (-1)*count_of_fulstop
            # print(count_of_fulstop)
    method_name = method_name_full.split(".")[count_of_fulstop]
    simple_method_name = method_name.split('.')[-1]

    if simple_method_name in methods_to_track or method_name in methods_to_track:
        method_occurrences[method_name].append(method.method.get_class_name())

    for _, callee, _ in method.get_xref_to():
        callee_name_full = callee.method.get_class_name() + "." + callee.method.get_name()
        callee_name = callee_name_full.split(";")[-1]

        count_of_fulstop_cal = callee_name.count('.')
        count_of_fulstop_cal = (-1)*count_of_fulstop_cal
                # print(count_of_fulstop_cal)
                
        callee_name = callee_name_full.split(".")[count_of_fulstop_cal]
        simple_callee_name = callee_name.split('.')[-1]

        if simple_callee_name in methods_to_track or callee_name in methods_to_track:
            method_call_count[callee_name] += 1


def export_methods_to_csv(method_occurrences, method_call_count, output_path,sha256,methods_to_track):
    """Export the methods, their occurrences, and call counts to a CSV file."""
    try:
        file_exists = os.path.isfile(output_path)



        with open(output_path, 'a', newline='') as csvfile:
            csv_writer = csv.writer(csvfile)

            if not file_exists:
                # Write method names as a header
                a = []
                for method in methods_to_track:
                    b = method+ '_occurrences'
                    a.append(b)
                    c = method+ '_call_count'
                    a.append(c)
                csv_writer.writerow(['sha256']+a)

            # Write occurrences and call counts
            # for method, occurrences in method_occurrences.items():
                # call_count = method_call_count[method]
                # csv_writer.writerow([sha256]+['occurrences']+[len(occurrences)])
                # csv_writer.writerow([sha256]+['call count']+[call_count])

            row_occurrences = [len(method_occurrences.get(m, [])) for m in methods_to_track]
            row_call_counts = [method_call_count.get(m, 0) for m in methods_to_track]

            data_in_oneline = []
            for occ,call in zip(row_occurrences,row_call_counts):
                data_in_oneline.append(occ)
                data_in_oneline.append(call)
            csv_writer.writerow([sha256]+data_in_oneline)

            # rowouc = [sha256] +['occurrences']+ row_occurrences
            # rowcc = [sha256] +['call count']+ row_call_counts
            # csv_writer.writerow(rowouc)
            # csv_writer.writerow(rowcc)
                
    except PermissionError as e:
        print(f"Permission error: {e}. Please check if the file is open or if you have write permissions.")
    except Exception as e:
        print(f"An error occurred while writing to the file: {e}")

def main(sha256,year_for_file):
    """Main function to analyze the APK, extract methods, and export to CSV."""
    warnings.filterwarnings('ignore')

    set_high_priority()
    
    filename = 'APK_fcg'
    sha256 = str(sha256)
    year_for_file = str(year_for_file)
    apkname = sha256 + '.apk'
    apkfilepath = get_file_path(filename)

    apk_path = os.path.join(apkfilepath,year_for_file,apkname)

    output_csv = 'csv\\function_call_graph.csv'
    create_dir_if_not("csv")
    # # Analyze the APK
    # # a, dx = analyze_apk(apk_path)
    # def update_progress():
    #     for i in range(10):
    #         time.sleep(0.5)  # Simulate progress
    #         progress_bar.update(1)

    # # Start the progress updater in a separate thread
    # progress_thread = threading.Thread(target=update_progress)
    # progress_thread.start()

    # Analyze the APK
    # a, dx = analyze_apk(apk_path)

     # Profile the analyze_apk function
    # profiler = cProfile.Profile()
    # profiler.enable()
    a, dx = analyze_apk(apk_path)
    # profiler.disable()

    # Wait for the progress updater to finish
    # progress_thread.join()
    # progress_bar.close()

    
    # Extract methods and their call counts
    method_occurrences, method_call_count = extract_methods_and_calls(dx)
    
    # Export the methods, their occurrences, and call counts to CSV
    export_methods_to_csv(method_occurrences, method_call_count, output_csv,sha256,methods_to_track)
    print(f'Method occurrences and call counts exported to {output_csv}')

if __name__ == '__main__':
    # The script expects the APK to be in the same folder
    # apk_path = "D:\\cyber_security\\Project\\droidware\\APK\\2024\\00014E968641C92CD4245AF09EEC1DE5A231F040085C880C664437EC6D7272C9.apk"  # Replace with the actual APK file name
    # output_csv = 'csv\\methods_occurrences_and_calls.csv'
    # sha256 = '0006C62878EA21CE2E28ECB929E651886150F89946111913D1AEB7B072E062F2'
    # year_for_file = '2024'
    
    # # progress_bar = tqdm(total=1, desc='Progress')
    
    # main(sha256,year_for_file)

    # progress_bar.close()
    year_for_file = '2024'

    df = pd.read_csv("2024.csv",sep=" ",usecols=[1],header=None)

    sha256 = df.values.flatten()
    print(sha256)
    count_sha = len(sha256)
    progress_bar = tqdm(total=count_sha, desc='Progress')
    start_time = datetime.now()
    for i in range(0,count_sha):
        filename = sha256[i]
        main(filename,year_for_file)
        progress_bar.update(1)

    end_time = datetime.now()
    print(f"Time taken: {end_time - start_time}")

  

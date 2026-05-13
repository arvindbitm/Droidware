
import xml.etree.ElementTree as ET
import csv
import os

def extract_permissions(mnf_file_path):
    try:
        tree = ET.parse(mnf_file_path)
        root = tree.getroot()

        permissions = []
        for elem in root.iter():
            if elem.tag.endswith('permission'):
                name = elem.get('{http://schemas.android.com/apk/res/android}name')
                if name:  # Ensure the name attribute exists
                    permissions.append(name)

        if not permissions:
            print("No permission elements found in the XML file.")
            return []

        return permissions
    except ET.ParseError as e:
        print(f"Error parsing XML file: {e}")
        return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []

def check_permissions(mnf_file_path, permissions_to_check):
    permissions_found = extract_permissions(mnf_file_path)
    result = []
    for permission in permissions_to_check:
        permission = 'android.permission.'+permission
        if permission in permissions_found:
            result.append(1)  # Yes, permission found
        else:
            result.append(0)  # No, permission not found
    return result

def print_result(permissions_to_check, result):
    print("Permission Check Result:")
    print("----------------------------")
    for i, permission in enumerate(permissions_to_check):
        print(f"{permission}\t{result[i]}")
    print("----------------------------")

def write_to_csv(permissions_to_check, result, csv_file_path,sha256):
    file_exists = os.path.isfile(csv_file_path)
    with open(csv_file_path, 'a', newline='') as csvfile:
        writer = csv.writer(csvfile)

        if not file_exists:
            writer.writerow(["sha256"]+permissions_to_check )

        writer.writerow([sha256]+result)

def get_file_path(file_name):
    try:
        file_path = os.path.abspath(file_name)  # Getting the absolute path of the file.
        return file_path  # Returning the absolute path.
    except FileNotFoundError:
        return f"File '{file_name}' not found."

# Example usage

def main(sha256,year_for_file):
    year_for_file = str(year_for_file)
    sha256 = str(sha256)
    xml_name = sha256 + '.xml'

    file_name = 'MNF'
    file_path = get_file_path(file_name)
    mnf_file_path =os.path.join( file_path,year_for_file,xml_name)
    # print(mnf_file_path)
    permissions_to_check = [ "WRITE_CALENDAR",
        "CAMERA",
        "READ_CONTACTS",
        "WRITE_CONTACTS",
        "GET_ACCOUNTS",
        "ACCESS_FINE_LOCATION",
        "ACCESS_COARSE_LOCATION",
        "RECORD_AUDIO",
        "READ_PHONE_STATE",
        "CALL_PHONE",
        "READ_CALL_LOG",
        "WRITE_CALL_LOG",
        "ADD_VOICEMAIL",
        "USE_SIP",
        "PROCESS_OUTGOING_CALLS",
        "BODY_SENSORS",
        "SEND_SMS",
        "RECEIVE_SMS",
        "READ_SMS",
        "RECEIVE_WAP_PUSH",
        "RECEIVE_MMS",
        "READ_EXTERNAL_STORAGE",
        "WRITE_EXTERNAL_STORAGE",
        "INTERNET",
        "BLUETOOTH",
        "BLUETOOTH_ADMIN",
        "ACCESS_WIFI_STATE",
        "CHANGE_WIFI_STATE",
        "ACCESS_NETWORK_STATE",
        "CHANGE_NETWORK_STATE",
        "READ_SYNC_SETTINGS",
        "WRITE_SYNC_SETTINGS",
        "READ_SYNC_STATS",
        "VIBRATE",
        "WAKE_LOCK",
        "REORDER_TASKS",
        "GET_TASKS",
        "SYSTEM_ALERT_WINDOW",
        "RECEIVE_BOOT_COMPLETED",
        "DISABLE_KEYGUARD",
        "MODIFY_AUDIO_SETTINGS",
        "ACCESS_NOTIFICATION_POLICY",
        "BIND_ACCESSIBILITY_SERVICE",
        "BIND_DEVICE_ADMIN",
        "BIND_INPUT_METHOD",
        "BIND_NFC_SERVICE",
        "BIND_PRINT_SERVICE",
        "BIND_TEXT_SERVICE",
        "BIND_VOICE_INTERACTION",
        "BIND_VPN_SERVICE",
        "BIND_WALLPAPER",
        "CLEAR_APP_CACHE",
        "EXPAND_STATUS_BAR",
        "INSTALL_SHORTCUT",
        "UNINSTALL_SHORTCUT",
        "KILL_BACKGROUND_PROCESSES",
        "MANAGE_DOCUMENTS",
        "READ_LOGS",
        "SET_ALARM",
        "SET_ALWAYS_FINISH",
        "SET_ANIMATION_SCALE",
        "SET_DEBUG_APP",
        "SET_PROCESS_LIMIT",
        "SET_TIME_ZONE",
        "SET_WALLPAPER",
        "SET_WALLPAPER_HINTS",
        "SET_PREFERRED_APPLICATIONS",
        "SIGNAL_PERSISTENT_PROCESSES",
        "UPDATE_DEVICE_STATS",
        "USE_FINGERPRINT",
        "USE_BIOMETRIC",
        "USE_FULL_SCREEN_INTENT",
        "WRITE_APN_SETTINGS",
        "WRITE_SECURE_SETTINGS",
        "WRITE_SETTINGS",
        "ACCESS_MOCK_LOCATION",
        "INSTALL_PACKAGES",
        "DELETE_PACKAGES",
        "REQUEST_INSTALL_PACKAGES",
        "PACKAGE_USAGE_STATS",
        "REQUEST_IGNORE_BATTERY_OPTIMIZATIONS",
        "READ_PRIVILEGED_PHONE_STATE",
        "ANSWER_PHONE_CALLS",
        "READ_PHONE_NUMBERS",
        "FOREGROUND_SERVICE",
        "MANAGE_OWN_CALLS",
        "READ_VOICEMAIL",
        "WRITE_VOICEMAIL",
        "USE_SIP",
        "ACCESS_BACKGROUND_LOCATION",
        "ACTIVITY_RECOGNITION",
        "ACCESS_MEDIA_LOCATION",
        "ACCEPT_HANDOVER",
        "ACCESS_BLUETOOTH_SHARE",
        "BIND_AUTOFILL_SERVICE",
        "BIND_COMPANION_DEVICE_MANAGER",
        "BIND_CALL_SCREENING_SERVICE",
        "BIND_CARRIER_SERVICES",
        "BIND_CHOOSER_TARGET_SERVICE",
        "BIND_CONDITION_PROVIDER_SERVICE",
        "BIND_CARRIER_MESSAGING_SERVICE",
        "BIND_INCALL_SERVICE",
        "BIND_JOB_SERVICE",
        "BIND_MEDIA_BROWSER_SERVICE",
        "BIND_MIDI_DEVICE_SERVICE",
        "BIND_NOTIFICATION_LISTENER_SERVICE",
        "BIND_PRINT_SPOOLER_SERVICE",
        "BIND_QUICK_SETTINGS_TILE",
        "BIND_SCREENING_SERVICE",
        "BIND_TELECOM_CONNECTION_SERVICE",
        "BIND_TELEPHONY_SUBSCRIPTION_SERVICE",
        "BIND_TV_INPUT",
        "BIND_VISUAL_VOICEMAIL_SERVICE",
        "BIND_WALLPAPER",
        "BIND_WIFI_P2P_SERVICE",
        "CALL_COMPANION_APP",
        "CAPTURE_AUDIO_OUTPUT",
        "CAPTURE_SECURE_VIDEO_OUTPUT",
        "CAPTURE_VIDEO_OUTPUT",
        "CHANGE_APP_IDLE_STATE",
        "CONTROL_INCALL_EXPERIENCE",
        "DEVICE_POWER",
        "GET_ACCOUNTS_PRIVILEGED",
        "MANAGE_IPSEC_TUNNELS",
        "MODIFY_PHONE_STATE",
        "MANAGE_ACTIVITY_STACKS",
        "MODIFY_AUDIO_ROUTING",
        "MODIFY_PARENTAL_CONTROLS",
        "MONITOR_LOCATION",
        "NEARBY_WIFI_DEVICES",
        "NETWORK_SETTINGS",
        "READ_SEARCH_INDEXABLES",
        "READ_PRECISE_PHONE_STATE",
        "READ_NETWORK_USAGE_HISTORY",
        "READ_OEM_UNLOCK_STATE",
        "READ_USER_DICTIONARY",
        "RESET_PASSWORD",
        "SEND_RESPOND_VIA_MESSAGE",
        "SET_PACKAGE_VERIFICATION",
        "START_ACTIVITIES_FROM_BACKGROUND",
        "START_CALL_SERVICE",
        "START_TASKS_FROM_RECENTS",
        "STATUS_BAR",
        "SYSTEM_ALERT_WINDOW",
        "TRANSMIT_IR",
        "TRUST_LISTENER",
        "UNLIMITED_SHORTCUTS_API_CALLS",
        "UPDATE_APP_OPS_STATS",
        "USE_CREDENTIALS",
        "USE_FINGERPRINT",
        "VIBRATE",
        "WRITE_APN_SETTINGS",
        "WRITE_MEDIA_STORAGE",
        "WRITE_USER_DICTIONARY",
        "BIND_NOTIFICATION_ASSISTANT_SERVICE",
        "READ_CALENDAR",
        "WRITE_CALENDAR",
        "BLUETOOTH",
        "CHANGE_WIFI_STATE",
        "READ_SYNC_STATS",
        "SET_TIME",
        "ACCESS_LOCATION_EXTRA_COMMANDS",
        "GET_PACKAGE_SIZE",
        "UPDATE_DEVICE_STATS",
        "MOUNT_FORMAT_FILESYSTEMS",
        "MOUNT_UNMOUNT_FILESYSTEMS",
        "PERSISTENT_ACTIVITY",
        "CHANGE_CONFIGURATION",
        "WRITE_USER_DICTIONARY",
        "DUMP",
        "READ_INPUT_STATE",
        "READ_SOCIAL_STREAM",
        "WRITE_SOCIAL_STREAM",
        "BATTERY_STATS",
        "BROADCAST_PACKAGE_REMOVED",
        "BROADCAST_SMS",
        "BROADCAST_STICKY",
        "BROADCAST_WAP_PUSH",
        "READ_PROFILE",
        "WRITE_PROFILE",
        "CALL_PRIVILEGED",
        "CLEAR_APP_CACHE",
        "DIAGNOSTIC",
        "FLASHLIGHT",
        "GLOBAL_SEARCH",
        "HARDWARE_TEST",
        "INJECT_EVENTS",
        "MANAGE_ACCOUNTS",
        "MANAGE_APP_TOKENS",
        "READ_FRAME_BUFFER",
        "RECEIVE_DATA_ACTIVITY_CHANGE",
        "REBOOT",
        "SET_ORIENTATION",
        "SET_POINTER_SPEED",
        "SHUTDOWN",
        "SIGNAL_PERSISTENT_PROCESSES",
        "STATUS_BAR_SERVICE",
        "SUBSCRIBED_FEEDS_READ",
        "SUBSCRIBED_FEEDS_WRITE"
        ]
    
    csv_file_path = 'csv\\permission.csv'


    result = check_permissions(mnf_file_path, permissions_to_check)
    # print_result(permissions_to_check, result)
    write_to_csv(permissions_to_check, result, csv_file_path,sha256)
    print("csv save: ",csv_file_path)


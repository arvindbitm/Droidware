# # import pandas as pd
# # import numpy as np
# # import os


# # dataste = ["function_call_graph.csv","java_keyword.csv","permission.csv"]

# # fcg_selected_feature = [
# #     "sha256",
# #     "access_network_state_occurrences",
# #     "access_fine_location_occurrences",
# #     "access_fine_location_call_count",
# #     "access_coarse_location_occurrences",
# #     "change_network_state_occurrences",
# #     "change_network_state_call_count",
# #     "internet_occurrences",
# #     "read_phone_state_occurrences",
# #     "read_contacts_occurrences",
# #     "write_contacts_occurrences",
# #     "read_sms_occurrences",
# #     "read_sms_call_count",
# #     "send_sms_occurrences",
# #     "send_sms_call_count",
# #     "receive_sms_occurrences",
# #     "read_external_storage_occurrences",
# #     "read_external_storage_call_count",
# #     "write_external_storage_occurrences",
# #     "write_external_storage_call_count",
# #     "bluetooth_occurrences",
# #     "bluetooth_call_count",
# #     "record_audio_occurrences",
# #     "record_audio_call_count",
# #     "camera_occurrences",
# #     "camera_call_count",
# #     "getsystemservice_occurrences",
# #     "getsystemservice_call_count",
# #     "getdeviceid_occurrences",
# #     "getdeviceid_call_count",
# #     "getsubscriberid_occurrences",
# #     "getsubscriberid_call_count",
# #     "getsimserialnumber_occurrences",
# #     "getsimserialnumber_call_count",
# #     "getline1number_occurrences",
# #     "getline1number_call_count",
# #     "exec_occurrences",
# #     "exec_call_count",
# #     "openconnection_occurrences",
# #     "openconnection_call_count",
# #     "fileoutputstream_occurrences",
# #     "fileoutputstream_call_count",
# #     "delete_occurrences",
# #     "delete_call_count",
# #     "mkdir_occurrences",
# #     "mkdir_call_count",
# #     "sendtextmessage_occurrences",
# #     "sendtextmessage_call_count",
# #     "startactivity_occurrences",
# #     "startactivity_call_count",
# #     "startservice_occurrences"
# # ]

# # java_selected_feature = [
# #     "sha256",
# #     "total java file",
# #     "findsecbugs",
# #     "oauth2",
# #     "javax.net.ssl.sslsocket",
# #     "regulatory compliance",
# #     "code injection",
# #     "scribejava",
# #     "java.security.provider",
# #     "cron job",
# #     "content security policy",
# #     "heap dump",
# #     "java.lang.reflect.method",
# #     "disaster recovery",
# #     "zero trust",
# #     "java.net.url",
# #     "java.util.concurrent.scheduledthreadpoolexecutor",
# #     "veracode",
# #     "java.nio.file.standardopenoption",
# #     "javax.crypto.keygenerator",
# #     "javax.security.auth.callback.callback",
# #     "java.nio.channels.socketchannel",
# #     "keylogger",
# #     "advanced techniques",
# #     "fake profile",
# #     "bcrypt",
# #     "java.security.domaincombiner",
# #     "phpstan",
# #     "argon2",
# #     "wireshark",
# #     "java.net.httpurlconnection",
# #     "java.security.unresolvedpermission",
# #     "security framework",
# #     "data loss prevention (dlp)",
# #     "java.util.jar.jarfile",
# #     "java.util.jar.jarentry",
# #     "@inherited",
# #     "pepper",
# #     "root exploit",
# #     "spring security",
# #     "digital signatures",
# #     "data breach",
# #     "csrf protection",
# #     "system analysis",
# #     "logmein",
# #     "security testing",
# #     "data privacy",
# #     "logic bomb",
# #     "social engineering",
# #     "keystore",
# #     "active directory"
# # ]

# # permission_selected_feature =  [
# #     "sha256",
# #     "write_calendar",
# #     "camera",
# #     "read_contacts",
# #     "write_contacts",
# #     "get_accounts",
# #     "access_fine_location",
# #     "access_coarse_location",
# #     "record_audio",
# #     "read_phone_state",
# #     "call_phone",
# #     "read_call_log",
# #     "write_call_log",
# #     "add_voicemail",
# #     "use_sip",
# #     "process_outgoing_calls",
# #     "body_sensors",
# #     "send_sms",
# #     "receive_sms",
# #     "read_sms",
# #     "receive_wap_push",
# #     "receive_mms",
# #     "read_external_storage",
# #     "write_external_storage",
# #     "internet",
# #     "bluetooth",
# #     "bluetooth_admin",
# #     "access_wifi_state",
# #     "change_wifi_state",
# #     "access_network_state",
# #     "change_network_state",
# # ]

# # output_path = ["selected_csv/selected_features_dataset_of_fcg","selected_csv/selected_features_dataset_of_java","selected_csv/selected_features_dataset_of_permission"]
# # os.makedirs("selected_csv", exist_ok=True)
# # for i in dataste:
# #     path_of_csv = os.path.join("csv",i)

# #     print(path_of_csv)
# #     if i == dataste[0]:
# #         data = pd.read_csv(path_of_csv, usecols=fcg_selected_feature)
# #         data.to_csv(output_path[0] + ".csv", index=False)
# #     elif i == dataste[1]:
# #         data = pd.read_csv(path_of_csv, usecols=java_selected_feature)
# #         data.to_csv(output_path[1] + ".csv", index=False)
# #     elif i == dataste[2]:
# #         data = pd.read_csv(path_of_csv, usecols=permission_selected_feature)
# #         data.to_csv(output_path[2] + ".csv", index=False)
# #     # print(data.head(5))



# # # Mapping datasets to features and output paths
# # # feature_mapping = {
# # #     dataste[0]: (fcg_selected_feature, "selected_csv/selected_features_dataset_of_fcg.csv"),
# # #     dataste[1]: (java_selected_feature, "selected_csv/selected_features_dataset_of_java.csv"),
# # #     dataste[2]: (permission_selected_feature, "selected_csv/selected_features_dataset_of_permission.csv"),
# # # }

# # # # Ensure output directory exists
# # # os.makedirs("selected_csv", exist_ok=True)

# # # # Process each dataset
# # # for dataset, (features, output_path) in feature_mapping.items():
# # #     input_path = os.path.join("csv", dataset)
# # #     if os.path.exists(input_path):
# # #         data = pd.read_csv(input_path, usecols=features)
# # #         data.to_csv(output_path, index=False)
# # #         print(f"Processed: {dataset} -> {output_path}")
# # #     else:
# # #         print(f"File not found: {input_path}")



# # # import pandas as pd
# # # import os

# # # Assuming 'dir_of_csv' is a list of directories containing the CSV files
# # # dir_of_csv = ["directory1", "directory2", "directory3"]  # Replace with actual directory names

# # output_path = 'Droidware_client.csv'

# # dir_of_csv = ["selected_features_dataset_of_fcg.csv","selected_features_dataset_of_java.csv", "selected_features_dataset_of_permission.csv" ]

# # for i in range(0,3):
# #     dir_of_csv[0]= os.path.join("selected_csv",dir_of_csv[0])

# # for i in range(0,1):
# #     # Load each CSV file in the directory
# #     # java = os.path.join(i, 'java_keyword.csv')
# #     df_java = pd.read_csv(dir_of_csv[1])
    
# #     # fcg = os.path.join(i, 'function_call_graph.csv')
# #     df_fcg = pd.read_csv(dir_of_csv[0])
    
# #     # permission = os.path.join(i, 'permission.csv')
# #     df_permission = pd.read_csv(dir_of_csv[2])

# #     # Standardize column names by making them lowercase and stripping whitespace
# #     df_java.columns = df_java.columns.str.lower().str.strip()
# #     df_fcg.columns = df_fcg.columns.str.lower().str.strip()
# #     df_permission.columns = df_permission.columns.str.lower().str.strip()

# #     # Check if 'sha256' exists in each DataFrame
# #     if 'sha256' not in df_java.columns:
# #         print(f"'sha256' column not found in java_keyword.csv in directory: {i}")
# #         continue
# #     if 'sha256' not in df_fcg.columns:
# #         print(f"'sha256' column not found in function_call_graph.csv in directory: {i}")
# #         continue
# #     if 'sha256' not in df_permission.columns:
# #         print(f"'sha256' column not found in permission.csv in directory: {i}")
# #         continue

# #     # Merge df_java and df_fcg on the common 'sha256' column
# #     merged_df = pd.merge(df_java, df_fcg, on='sha256', how='inner')
    
# #     # Then merge the resulting dataframe with df_permission
# #     final_merged_df = pd.merge(merged_df, df_permission, on='sha256', how='inner')

# #     # Remove duplicate rows in final_merged_df
# #     final_merged_df.drop_duplicates(inplace=True)

# #     # If the merged dataset exists, filter out rows that already exist in it based on 'sha256'
# #     if os.path.exists(output_path):
# #         # Load only the 'sha256' column to avoid loading the full dataset
# #         existing_sha256 = pd.read_csv(output_path, usecols=['sha256'])

# #         # Keep only new rows that don’t have a matching 'sha256' in the existing dataset
# #         final_merged_df = final_merged_df[~final_merged_df['sha256'].isin(existing_sha256['sha256'])]

# #     # Append only the new rows to the output file
# #     if not final_merged_df.empty:  # Check if there’s any new data to append
# #         final_merged_df.to_csv(output_path, mode='a', index=False, header=not os.path.exists(output_path))
# #         print(f"Appended new data to: {output_path}")
# #     else:
# #         print("No new data to append.")
# import pandas as pd
# import os

# # Datasets and selected features
# datasets = ["function_call_graph.csv", "java_keyword.csv", "permission.csv"]

# fcg_selected_feature = [
#     "sha256",
#     "access_network_state_occurrences",
#     "access_fine_location_occurrences",
#     "access_fine_location_call_count",
#     "access_coarse_location_occurrences",
#     "change_network_state_occurrences",
#     "change_network_state_call_count",
#     "internet_occurrences",
#     "read_phone_state_occurrences",
#     "read_contacts_occurrences",
#     "write_contacts_occurrences",
#     "read_sms_occurrences",
#     "read_sms_call_count",
#     "send_sms_occurrences",
#     "send_sms_call_count",
#     "receive_sms_occurrences",
#     "read_external_storage_occurrences",
#     "read_external_storage_call_count",
#     "write_external_storage_occurrences",
#     "write_external_storage_call_count",
#     "bluetooth_occurrences",
#     "bluetooth_call_count",
#     "record_audio_occurrences",
#     "record_audio_call_count",
#     "camera_occurrences",
#     "camera_call_count",
#     "getsystemservice_occurrences",
#     "getsystemservice_call_count",
#     "getdeviceid_occurrences",
#     "getdeviceid_call_count",
#     "getsubscriberid_occurrences",
#     "getsubscriberid_call_count",
#     "getsimserialnumber_occurrences",
#     "getsimserialnumber_call_count",
#     "getline1number_occurrences",
#     "getline1number_call_count",
#     "exec_occurrences",
#     "exec_call_count",
#     "openconnection_occurrences",
#     "openconnection_call_count",
#     "fileoutputstream_occurrences",
#     "fileoutputstream_call_count",
#     "delete_occurrences",
#     "delete_call_count",
#     "mkdir_occurrences",
#     "mkdir_call_count",
#     "sendtextmessage_occurrences",
#     "sendtextmessage_call_count",
#     "startactivity_occurrences",
#     "startactivity_call_count",
#     "startservice_occurrences",
# ]

# java_selected_feature = [
#     "sha256",
#     "total java file",
#     "findsecbugs",
#     "oauth2",
#     "javax.net.ssl.sslsocket",
#     "regulatory compliance",
#     "code injection",
#     "scribejava",
#     "java.security.provider",
#     "cron job",
#     "content security policy",
#     "heap dump",
#     "java.lang.reflect.method",
#     "disaster recovery",
#     "zero trust",
#     "java.net.url",
#     "java.util.concurrent.scheduledthreadpoolexecutor",
#     "veracode",
#     "java.nio.file.standardopenoption",
#     "javax.crypto.keygenerator",
#     "javax.security.auth.callback.callback",
#     "java.nio.channels.socketchannel",
#     "keylogger",
#     "advanced techniques",
#     "fake profile",
#     "bcrypt",
#     "java.security.domaincombiner",
#     "phpstan",
#     "argon2",
#     "wireshark",
#     "java.net.httpurlconnection",
#     "java.security.unresolvedpermission",
#     "security framework",
#     "data loss prevention (dlp)",
#     "java.util.jar.jarfile",
#     "java.util.jar.jarentry",
#     "@inherited",
#     "pepper",
#     "root exploit",
#     "spring security",
#     "digital signatures",
#     "data breach",
#     "csrf protection",
#     "system analysis",
#     "logmein",
#     "security testing",
#     "data privacy",
#     "logic bomb",
#     "social engineering",
#     "keystore",
#     "active directory",
# ]

# permission_selected_feature = [
#     "sha256",
#     "write_calendar",
#     "camera",
#     "read_contacts",
#     "write_contacts",
#     "get_accounts",
#     "access_fine_location",
#     "access_coarse_location",
#     "record_audio",
#     "read_phone_state",
#     "call_phone",
#     "read_call_log",
#     "write_call_log",
#     "add_voicemail",
#     "use_sip",
#     "process_outgoing_calls",
#     "body_sensors",
#     "send_sms",
#     "receive_sms",
#     "read_sms",
#     "receive_wap_push",
#     "receive_mms",
#     "read_external_storage",
#     "write_external_storage",
#     "internet",
#     "bluetooth",
#     "bluetooth_admin",
#     "access_wifi_state",
#     "change_wifi_state",
#     "access_network_state",
#     "change_network_state",
# ]

# selected_features = [fcg_selected_feature, java_selected_feature, permission_selected_feature]
# output_paths = [
#     "selected_csv/selected_features_dataset_of_fcg.csv",
#     "selected_csv/selected_features_dataset_of_java.csv",
#     "selected_csv/selected_features_dataset_of_permission.csv",
# ]

# # Ensure output directory exists
# os.makedirs("selected_csv", exist_ok=True)

# # Process each dataset
# for dataset, features, output_path in zip(datasets, selected_features, output_paths):
#     input_path = os.path.join("csv", dataset)
#     if os.path.exists(input_path):
#         # Load columns dynamically
#         available_columns = pd.read_csv(input_path, nrows=0).columns
#         valid_features = [col for col in features if col in available_columns]
        
#         if valid_features:
#             data = pd.read_csv(input_path, usecols=valid_features)
#             data.to_csv(output_path, index=False)
#             print(f"Processed: {dataset} -> {output_path}")
#         else:
#             print(f"No matching columns found in {dataset}")
#     else:
#         print(f"File not found: {input_path}")
import pandas as pd
import os
from logging_config import get_logger
logger = get_logger(__name__)
logger.info("module_loaded")

# Datasets and selected features
datasets = ["function_call_graph.csv", "java_keyword.csv", "permission.csv"]

# fcg_selected_feature = [
#     "sha256",
#     "access_network_state_occurrences",
#     "access_fine_location_occurrences",
#     "access_fine_location_call_count",
#     "access_coarse_location_occurrences",
#     "change_network_state_occurrences",
#     "change_network_state_call_count",
#     "internet_occurrences",
#     "read_phone_state_occurrences",
#     "read_contacts_occurrences",
#     "write_contacts_occurrences",
#     "read_sms_occurrences",
#     "read_sms_call_count",
#     "send_sms_occurrences",
#     "send_sms_call_count",
#     "receive_sms_occurrences",
#     "read_external_storage_occurrences",
#     "read_external_storage_call_count",
#     "write_external_storage_occurrences",
#     "write_external_storage_call_count",
#     "bluetooth_occurrences",
#     "bluetooth_call_count",
#     "record_audio_occurrences",
#     "record_audio_call_count",
#     "camera_occurrences",
#     "camera_call_count",
#     "getsystemservice_occurrences",
#     "getsystemservice_call_count",
#     "getdeviceid_occurrences",
#     "getdeviceid_call_count",
#     "getsubscriberid_occurrences",
#     "getsubscriberid_call_count",
#     "getsimserialnumber_occurrences",
#     "getsimserialnumber_call_count",
#     "getline1number_occurrences",
#     "getline1number_call_count",
#     "exec_occurrences",
#     "exec_call_count",
#     "openconnection_occurrences",
#     "openconnection_call_count",
#     "fileoutputstream_occurrences",
#     "fileoutputstream_call_count",
#     "delete_occurrences",
#     "delete_call_count",
#     "mkdir_occurrences",
#     "mkdir_call_count",
#     "sendtextmessage_occurrences",
#     "sendtextmessage_call_count",
#     "startactivity_occurrences",
#     "startactivity_call_count",
#     "startservice_occurrences",
# ]

# java_selected_feature = [
#     "sha256",
#     "total java file",
#     "findsecbugs",
#     "oauth2",
#     "javax.net.ssl.sslsocket",
#     "regulatory compliance",
#     "code injection",
#     "scribejava",
#     "java.security.provider",
#     "cron job",
#     "content security policy",
#     "heap dump",
#     "java.lang.reflect.method",
#     "disaster recovery",
#     "zero trust",
#     "java.net.url",
#     "java.util.concurrent.scheduledthreadpoolexecutor",
#     "veracode",
#     "java.nio.file.standardopenoption",
#     "javax.crypto.keygenerator",
#     "javax.security.auth.callback.callback",
#     "java.nio.channels.socketchannel",
#     "keylogger",
#     "advanced techniques",
#     "fake profile",
#     "bcrypt",
#     "java.security.domaincombiner",
#     "phpstan",
#     "argon2",
#     "wireshark",
#     "java.net.httpurlconnection",
#     "java.security.unresolvedpermission",
#     "security framework",
#     "data loss prevention (dlp)",
#     "java.util.jar.jarfile",
#     "java.util.jar.jarentry",
#     "@inherited",
#     "pepper",
#     "root exploit",
#     "spring security",
#     "digital signatures",
#     "data breach",
#     "csrf protection",
#     "system analysis",
#     "logmein",
#     "security testing",
#     "data privacy",
#     "logic bomb",
#     "social engineering",
#     "keystore",
#     "active directory",
# ]

# permission_selected_feature = [
#     "sha256",
#     "write_calendar",
#     "camera",
#     "read_contacts",
#     "write_contacts",
#     "get_accounts",
#     "access_fine_location",
#     "access_coarse_location",
#     "record_audio",
#     "read_phone_state",
#     "call_phone",
#     "read_call_log",
#     "write_call_log",
#     "add_voicemail",
#     "use_sip",
#     "process_outgoing_calls",
#     "body_sensors",
#     "send_sms",
#     "receive_sms",
#     "read_sms",
#     "receive_wap_push",
#     "receive_mms",
#     "read_external_storage",
#     "write_external_storage",
#     "internet",
#     "bluetooth",
#     "bluetooth_admin",
#     "access_wifi_state",
#     "change_wifi_state",
#     "access_network_state",
#     "change_network_state",
# ]


fcg_selected_feature = [
    "sha256",
    "access_network_state_occurrences",
    "access_fine_location_occurrences",
    "access_fine_location_call_count",
    "access_coarse_location_occurrences",
    "change_network_state_occurrences",
    "change_network_state_call_count",
    "internet_occurrences",
    "read_phone_state_occurrences",
    "read_contacts_occurrences",
    "write_contacts_occurrences",
    "read_sms_occurrences",
    "read_sms_call_count",
    "send_sms_occurrences",
    "send_sms_call_count",
    "receive_sms_occurrences",
    "read_external_storage_occurrences",
    "read_external_storage_call_count",
    "write_external_storage_occurrences",
    "write_external_storage_call_count",
    "bluetooth_occurrences",
    "bluetooth_call_count",
    "record_audio_occurrences",
    "record_audio_call_count",
    "camera_occurrences",
    "camera_call_count",
    "getsystemservice_occurrences",
    "getsystemservice_call_count",
    "getdeviceid_occurrences",
    "getdeviceid_call_count",
    "getsubscriberid_occurrences",
    "getsubscriberid_call_count",
    "getsimserialnumber_occurrences",
    "getsimserialnumber_call_count",
    "getline1number_occurrences",
    "getline1number_call_count",
    "exec_occurrences",
    "exec_call_count",
    "openconnection_occurrences",
    "openconnection_call_count",
    "fileoutputstream_occurrences",
    "fileoutputstream_call_count",
    "delete_occurrences",
    "delete_call_count",
    "mkdir_occurrences",
    "mkdir_call_count",
    "sendtextmessage_occurrences",
    "sendtextmessage_call_count",
    "startactivity_occurrences",
    "startactivity_call_count",
    "startservice_occurrences"
]

java_selected_feature = [
    "sha256",
    "total java file",
    "findsecbugs",
    "oauth2",
    "javax.net.ssl.sslsocket",
    "regulatory compliance",
    "code injection",
    "scribejava",
    "java.security.provider",
    "cron job",
    "content security policy",
    "heap dump",
    "java.lang.reflect.method",
    "disaster recovery",
    "zero trust",
    "java.net.url",
    "java.util.concurrent.scheduledthreadpoolexecutor",
    "veracode",
    "java.nio.file.standardopenoption",
    "javax.crypto.keygenerator",
    "javax.security.auth.callback.callback",
    "java.nio.channels.socketchannel",
    "keylogger",
    "advanced techniques",
    "fake profile",
    "bcrypt",
    "java.security.domaincombiner",
    "phpstan",
    "argon2",
    "wireshark",
    "java.net.httpurlconnection",
    "java.security.unresolvedpermission",
    "security framework",
    "data loss prevention (dlp)",
    "java.util.jar.jarfile",
    "java.util.jar.jarentry",
    "@inherited",
    "pepper",
    "root exploit",
    "spring security",
    "digital signatures",
    "data breach",
    "csrf protection",
    "system analysis",
    "logmein",
    "security testing",
    "data privacy",
    "logic bomb",
    "social engineering",
    "keystore",
    "active directory"
]

permission_selected_feature =  [
    "sha256",
    "write_calendar",
    "camera",
    "read_contacts",
    "write_contacts",
    "get_accounts",
    "access_fine_location",
    "access_coarse_location",
    "record_audio",
    "read_phone_state",
    "call_phone",
    "read_call_log",
    "write_call_log",
    "add_voicemail",
    "use_sip",
    "process_outgoing_calls",
    "body_sensors",
    "send_sms",
    "receive_sms",
    "read_sms",
    "receive_wap_push",
    "receive_mms",
    "read_external_storage",
    "write_external_storage",
    "internet",
    "bluetooth",
    "bluetooth_admin",
    "access_wifi_state",
    "change_wifi_state",
    "access_network_state",
    "change_network_state"

]


selected_features = [fcg_selected_feature, java_selected_feature, permission_selected_feature]
output_paths = [
    "selected_csv/selected_features_dataset_of_fcg.csv",
    "selected_csv/selected_features_dataset_of_java.csv",
    "selected_csv/selected_features_dataset_of_permission.csv",
]

# Ensure output directory exists
os.makedirs("selected_csv", exist_ok=True)

# Process each dataset
processed_data = []
for dataset, features, output_path in zip(datasets, selected_features, output_paths):
    input_path = os.path.join("csv", dataset)
    if os.path.exists(input_path):
        # Load columns dynamically
        available_columns = pd.read_csv(input_path, nrows=0).columns.str.lower().str.strip()
        features_lower = [col.lower() for col in features]
        valid_features = [col for col in features_lower if col in available_columns]

        if valid_features:
            data = pd.read_csv(input_path, usecols=available_columns)
            data.columns = available_columns  # Standardize column names
            data = data[[col for col in available_columns if col in valid_features]]
            data.to_csv(output_path, index=False)
            processed_data.append(data)
            print(f"Processed: {dataset} -> {output_path}")
        else:
            print(f"No matching columns found in {dataset}")
    else:
        print(f"File not found: {input_path}")

# Combine all datasets on 'sha256'
if len(processed_data) == 3:
    # Debugging: Check columns before merging
    for idx, data in enumerate(processed_data):
        print(f"Columns in dataset {idx}: {list(data.columns)}")

    # Normalize 'sha256' column names for merging
    for i, data in enumerate(processed_data):
        data.columns = data.columns.str.lower().str.strip()  # Normalize column names
        if "sha256" not in data.columns:
            raise ValueError(f"'sha256' column is missing in dataset {datasets[i]}")

    combined_data = processed_data[0]
    for data in processed_data[1:]:
        combined_data = pd.merge(combined_data, data, on="sha256", how="inner")

    # Save the combined dataset
    combined_output_path = "selected_csv/combined_selected_features.csv"
    combined_data.to_csv(combined_output_path, index=False)
    print(f"Combined dataset saved to {combined_output_path}")
else:
    print("Not all datasets were processed successfully. Combined dataset not created.")
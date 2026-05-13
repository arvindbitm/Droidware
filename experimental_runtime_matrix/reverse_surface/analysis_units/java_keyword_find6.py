import os
import csv
from tqdm import tqdm
import threading
from queue import Queue
from datetime import datetime
import pandas as pd
import csv
from collections import Counter
from multiprocessing import Pool, Manager, cpu_count
from threading import Thread
import psutil
import win32api # type: ignore
import win32process # type: ignore
import win32con # type: ignore
# import cupy as cp  # Importing CuPy for GPU processing


def set_high_priority():
    """Set the current process to real-time priority."""
    # #    # Get current process
    # # p = psutil.Process(os.getpid())
    
    # # # Set priority to high
    # # p.nice(psutil.REALTIME_PRIORITY_CLASS)
    
    # # Alternatively, use win32api to set priority
    # handle = win32api.GetCurrentProcess()
    # win32process.SetPriorityClass(handle, win32process.REALTIME_PRIORITY_CLASS)
    try:
        # Get the current process handle
        handle = win32api.GetCurrentProcess()

        # Set the process priority to real-time
        win32process.SetPriorityClass(handle, win32process.REALTIME_PRIORITY_CLASS)

        # print("Process priority set to real-time.")
    
    except Exception as e:
        print(f"Failed to set process priority: {e}")
    


# Define the keywords to search for
keywords = [
    "FindSecBugs",
    "OAuth2",
    "javax.net.ssl.SSLSocket",
    "Regulatory Compliance",
    "Code Injection",
    "ScribeJava",
    "java.security.Provider",
    "Cron Job",
    "Content Security Policy",
    "Anti-Debugging",
    "java.lang.instrument.Instrumentation.isRedefineClassesSupported()",
    "Heap Dump",
    "Pretexting",
    "Credential Stuffing",
    "Self-Modification",
    "Key Derivation Functions (KDF)",
    "Covert Storage",
    "java.lang.reflect.Method",
    "Blockchain Security",
    "Security Operations Center (SOC)",
    "Public Key Infrastructure (PKI)",
    "SCADA Security",
    "Disaster Recovery",
    "Zero Trust",
    "java.net.URL",
    "java.util.concurrent.ScheduledThreadPoolExecutor",
    "Veracode",
    "java.nio.file.StandardOpenOption",
    "javax.crypto.KeyGenerator",
    "javax.security.auth.callback.Callback",
    "java.nio.channels.SocketChannel",
    "Keylogger",
    "Advanced Techniques",
    "Fake Profile",
    "Twofish Encryption",
    "java.lang.instrument.Instrumentation.appendToBootstrapClassLoaderSearch()",
    "BCrypt",
    "java.security.DomainCombiner",
    "Security Best Practices",
    "PHPStan",
    "Argon2",
    "Wireshark",
    "java.net.HttpURLConnection",
    "java.security.UnresolvedPermission",
    "Anti-VM",
    "Kube-hunter",
    "java.lang.instrument.Instrumentation.redefineClasses()",
    "Security Framework",
    "Power Analysis",
    "Data Loss Prevention (DLP)",
    "java.util.jar.JarFile",
    "Apache Camel",
    "java.util.jar.JarEntry",
    "java.lang.instrument.Instrumentation.retransformClasses()",
    "Interactive Application Security Testing (IAST)",
    "@Inherited",
    "Threat Modeling",
    "Pepper",
    "Side-Channel Attack",
    "Phishing Campaign",
    "Root Exploit",
    "Code Stomping",
    "Spring Security",
    "Discretionary Access Control (DAC)",
    "Digital Signatures",
    "Data Breach",
    "CSRF Protection",
    "Resilient Architecture",
    "System Analysis",
    "Decentralized Identity",
    "LogMeIn",
    "Security Testing",
    "System Hardening",
    "Data Privacy",
    "Heap Spray",
    "Logic Bomb",
    "Content Spoofing",
    "Social Engineering",
    "Keystore",
    "Active Directory",
    "SSL Pinning",
    "Memory Corruption",
    "Certificate Pinning",
    "Key Exchange",
    "Security Misconfiguration",
    "Domain Controller",
    "java.nio.file.Files",
    "Tamper Detection",
    "Forensics",
    "Cross-Site Scripting (XSS)",
    "Clickjacking",
    "java.nio.file.attribute.UserPrincipal",
    "java.net.http.HttpClient",
    "HTTP Strict Transport Security (HSTS)",
    "Common Weakness Enumeration (CWE)",
    "Keychain",
    "PCI-DSS",
    "Phishing",
    "Malware Analysis",
    "Risk Assessment",
    "java.nio.file.attribute.AclFileAttributeView",
    "Access Control",
    "java.nio.file.FileSystems",
    "Static Analysis",
    "java.nio.file.Paths",
    "java.nio.file.attribute.UserDefinedFileAttributeView",
    "java.nio.file.StandardCopyOption",
    "javax.security.auth.Subject",
    "Security Policy",
    "DDoS",
    "java.nio.file.LinkOption",
    "Penetration Testing",
    "Session Fixation",
    "java.nio.file.attribute.DosFileAttributeView",
    "java.nio.file.FileStore",
    "Incident Response",
    "java.net.URI",
    "java.security.Key",
    "java.nio.file.DirectoryStream",
    "Cryptanalysis",
    "Spyware",
    "Adware",
    "Security Monitoring",
    "java.net.DatagramPacket",
    "API Security",
    "java.security.KeyFactory",
    "Botnet",
    "Threat Intelligence",
    "Authentication",
    "java.nio.file.attribute.FileAttribute",
    "Man-in-the-Middle (MITM)",
    "Identity Theft",
    "Fraud Detection",
    "java.nio.file.attribute.FileTime",
    "VirusTotal",
    "java.nio.file.FileVisitResult",
    "Code Review",
    "java.net.ServerSocket",
    "java.security.cert.Certificate",
    "Eavesdropping",
    "Patch Management",
    "java.nio.file.OpenOption",
    "Security Awareness",
    "java.nio.file.AccessMode",
    "java.security.KeyPair",
    "java.nio.file.attribute.BasicFileAttributes",
    "Secure Coding",
    "Security Audit",
    "java.nio.file.SecureDirectoryStream",
    "CWE Top 25",
    "java.nio.file.StandardWatchEventKinds",
    "java.nio.file.CopyOption",
    "java.nio.file.attribute.FileOwnerAttributeView",
    "java.nio.file.attribute.PosixFileAttributes",
    "Trojan",
    "java.security.KeyStore",
    "java.net.Socket",
    "Cross-Site Request Forgery (CSRF)",
    "java.nio.file.attribute.GroupPrincipal",
    "java.security.cert.X509Certificate",
    "Injection Flaws",
    "java.nio.file.FileVisitOption",
    "java.nio.file.spi.FileTypeDetector",
    "java.net.InetAddress",
    "Zero-Day",
    "Mobile Device Management (MDM)",
    "java.security.Provider.Service",
    "java.nio.file.FileVisitResult.CONTINUE",
    "java.security.cert.CertificateFactory",
    "Code Obfuscation",
    "java.nio.file.WatchService",
    "java.nio.file.spi.FileSystemProvider.installedProviders()",
    "java.security.cert.CertificateEncodingException",
    "java.nio.file.StandardWatchEventKinds.ENTRY_MODIFY",
    "java.nio.file.StandardWatchEventKinds.ENTRY_CREATE",
    "java.nio.file.StandardWatchEventKinds.ENTRY_DELETE",
    "Threat Detection",
    "java.nio.file.StandardOpenOption.CREATE",
    "java.nio.file.StandardOpenOption.TRUNCATE_EXISTING",
    "Digital Forensics",
    "Endpoint Security",
    "java.nio.file.StandardOpenOption.READ",
    "java.nio.file.StandardOpenOption.WRITE",
    "Intrusion Detection System (IDS)",
    "java.nio.file.spi.FileSystemProvider.getFileAttributeView()",
    "java.nio.file.StandardOpenOption.APPEND",
    "java.security.cert.CertificateFactory.generateCertificate()",
    "java.nio.file.StandardOpenOption.DSYNC",
    "Cybersecurity",
    "java.security.cert.CertificateException",
    "java.security.cert.CertificateFactory.generateCertificates()",
    "java.nio.file.StandardOpenOption.SPARSE",
    "java.nio.file.attribute.AclFileAttributeView.setOwner()",
    "java.nio.file.StandardOpenOption.SYNC",
    "java.nio.file.attribute.BasicFileAttributeView.readAttributes()",
    "Security Incident",
    "java.nio.file.attribute.PosixFileAttributeView",
    "java.nio.file.StandardOpenOption.CREATE_NEW",
    "java.nio.file.StandardOpenOption.DELETE_ON_CLOSE",
    "java.nio.file.attribute.PosixFilePermissions",
    "Privilege Escalation",
    "Data Leakage",
    "Credential Theft",
    "Rootkit",
    "SSL Stripping",
    "Sandbox Evasion",
    "APK Repacking",
    "Malicious Advertising",
    "Dynamic Analysis",
    "Static Analysis",
    "Key Injection",
    "Fake System Update",
    "Overlay Attack",
    "Activity Hijacking",
    "Telephony Fraud",
    "Botnet Command and Control",
    "Malicious URL",
    "Drive-by Download",
    "In-App Billing Fraud",
    "Accessibility Abuse",
    "APK Signature Forgery",
    "Reflection Attack",
    "DexClassLoader",
    "SMiShing",
    "PackageManager",
    "Root Access",
    "SOCKS Proxy",
    "DNS Tunneling",
    "Content Provider Leakage",
    "ActivityManager",
    "Intent Sniffing",
    "SharedPreferences",
    "AccountManager",
    "BroadcastReceiver",
    "Custom Permission",
    "DexFile",
    "FragmentManager",
    "ContentResolver",
    "WebView Exploits",
    "Click Fraud",
    "SMSSend",
    "TelephonyManager",
    "IPC Abuse",
    "Binder",
    "Notification Hijacking",
    "DeviceAdmin",
    "Kernel Exploit",
    "System Property Manipulation",
    "Service Hijacking",
    "Network Traffic Analysis",
    "APK Decompiling",
    "Tamper Detection Bypass",
    "Frida",
    "Xposed",
    "Obfuscation Techniques",
    "DexProtector",
    "ProGuard",
    "Java Debug Wire Protocol (JDWP)",
    "JNI",
    "Native Code Injection",
    "Code Caves",
    "Stack Canaries",
    "ROP Gadgets",
    "Root Detection Bypass",
    "Anti-Emulation",
    "Code Packing",
    "Dalvik Executable",
    "Activity Lifecycle",
    "Service Lifecycle",
    "Broadcast Intent",
    "JobScheduler",
    "WorkManager",
    "ContentProvider",
    "NDK",
    "Dynamic Link Libraries (DLL)",
    "Symantec Mobile Insight",
    "Lookout",
    "Checkpoint Sandblast Mobile",
    "Cisco AMP for Endpoints",
    "McAfee MVISION Mobile",
    "Zimperium zIPS",
    "Wandera",
    "Better Mobile Threat Defense",
    "Pradeo",
    "MobileIron",
    "F5 Networks",
    "Ivanti Mobile Threat Defense",
    "Sophos Intercept X",
    "Trend Micro Mobile Security",
    "FireEye Mobile Threat Prevention",
    "ESET Endpoint Security",
    "Malwarebytes Endpoint Protection",
    "Bitdefender GravityZone",
    "Avast Mobile Security",
    "AVG Mobile Security",
    "Malware Patterns",
    "Heuristics Analysis",
    "Machine Learning in Malware Detection",
    "Behavioral Analysis",
    "Static Signature Analysis",
    "Memory Forensics",
    "ARM Architecture",
    "System Call Hooking",
    "Encryption Keys",
    "Reverse Engineering",
    "Malware Research Labs",
    "Incident Analysis",
    "API Hooking",
    "Packet Sniffing",
    "Key Exchange Algorithms",
    "Encryption Standards",
    "Threat Response",
    "Botnet Analysis",
    "SQL Injection",
    "Cross-Site Scripting",
    "Cross-Site Request Forgery",
    "Command Injection",
    "Path Traversal",
    "Insecure Deserialization",
    "Remote Code Execution",
    "Buffer Overflow",
    "Heap Overflow",
    "Integer Overflow",
    "Use-After-Free",
    "Format String Vulnerability",
    "Race Condition",
    "Timing Attack",
    "SSL/TLS Security",
    "DNS Security",
    "HTTP/2 Security",
    "OAuth2 Security",
    "API Security",
    "JSON Web Token (JWT)",
    "Token Binding",
    "Fuzz Testing",
    "Protocol Analysis",
    "Network Traffic Analysis",
    "Packet Analysis",
    "Network Intrusion Detection",
    "Network Intrusion Prevention",
    "Secure Network Design",
    "Firewall Management",
    "VPN Security",
    "Wireless Security",
    "Bluetooth Security",
    "NFC Security",
    "IoT Security",
    "Industrial Control Systems Security",
    "SCADA Security",
    "Endpoint Security",
    "Mobile Device Security",
    "BYOD Security",
    "MDM Solutions",
    "Mobile App Security",
    "App Store Security",
    "App Wrapping",
    "App Sandboxing",
    "App Hardening",
    "App Shielding",
    "Runtime Application Self-Protection",
    "App Security Testing",
    "App Security Review",
    "App Security Best Practices",
    "App Security Tools",
    "App Security Standards",
    "App Security Policies",
    "App Security Guidelines",
    "App Security Checklists",
    "App Security Training",
    "App Security Certification",
    "App Security Conferences",
    "App Security Webinars",
    "App Security Blogs",
    "App Security Forums",
    "App Security Communities",
    "App Security News",
    "App Security Research",
    "App Security Papers",
    "App Security Journals",
    "App Security Books",
    "App Security Courses",
    "App Security Tutorials",
    "App Security Workshops",
    "App Security Consulting",
    "App Security Services",
    "App Security Companies",
    "App Security Solutions",
    "App Security Products",
    "App Security Vendors",
    "App Security Providers",
    "App Security Platforms",
    "App Security Software",
    "App Security Systems",
    "App Security Devices",
    "App Security Appliances",
    "App Security Networks",
    "App Security Infrastructure",
    "App Security Architecture",
    "App Security Framework",
    "App Security Methodology",
    "App Security Process",
    "App Security Practice",
    "App Security Approach",
    "App Security Model",
    "App Security Strategy",
    "App Security Plan",
    "App Security Roadmap",
    "App Security Program",
    "App Security Initiative",
    "App Security Project",
    "App Security Effort",
    "App Security Campaign",
    "App Security Activity",
    "App Security Task",
    "App Security Action",
    "App Security Step",
    "App Security Measure",
    "App Security Procedure",
    "App Security Technique",
    "App Security Mechanism",
    "App Security Tool",
    "App Security Resource",
    "App Security Asset",
    "App Security Component",
    "App Security Element",
    "App Security Feature",
    "App Security Function",
    "App Security Role",
    "App Security Responsibility",
    "App Security Accountability",
    "App Security Authority",
    "App Security Ownership",
    "App Security Control",
    "App Security Governance",
    "App Security Risk Management",
    "App Security Incident Management",
    "App Security Compliance Management",
    "App Security Policy Management",
    "App Security Audit Management",
    "App Security Review Management",
    "App Security Testing Management",
    "App Security Monitoring Management",
    "App Security Reporting Management",
    "App Security Metrics Management",
    "App Security Dashboard",
    "App Security Scorecard",
    "App Security Benchmarking",
    "App Security Performance Management",
    "App Security Maturity Model",
    "App Security Capability Model",
    "App Security Assessment",
    "App Security Evaluation",
    "App Security Audit",
    "App Security Review",
    "App Security Analysis",
    "App Security Testing",
    "App Security Verification",
    "App Security Validation",
    "App Security Inspection",
    "App Security Investigation",
    "App Security Examination",
    "App Security Exploration",
    "App Security Discovery",
    "App Security Detection",
    "App Security Identification",
    "App Security Recognition",
    "App Security Classification",
    "App Security Categorization",
    "App Security Typing",
    "App Security Grouping",
    "App Security Sorting",
    "App Security Filtering",
    "App Security Matching",
    "App Security Correlation",
    "App Security Pattern",
    "App Security Signature",
    "App Security Profile",
    "App Security Behavior",
    "App Security Anomaly",
    "App Security Threat",
    "App Security Risk",
    "App Security Vulnerability",
    "App Security Exploit",
    "App Security Attack",
    "App Security Incident",
    "App Security Event",
    "App Security Alert",
    "App Security Notification",
    "App Security Warning",
    "App Security Advisory",
    "App Security Bulletin",
    "App Security Report",
    "App Security News",
    "App Security Update",
    "App Security Patch",
    "App Security Release",
    "App Security Fix"
]

keywords = [keyword.lower()for keyword in keywords]

def get_file_path(file_name):
    """Get the file path for a given file name."""
    base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, file_name)

def count_keywords_in_file(file_path, keywords):
    """Count the occurrences of each keyword in a given file."""

    # **Check if the file exists**
    if not os.path.isfile(file_path):
        print(f"File not found: {file_path}")
        return {keyword: 0 for keyword in keywords}  # **Return a count of 0 for all keywords**

    # **Check if the file is empty**
    if os.path.getsize(file_path) == 0:
        print(f"File is empty: {file_path}")
        return {keyword: 0 for keyword in keywords}  # **Return a count of 0 for all keywords**
    
    keyword_count = {keyword: 0 for keyword in keywords}
    
    with open(file_path, 'r', errors='ignore') as file:
        for line in file:
            # print(line)
            content = line.lower()
            for keyword in keywords:
                keyword_count[keyword] += content.count(keyword)
                # print(keyword)
        # content = file.read().lower()
        # for keyword in keywords:
        #     keyword_count[keyword] += content.count(keyword)
    
    return keyword_count

def count_java_file(directory_to_search):
    java_file_count = 0
    for root, dirs, files in os.walk(directory_to_search):
        for file in files:
            if file.endswith('.java'):
                java_file_count += 1

# Worker function for threading
def worker(file_path):
    # while not file_queue.empty():
    #     file_path = file_queue.get()
    #     keyword_count = count_keywords_in_file(file_path, keywords)
    #     keyword_count_queue.put(keyword_count)
    #     file_queue.task_done()
    set_high_priority()

    return  count_keywords_in_file(file_path, keywords)


def threaded_worker(file_queue, result_queue, keywords):
    """Thread worker function to process files in a queue."""
    set_high_priority()
    while not file_queue.empty():
        file_path = file_queue.get()
        result = count_keywords_in_file(file_path, keywords)
        result_queue.put(result)
        file_queue.task_done()

def process_files(files, keywords):
    """Process a list of files using threads."""
    set_high_priority()

    #  = args
    file_queue = Queue()
    result_queue = Queue()
    for file in files:
        file_queue.put(file)
    
    
    num_threads = min(16, len(files))  # You can adjust the number of threads per process
    threads = []
    for _ in range(num_threads):
        thread = Thread(target=threaded_worker, args=(file_queue, result_queue, keywords))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    total_counts = Counter()
    while not result_queue.empty():
        total_counts.update(result_queue.get())

    return total_counts

# def process_files(args):
#     files, keywords = args
#     total_counts = Counter()
#     for file in files:
#         total_counts.update(count_keywords_in_file(file, keywords))
#     return total_counts


def main(year_for_file,sha256):

    # Get current process
    p = psutil.Process(os.getpid())
    
    # Set priority to high
    p.nice(psutil.HIGH_PRIORITY_CLASS)
    
    # Alternatively, use win32api to set priority
    handle = win32api.GetCurrentProcess()
    win32process.SetPriorityClass(handle, win32process.REALTIME_PRIORITY_CLASS)
    
    
    
    java_file_name = 'JAVA'
    java_dir = get_file_path(java_file_name)
    year_for_file = str(year_for_file)
    sha256 = str(sha256)
    directory_to_search = os.path.join(java_dir, year_for_file, sha256)
    # print(directory_to_search)

    start_time = datetime.now()
    # print(f"\nStart time: {start_time}\n")


    # count_java = count_java_file(directory_to_search)
    # progressbar.reset(total = count_java)
    # time.sleep(1)


    # CSV output file
    csv_output_file = 'csv/java_keyword.csv'

    # total_counts = {keyword: 0 for keyword in keywords}
    total_counts = Counter({keyword: 0 for keyword in keywords})
    file_count = 0
    files_to_process = []
    # file_queue = Queue()
    # keyword_count_queue = Queue()

    # Traverse the directory and search for Java files
    for root, dirs, files in os.walk(directory_to_search):
        for file in files:
            if file.endswith('.java'):
                file_count += 1
                file_path = os.path.join(root, file)
                # keyword_count = count_keywords_in_file(file_path, keywords)
                # for keyword in keywords:
                #     total_counts[keyword] += keyword_count[keyword]
                # file_queue.put(file_path)
                files_to_process.append(file_path)
                

    # # Create and start threads
    # num_threads = min(64, file_queue.qsize())  # Reduce thread count if there aren't enough files
    # threads = []
    # for _ in range(num_threads):
    #     thread = threading.Thread(target=worker, args=(file_queue, keyword_count_queue))
    #     thread.start()
    #     threads.append(thread)

    # # Wait for all threads to finish
    # for thread in threads:
    #     thread.join()

    # Collect results from the queue
    # while not keyword_count_queue.empty():
    #     keyword_count = keyword_count_queue.get()
    #     for keyword in keywords:
    #         total_counts[keyword] += keyword_count[keyword]        
    
    # with Pool() as pool:
    #     results = pool.map(worker, files_to_process)
    
    # # Combine results from all processes
    # for result in results:
    #     total_counts.update(result)

    # Use multiprocessing Pool to process files in parallel

    # If no files to process, write zero counts to CSV
    if not files_to_process:
        print(f"No Java files found in: {directory_to_search}")
        file_count = '0'
        file_count = str(file_count)
    # Write the results to a CSV file
        file_exists = os.path.isfile(csv_output_file)
        with open(csv_output_file, 'a', newline='') as csvfile:
            fieldnames = ['Sha256', 'Total JAVA File'] + keywords
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()

            row_data = {'Sha256': sha256, 'Total JAVA File': file_count}
            row_data.update(total_counts)
            # row = [row_data[key] for key in fieldnames]
            # print(row_data)
            writer.writerow(row_data)
            # progress_bar.update(1)

        return

    count_of_cpu = cpu_count()
    num_processes = min(count_of_cpu-3, len(files_to_process))  # Adjust the number of processes

    if num_processes == 0:
        num_processes = 1

    
    chunk_size = len(files_to_process) // num_processes if num_processes > 0 else 1


    with Pool(processes=num_processes) as pool:
        results = pool.starmap(process_files, [(files_to_process[i:i + chunk_size], keywords) for i in range(0, len(files_to_process), chunk_size)])

    
    # Combine results from all processes
    for result in results:
        total_counts.update(result)
    
    file_count = str(file_count)
    # Write the results to a CSV file
    file_exists = os.path.isfile(csv_output_file)
    with open(csv_output_file, 'a', newline='') as csvfile:
        fieldnames = ['Sha256', 'Total JAVA File'] + keywords
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        
        row_data = {'Sha256': sha256, 'Total JAVA File': file_count}
        row_data.update(total_counts)
        # row = [row_data[key] for key in fieldnames]
        # print(row_data)
        writer.writerow(row_data)
        # progress_bar.update(1)

        # print(row_data)
    
    end_time = datetime.now()
    # print(f"End time: {end_time}")
    # print(f"Results have been written to {csv_output_file}")
    # print(f"Total execution time: {end_time - start_time}")



if __name__ == '__main__':
    
    year_for_file = '2024'

    df = pd.read_csv("2024.csv",sep=" ",usecols=[1],header=None)

    sha256 = df.values.flatten()
    print(sha256)
    count_sha = len(sha256)
    progress_bar = tqdm(total=count_sha, desc='Progress')
    start_time = datetime.now()
    for i in range(49,count_sha):
        filename = sha256[i]
        main(year_for_file,filename)
        progress_bar.update(1)

    end_time = datetime.now()
    print(f"Time taken: {end_time - start_time}")

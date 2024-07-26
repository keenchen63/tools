import paramiko
import openpyxl
from concurrent.futures import ThreadPoolExecutor
import re
import time
import ipaddress

# 连接设备的函数
def ssh_connect(hostname, username, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, username=username, password=password)
    return ssh

# 执行命令并打印回显的函数
def execute_and_print(channel, command):
    channel.send(command + '\n')
    time.sleep(2)  # 等待命令执行
    
    # 使用 recv 方法持续接收数据，直到命令执行完成
    output = ""
    while True:
        if channel.recv_ready():
            output += channel.recv(1024).decode('utf-8')
        if re.search(r'>|\$', output):  # 检查命令提示符，表示命令执行完成
            break
        time.sleep(0.1)
    
    print(f"Command: {command}\nOutput: {output}")
    return output

# 设置新密码的函数
def set_new_password(ssh, new_password):
    channel = ssh.invoke_shell()
    time.sleep(1)    
    # 读取初始输出
    output = channel.recv(9999).decode('utf-8')
    print(output)    
    # 发送新密码
    channel.send(new_password + '\n')
    time.sleep(2)
    output += channel.recv(1024).decode('utf-8')    
    print(output)
    # 发送确认密码
    channel.send(new_password + '\n')
    time.sleep(2)
    output += channel.recv(1024).decode('utf-8')    
    print(output)
    return output

# 获取设备SN号的函数
def get_sn(channel):
    channel.send("display system/system-info/esn\n")
    output = execute_and_print(channel, "display system/system-info/esn\n")
    
    sn_match = re.search(r'(215[0-9A-Za-z]{17})', output)

    if sn_match:
        print(f"The device SN is {sn_match}")
        return sn_match.group(1)
    else:
        print("SN not found in output")  # 打印未找到SN的调试信息
    return None

# 根据SN号在Excel文件中查找对应的IP地址
def find_ip_for_sn(sn, excel_file):
    workbook = openpyxl.load_workbook(excel_file)
    sheet = workbook.active
    for row in sheet.iter_rows(min_row=2, values_only=True):  # 假设第一行是标题
        sn_in_file, ip, gateway, mask = row
        if sn_in_file.strip().lower() == sn.strip().lower():
            return ip, gateway, mask
    return None, None, None

# 配置设备IP地址的函数
def configure_ip_address(channel, ip_address, ip_gateway, ip_mask):
    commands = [
        "diagnose ap-address address-mode mode static",
        f"diagnose ap-address ap-ipv4-address ipv4-address {ip_address} subnet-mask {ip_mask} gateway {ip_gateway}",
        "diagnose ap-address ac-ipv4-list",
        "ac-ip-list 172.31.161.240"
        "emit"
    ]
    for command in commands:
        execute_and_print(channel, command)    
    print(f"表格匹配IP为： {ip_address} / {ip_gateway} / {ip_mask}")
    print(execute_and_print(channel, "diagnose ap-address query-ap-address-info"))
    return None

def save_config(channel):
    commands = [
        "save"
        "y"
    ]
    for command in commands:
        execute_and_print(channel, command)
    return None

# 处理单个设备的函数
def process_device(ip, username, initial_password, new_password, excel_file):
    try:
        try:
            # 第一次使用初始密码连接
            ssh = ssh_connect(ip, username, initial_password)
            
            # 设置新密码
            print(f"Setting new password for device {ip}")
            set_new_password(ssh, new_password)
            
            # 由于设备会自动断开连接，等待一段时间再重新连接
            time.sleep(6)
                        #使用新密码重新连接
            ssh = ssh_connect(ip, username, new_password)
            channel = ssh.invoke_shell()
            
            # 获取设备的SN号
            sn = get_sn(channel)
            if sn:
                print(f"Device {ip} SN: {sn}")
                ip_address, ip_gateway, ip_mask = find_ip_for_sn(sn, excel_file)
                if ip_address:
                    print(f"Configuring IP Address: {ip_address} / {ip_gateway} / {ip_mask} for device {ip}")
                    configure_ip_address(channel, ip_address, ip_gateway, ip_mask)
                    ssh.close()

                    try:
                            
                        ssh = ssh_connect(ip_address, username, new_password)
                        channel = ssh.invoke_shell()

                        save_config(channel)
                    except Exception as e:
                        print(f"Failed to save config {ip}: {e}")

                else:
                    print(f"SN {sn} not found in Excel file for device {ip}.")
            else:
                print(f"Failed to get SN for device {ip}")
            
            ssh.close()

        except:

            #使用新密码重新连接
            ssh = ssh_connect(ip, username, new_password)
            channel = ssh.invoke_shell()
            
            # 获取设备的SN号
            sn = get_sn(channel)
            if sn:
                print(f"Device {ip} SN: {sn}")
                ip_address, ip_gateway, ip_mask = find_ip_for_sn(sn, excel_file)
                if ip_address:
                    print(f"Configuring IP Address: {ip_address} / {ip_gateway} / {ip_mask} for device {ip}")
                    configure_ip_address(channel, ip_address, ip_gateway, ip_mask)
                    ssh.close()

                    try:
                            
                        ssh = ssh_connect(ip_address, username, new_password)
                        channel = ssh.invoke_shell()

                        save_config(channel)
                    except Exception as e:
                        print(f"Failed to save config {ip}: {e}")

                else:
                    print(f"SN {sn} not found in Excel file for device {ip}.")
            else:
                print(f"Failed to get SN for device {ip}")
            
            ssh.close()
    except Exception as e:
        print(f"Failed to process device {ip}: {e}")

# 主函数
def main():
    username = "admin"
    initial_password = "admin@huawei.com"
    new_password = "Huawei@123"
    excel_file = "sn_ip_mapping.xlsx"
    ip_subnet = ipaddress.ip_network('192.168.1.196/32')    
    ip_base = "10.1.1."
    ip_range = range(1, 12)


    with ThreadPoolExecutor(max_workers=1) as executor:  # 根据需要调整工作线程数
        for i in ip_range:
            ip = f"{ip_base}{i}"
            executor.submit(process_device, ip, username, initial_password, new_password, excel_file)

if __name__ == "__main__":
    main()

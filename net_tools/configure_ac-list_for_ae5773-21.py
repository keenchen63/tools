import paramiko
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
    output = execute_and_print(channel, new_password + '\n')        
    # 发送确认密码
    output = execute_and_print(channel, new_password + '\n')    
    return output

# 配置设备ac-list的函数
def configure_aclist_address(channel, ac_ip_address):
    commands = [
        "diagnose apaddress ac-ipv4-list \n"
        f"ac-ip-list {ac_ip_address} \n"
    ]
    for command in commands:        
        execute_and_print(channel, command)
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
def process_device(ip, username, initial_password, new_password, ac_ip_address):
    try:
        try:
            # 第一次使用初始密码连接
            ssh = ssh_connect(ip, username, initial_password)
            # 设置新密码
            print(f"Setting new password for device {ip}")
            set_new_password(ssh, new_password)            
            # 由于设备会自动断开连接，等待一段时间再重新连接
            time.sleep(8)
        except:
            #使用新密码重新连接
            ssh = ssh_connect(ip, username, new_password)
            channel = ssh.invoke_shell()            
            configure_aclist_address(channel, ac_ip_address)            
            save_config(channel)
            ssh.close()
    except Exception as e:
        print(f"Failed to process device {ip}: {e}")

# 主函数
def main():
    username = "admin"
    initial_password = "admin@huawei.com"
    new_password = "Huawei@123"
    ip_subnet = ipaddress.ip_network('192.168.1.196/32')
    ac_ip_address = "172.31.161.240"

    with ThreadPoolExecutor(max_workers=10) as executor:  # 根据需要调整工作线程数
        for i in ip_subnet:
            ip = f"{i}"
            executor.submit(process_device, ip, username, initial_password, new_password, ac_ip_address)

if __name__ == "__main__":
    main()
